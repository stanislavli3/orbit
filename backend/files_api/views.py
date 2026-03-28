import json
import os
import threading

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import UploadedFile, ExtractionResult, FileEmbedding
from .serializers import UploadedFileSerializer
from .s3_service import upload_file_to_s3
from projects.models import Project
from .embeddings import generate_embedding

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 100_000_000))  # 100 MB default


def _run_extraction(file_id: int, s3_key: str, file_name: str, file_type: str):
    from .s3_service import download_file_from_s3
    from .extractor import extract_step_header
    from .ai_description import generate_file_description

    try:
        UploadedFile.objects.filter(id=file_id).update(status="processing")
        file_bytes = download_file_from_s3(s3_key)
        result = extract_step_header(file_bytes)
        ExtractionResult.objects.create(file_id=file_id, result_json=result)
        description = generate_file_description(file_name, file_type, result)
        UploadedFile.objects.filter(id=file_id).update(
            status="processed", description=description
        )
        embedding_payload = f"{file_name}\n{description}\n{json.dumps(result)}"
        embedding_vector = generate_embedding(embedding_payload)
        if embedding_vector:
            FileEmbedding.objects.update_or_create(
                file_id=file_id, defaults={"embedding_json": embedding_vector}
            )
    except Exception:
        UploadedFile.objects.filter(id=file_id).update(status="failed")


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

        threading.Thread(
            target=_run_extraction,
            args=(file_record.id, s3_key, uploaded_file.name, ext),
            daemon=True,
        ).start()

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


class FileDescriptionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, file_id):
        file_record = get_object_or_404(
            UploadedFile, id=file_id, project__owner=request.user
        )
        description = request.data.get("description", "")
        file_record.description = description
        file_record.save(update_fields=["description"])
        return Response(
            {"description": file_record.description}, status=status.HTTP_200_OK
        )


class FileResultView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, file_id):
        file_record = get_object_or_404(
            UploadedFile, id=file_id, project__owner=request.user
        )
        try:
            result = file_record.result
        except ExtractionResult.DoesNotExist:
            return Response(
                {"error": "Extraction result not available yet"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(result.result_json, status=status.HTTP_200_OK)
