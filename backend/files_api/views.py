import json
import os
import threading

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import UploadedFile, ExtractionResult, FileEmbedding
from .serializers import UploadedFileSerializer
from .s3_service import upload_file_to_s3, delete_file_from_s3, generate_presigned_url
from projects.models import Project
from .embeddings import generate_embedding

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 100_000_000))  # 100 MB default


def _run_description(file_id: int, s3_key: str, file_name: str, file_type: str):
    """Generate AI description on upload only. Status stays 'uploaded'."""
    from .s3_service import download_file_from_s3
    from .extractor import extract_step_header
    from .ai_description import generate_file_description

    try:
        file_bytes = download_file_from_s3(s3_key)
        result = extract_step_header(file_bytes)
        description = generate_file_description(file_name, file_type, result)
        if description:
            UploadedFile.objects.filter(id=file_id).update(description=description)
    except Exception:
        pass  # Non-fatal: description stays empty, file is still usable


def _run_extraction(file_id: int, s3_key: str, file_name: str, file_type: str):
    """Full extraction: STEP parse + profile + embedding. Triggered on demand."""
    from .s3_service import download_file_from_s3
    from .extractor import extract_step_header
    from .ai_description import generate_file_description, generate_engineering_profile

    try:
        UploadedFile.objects.filter(id=file_id).update(status="processing")
        file_bytes = download_file_from_s3(s3_key)
        result = extract_step_header(file_bytes)
        description = generate_file_description(file_name, file_type, result)
        profile = generate_engineering_profile(file_name, file_type, result)
        result["profile"] = profile
        ExtractionResult.objects.update_or_create(
            file_id=file_id, defaults={"result_json": result}
        )
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


VAULT_EXTENSIONS = {"step", "stp", "pdf", "dwg", "dxf", "iges", "igs"}
LIBRARY_EXTENSIONS = {"xlsx", "csv", "pdf", "docx"}


class FileUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        project_id = request.data.get("project_id")
        category = request.data.get("category", "vault")

        if category not in ("vault", "library"):
            category = "vault"

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

        allowed_extensions = VAULT_EXTENSIONS if category == "vault" else LIBRARY_EXTENSIONS
        ext = (
            uploaded_file.name.rsplit(".", 1)[-1].lower()
            if "." in uploaded_file.name
            else ""
        )
        if ext not in allowed_extensions:
            return Response(
                {
                    "error": f"Unsupported file type '.{ext}'. Allowed: {', '.join(sorted(allowed_extensions))}"
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
            category=category,
        )

        if category == "vault":
            threading.Thread(
                target=_run_description,
                args=(file_record.id, s3_key, uploaded_file.name, ext),
                daemon=True,
            ).start()

        serializer = UploadedFileSerializer(file_record)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class FileExtractView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, file_id):
        file_record = get_object_or_404(
            UploadedFile, id=file_id, project__owner=request.user
        )
        if file_record.status == "processing":
            return Response(
                {"error": "Extraction already in progress"},
                status=status.HTTP_409_CONFLICT,
            )
        threading.Thread(
            target=_run_extraction,
            args=(file_record.id, file_record.s3_key, file_record.original_name, file_record.file_type),
            daemon=True,
        ).start()
        return Response({"status": "processing"}, status=status.HTTP_202_ACCEPTED)


class AllFilesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        files = (
            UploadedFile.objects
            .filter(project__owner=request.user)
            .select_related("project")
            .order_by("-created_at")
        )
        serializer = UploadedFileSerializer(files, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProjectFileListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, project_id):
        try:
            project = Project.objects.get(id=project_id, owner=request.user)
        except Project.DoesNotExist:
            return Response(
                {"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND
            )

        qs = UploadedFile.objects.filter(project=project).order_by("-created_at")
        category = request.query_params.get("category")
        if category in ("vault", "library"):
            qs = qs.filter(category=category)
        serializer = UploadedFileSerializer(qs, many=True)
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


class FileDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, file_id):
        file_record = get_object_or_404(
            UploadedFile, id=file_id, project__owner=request.user
        )
        s3_key = file_record.s3_key
        file_record.delete()
        try:
            delete_file_from_s3(s3_key)
        except Exception:
            # Best-effort delete; ignore S3 errors
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class FileDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, file_id):
        file_record = get_object_or_404(
            UploadedFile, id=file_id, project__owner=request.user
        )
        url = generate_presigned_url(file_record.s3_key)
        return Response({"url": url}, status=status.HTTP_200_OK)


class FileProfileDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, file_id):
        file_record = get_object_or_404(
            UploadedFile, id=file_id, project__owner=request.user
        )
        try:
            extraction = file_record.result
        except ExtractionResult.DoesNotExist:
            return Response(
                {"error": "Profile not available yet"},
                status=status.HTTP_404_NOT_FOUND,
            )
        profile = extraction.result_json.get("profile") or {}
        safe_name = file_record.original_name.rsplit(".", 1)[0].replace(" ", "_")
        response = HttpResponse(
            json.dumps(profile, indent=2),
            content_type="application/json",
        )
        response["Content-Disposition"] = f'attachment; filename="{safe_name}_profile.json"'
        return response
