import json
import os

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .connectors import CONNECTORS, ConnectorError, index_source
from .models import ConnectedSource, UploadedFile, ExtractionResult
from .serializers import ConnectedSourceSerializer, UploadedFileSerializer
from .s3_service import upload_file_to_s3, delete_file_from_s3, generate_presigned_url
from .tasks import describe_file, extract_file
from projects.models import Project
from bom_agent.tasks import enqueue_bom_extraction

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 100_000_000))  # 100 MB default


VAULT_EXTENSIONS = {"step", "stp", "pdf", "dwg", "dxf", "iges", "igs", "m", "mat"}
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

        # .m/.mat aren't CAD, so skip the BOM agent for them.
        if category == "vault" and ext in ("m", "mat"):
            transaction.on_commit(lambda: describe_file.delay(file_record.id))
        elif category == "vault":
            transaction.on_commit(lambda: describe_file.delay(file_record.id))
            enqueue_bom_extraction(file_record)

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
        # Marked before enqueueing so the 409 guard holds and a worker restart
        # can find the job even if it was never picked up.
        file_record.status = "processing"
        file_record.save(update_fields=["status"])
        transaction.on_commit(lambda: extract_file.delay(file_record.id))
        return Response({"status": "processing"}, status=status.HTTP_202_ACCEPTED)


def _search(qs, q):
    """Plain substring search over name, description, owner and parsed metadata
    (so MATLAB variable / function names are findable)."""
    q = (q or "").strip()
    if not q:
        return qs
    return qs.filter(
        Q(original_name__icontains=q)
        | Q(description__icontains=q)
        | Q(owner_name__icontains=q)
        | Q(last_editor_name__icontains=q)
        | Q(result__result_json__icontains=q)
    ).distinct()


class AllFilesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        files = (
            UploadedFile.objects
            .filter(project__owner=request.user)
            .select_related("project", "uploaded_by", "connected_source")
            .order_by("-created_at")
        )
        files = _search(files, request.query_params.get("q"))
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

        qs = (
            UploadedFile.objects.filter(project=project)
            .select_related("project", "uploaded_by", "connected_source")
            .order_by("-created_at")
        )
        qs = _search(qs, request.query_params.get("q"))
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
        is_upload = file_record.source == "upload"
        file_record.delete()
        if not is_upload:
            # Connected files live at their source; only Orbit's index entry is removed.
            return Response(status=status.HTTP_204_NO_CONTENT)
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
        if file_record.source != "upload":
            return Response({"url": file_record.external_url}, status=status.HTTP_200_OK)
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


# ── Connected sources (SCRUM-50/78) ───────────────────────────────────────


class ConnectorStatusView(APIView):
    """Which connectors are usable on this server (e.g. Drive credentials present)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({kind: cls.status() for kind, cls in CONNECTORS.items()})


class ProjectSourcesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, owner=request.user)
        sources = project.connected_sources.order_by("created_at")
        return Response(ConnectedSourceSerializer(sources, many=True).data)

    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, owner=request.user)
        kind = request.data.get("kind")
        cls = CONNECTORS.get(kind)
        if cls is None:
            return Response({"error": f"Unknown source kind '{kind}'."}, status=400)
        st = cls.status()
        if not st["configured"]:
            return Response({"error": st["detail"]}, status=400)
        try:
            config = cls.validate_config(request.data.get("config") or {})
        except ConnectorError as exc:
            return Response({"error": str(exc)}, status=400)
        default_name = config.get("path") or config.get("folder_id") or ""
        source = ConnectedSource.objects.create(
            project=project,
            created_by=request.user,
            kind=kind,
            name=(request.data.get("name") or "").strip() or os.path.basename(default_name) or default_name,
            config=config,
        )
        return Response(ConnectedSourceSerializer(source).data, status=201)


class SourceDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, source_id):
        source = get_object_or_404(ConnectedSource, id=source_id, project__owner=request.user)
        source.delete()  # cascades to the index entries; originals are untouched
        return Response(status=status.HTTP_204_NO_CONTENT)


class SourceIndexView(APIView):
    """Index now. Runs inline — fine for demo-sized folders."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, source_id):
        source = get_object_or_404(ConnectedSource, id=source_id, project__owner=request.user)
        try:
            summary = index_source(source)
        except ConnectorError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        source.refresh_from_db()
        return Response({**summary, "source": ConnectedSourceSerializer(source).data})
