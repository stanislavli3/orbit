from datetime import timedelta

from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from .models import Project, ExportLog
from .serializers import ProjectSerializer
from files_api.models import UploadedFile, ExtractionResult


class ProjectListCreateView(generics.ListCreateAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Project.objects.filter(owner=self.request.user).order_by("-created_at")
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ProjectRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)

    def perform_destroy(self, instance):
        from files_api.s3_service import delete_file_from_s3

        for f in instance.files.all():
            try:
                delete_file_from_s3(f.s3_key)
            except Exception:
                pass
        instance.delete()


class ProjectExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk, owner=request.user)
        files = (
            UploadedFile.objects.filter(project=project)
            .prefetch_related("result")
            .order_by("-created_at")
        )
        payload = []
        for f in files:
            try:
                result = f.result.result_json
            except ExtractionResult.DoesNotExist:
                result = None
            payload.append(
                {
                    "file": {
                        "id": f.id,
                        "original_name": f.original_name,
                        "file_type": f.file_type,
                        "file_size": f.file_size,
                        "status": f.status,
                        "created_at": f.created_at.isoformat(),
                    },
                    "result": result,
                }
            )
        ExportLog.objects.create(
            project=project,
            user=request.user,
            file_count=len(payload),
        )
        return Response(payload, status=status.HTTP_200_OK)


class HistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from assistant.models import ChatSession

        period = request.query_params.get("period", "")
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=6)

        def apply_period(qs, field="created_at"):
            if period == "today":
                return qs.filter(**{f"{field}__gte": today_start})
            elif period == "last7days":
                return qs.filter(**{f"{field}__gte": week_start, f"{field}__lt": today_start})
            elif period == "older":
                return qs.filter(**{f"{field}__lt": week_start})
            return qs

        uploads = apply_period(
            UploadedFile.objects.filter(uploaded_by=request.user).select_related("project")
        )
        exports = apply_period(
            ExportLog.objects.filter(user=request.user).select_related("project")
        )
        chats = apply_period(
            ChatSession.objects.filter(user=request.user).select_related("project")
        )

        events = []

        for u in uploads:
            events.append({
                "id": f"upload-{u.id}",
                "type": "upload",
                "title": "File uploaded",
                "project": u.project.name if u.project else "—",
                "status": u.status,
                "created_at": u.created_at.isoformat(),
                "detail": u.original_name,
            })

        for e in exports:
            events.append({
                "id": f"export-{e.id}",
                "type": "export",
                "title": "JSON profiles exported",
                "project": e.project.name,
                "status": "completed",
                "created_at": e.created_at.isoformat(),
                "detail": f"{e.file_count} files",
            })

        for c in chats:
            events.append({
                "id": f"chat-{c.id}",
                "type": "chat",
                "title": "New chat started",
                "project": c.project.name if c.project else "—",
                "status": "completed",
                "created_at": c.created_at.isoformat(),
                "detail": str(c.session_id)[:8],
            })

        events.sort(key=lambda x: x["created_at"], reverse=True)
        return Response(events, status=status.HTTP_200_OK)
