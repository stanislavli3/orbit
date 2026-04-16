"""
Library document endpoints (#58 + #59).

POST   /api/library/documents/              — upload a document
GET    /api/library/documents/              — list workspace library
PATCH  /api/library/documents/<id>/         — update doc_type
DELETE /api/library/documents/<id>/         — delete document
POST   /api/library/documents/promote/      — promote project file to library
"""

import threading
import uuid

from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404

from files_api.s3_service import get_s3_client, generate_presigned_url
from files_api.embeddings import generate_embedding
from files_api.models import UploadedFile
from .models import LibraryDocument, LibraryEmbedding
from .serializers import LibraryDocumentSerializer

ALLOWED_EXTENSIONS = {"xlsx", "csv", "pdf", "docx"}
MAX_UPLOAD_BYTES = 50_000_000  # 50 MB


def _ingest_library_embedding(doc_id: int) -> None:
    """Background: generate and store embedding for a library document (#59)."""
    try:
        doc = LibraryDocument.objects.get(id=doc_id)
        text = f"{doc.original_name} {doc.doc_type} {' '.join(doc.doc_type.replace('-', ' ').split())}"
        vector = generate_embedding(text)
        LibraryEmbedding.objects.update_or_create(
            document=doc,
            defaults={"embedding_json": vector, "doc_type": doc.doc_type},
        )
    except Exception:
        pass


def _upload_to_library_s3(file_obj, workspace_owner_id: int) -> str:
    s3 = get_s3_client()
    import os
    bucket = os.getenv("AWS_STORAGE_BUCKET_NAME")
    ext = ("." + file_obj.name.rsplit(".", 1)[-1]) if "." in file_obj.name else ""
    key = f"library/{workspace_owner_id}/{uuid.uuid4()}{ext}"
    s3.upload_fileobj(file_obj, bucket, key)
    return key


class LibraryDocumentListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = LibraryDocument.objects.filter(workspace_owner=request.user)
        doc_type = request.query_params.get("doc_type", "").strip()
        if doc_type:
            qs = qs.filter(doc_type=doc_type)
        return Response(LibraryDocumentSerializer(qs, many=True).data)

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        if uploaded_file.size > MAX_UPLOAD_BYTES:
            return Response(
                {"detail": f"File exceeds {MAX_UPLOAD_BYTES // 1_000_000} MB limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ext = uploaded_file.name.rsplit(".", 1)[-1].lower() if "." in uploaded_file.name else ""
        if ext not in ALLOWED_EXTENSIONS:
            return Response(
                {"detail": f"Unsupported type '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        doc_type = request.data.get("doc_type", "").strip()
        valid_types = {c[0] for c in LibraryDocument.TYPE_CHOICES}
        if doc_type and doc_type not in valid_types:
            return Response({"detail": f"Invalid doc_type '{doc_type}'."}, status=status.HTTP_400_BAD_REQUEST)

        s3_key = _upload_to_library_s3(uploaded_file, request.user.id)

        doc = LibraryDocument.objects.create(
            workspace_owner=request.user,
            original_name=uploaded_file.name,
            doc_type=doc_type,
            s3_key=s3_key,
            file_size=uploaded_file.size,
            file_type=ext,
        )

        threading.Thread(target=_ingest_library_embedding, args=(doc.id,), daemon=True).start()

        return Response(LibraryDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


class LibraryDocumentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        doc = get_object_or_404(LibraryDocument, pk=pk, workspace_owner=request.user)
        doc_type = request.data.get("doc_type", "").strip()
        valid_types = {c[0] for c in LibraryDocument.TYPE_CHOICES}
        if doc_type and doc_type not in valid_types:
            return Response({"detail": f"Invalid doc_type '{doc_type}'."}, status=status.HTTP_400_BAD_REQUEST)
        doc.doc_type = doc_type
        doc.save(update_fields=["doc_type"])

        # Re-index with new type
        threading.Thread(target=_ingest_library_embedding, args=(doc.id,), daemon=True).start()

        return Response(LibraryDocumentSerializer(doc).data)

    def delete(self, request, pk):
        doc = get_object_or_404(LibraryDocument, pk=pk, workspace_owner=request.user)
        s3_key = doc.s3_key
        doc.delete()
        try:
            from files_api.s3_service import delete_file_from_s3
            delete_file_from_s3(s3_key)
        except Exception:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class LibraryDocumentDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        doc = get_object_or_404(LibraryDocument, pk=pk, workspace_owner=request.user)
        url = generate_presigned_url(doc.s3_key)
        return Response({"url": url})


class LibraryPromoteView(APIView):
    """Promote a project UploadedFile to the workspace Library."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        file_id = request.data.get("file_id")
        doc_type = request.data.get("doc_type", "").strip()

        if not file_id:
            return Response({"detail": "file_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        source = get_object_or_404(UploadedFile, pk=file_id, project__owner=request.user)

        valid_types = {c[0] for c in LibraryDocument.TYPE_CHOICES}
        if doc_type and doc_type not in valid_types:
            return Response({"detail": f"Invalid doc_type '{doc_type}'."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if already promoted
        existing = LibraryDocument.objects.filter(
            workspace_owner=request.user, source_file=source
        ).first()
        if existing:
            return Response(LibraryDocumentSerializer(existing).data, status=status.HTTP_200_OK)

        doc = LibraryDocument.objects.create(
            workspace_owner=request.user,
            original_name=source.original_name,
            doc_type=doc_type,
            s3_key=source.s3_key,
            file_size=source.file_size,
            file_type=source.file_type,
            source_file=source,
        )

        threading.Thread(target=_ingest_library_embedding, args=(doc.id,), daemon=True).start()

        return Response(LibraryDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)
