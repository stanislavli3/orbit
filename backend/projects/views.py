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
        return Project.objects.filter(owner=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ProjectRetrieveView(generics.RetrieveAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)


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
