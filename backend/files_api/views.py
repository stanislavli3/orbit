import os

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import UploadedFile
from .serializers import UploadedFileSerializer
from .s3_service import upload_file_to_s3
from projects.models import Project

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 100_000_000))  # 100 MB default

ALLOWED_EXTENSIONS = {"step", "stp", "pdf", "dwg", "dxf", "iges", "igs"}


class FileUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        project_id = request.data.get("project_id")

        if not uploaded_file:
            return Response(
                {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not project_id:
            return Response(
                {"error": "No project_id provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        if uploaded_file.size > MAX_UPLOAD_BYTES:
            return Response(
                {
                    "error": f"File exceeds maximum allowed size of {MAX_UPLOAD_BYTES // 1_000_000} MB"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ext = (
            uploaded_file.name.rsplit(".", 1)[-1].lower()
            if "." in uploaded_file.name
            else ""
        )
        if ext not in ALLOWED_EXTENSIONS:
            return Response(
                {
                    "error": f"Unsupported file type '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = get_object_or_404(Project, id=project_id, owner=request.user)

        s3_key = upload_file_to_s3(uploaded_file, project_id)

        file_record = UploadedFile.objects.create(
            project=project,
            uploaded_by=request.user,
            original_name=uploaded_file.name,
            file_type=ext,
            s3_key=s3_key,
            file_size=uploaded_file.size,
            status="uploaded",
        )

        serializer = UploadedFileSerializer(file_record)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProjectFileListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, project_id):
        try:
            project = Project.objects.get(id=project_id, owner=request.user)
        except Project.DoesNotExist:
            return Response(
                {"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND
            )

        files = UploadedFile.objects.filter(project=project).order_by("-created_at")
        serializer = UploadedFileSerializer(files, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
