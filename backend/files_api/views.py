from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import UploadedFile
from .serializers import UploadedFileSerializer
from .s3_service import upload_file_to_s3
from projects.models import Project

class FileUploadView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        project_id = request.data.get("project_id")

        if not uploaded_file:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        if not project_id:
            return Response({"error": "No project_id provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        s3_key = upload_file_to_s3(uploaded_file, project_id)

        file_type = ""
        if "." in uploaded_file.name:
            file_type = uploaded_file.name.split(".")[-1].lower()

        user = request.user if request.user.is_authenticated else project.owner

        file_record = UploadedFile.objects.create(
            project=project,
            uploaded_by=user,
            original_name=uploaded_file.name,
            file_type=file_type,
            s3_key=s3_key,
            file_size=uploaded_file.size,
            status="uploaded",
        )

        serializer = UploadedFileSerializer(file_record)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProjectFileListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, project_id):
        files = UploadedFile.objects.filter(project_id=project_id).order_by("-created_at")
        serializer = UploadedFileSerializer(files, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)