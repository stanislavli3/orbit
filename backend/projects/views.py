from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from .models import Project
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
        return Response(payload, status=status.HTTP_200_OK)
