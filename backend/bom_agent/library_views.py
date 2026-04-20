"""
Library document endpoints (#58 + #59 + #60).

POST   /api/library/documents/              — upload a document
GET    /api/library/documents/              — list workspace library
PATCH  /api/library/documents/<id>/         — update doc_type
DELETE /api/library/documents/<id>/         — delete document
POST   /api/library/documents/promote/      — promote project file to library
"""

import csv
import io
import os
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
_EXTRACT_ROW_LIMIT = 300
_EXTRACT_CHAR_LIMIT = 8_000


# ── Content extraction helpers (#60) ─────────────────────────────────────────

def _extract_csv(file_bytes: bytes) -> str:
    text = file_bytes.decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(text))
    rows = []
    for i, row in enumerate(reader):
        if i >= _EXTRACT_ROW_LIMIT:
            break
        line = ", ".join(c.strip() for c in row if c.strip())
        if line:
            rows.append(line)
    return "\n".join(rows)[:_EXTRACT_CHAR_LIMIT]


def _extract_xlsx(file_bytes: bytes) -> str:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        lines = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                if cells:
                    lines.append(", ".join(cells))
            if len(lines) >= _EXTRACT_ROW_LIMIT:
                break
        wb.close()
        return "\n".join(lines[:_EXTRACT_ROW_LIMIT])[:_EXTRACT_CHAR_LIMIT]
    except Exception:
        return ""


def _extract_pdf(file_bytes: bytes) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages[:20]:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)[:_EXTRACT_CHAR_LIMIT]
    except Exception:
        return ""


def _extract_text(file_bytes: bytes, file_type: str) -> str:
    """Extract plain text from a library document based on its file type."""
    if file_type == "csv":
        return _extract_csv(file_bytes)
    if file_type == "xlsx":
        return _extract_xlsx(file_bytes)
    if file_type == "pdf":
        return _extract_pdf(file_bytes)
    # docx: return empty — no python-docx dependency; filename still used for context
    return ""


def _ingest_library_embedding(doc_id: int) -> None:
    """
    Background: download doc from S3, extract text content, embed it, and store
    the embedding + extracted text (#60 — replaces filename-only stub).
    """
    try:
        doc = LibraryDocument.objects.get(id=doc_id)

        # Download from S3
        s3 = get_s3_client()
        bucket = os.getenv("AWS_STORAGE_BUCKET_NAME", "")
        buf = io.BytesIO()
        s3.download_fileobj(bucket, doc.s3_key, buf)
        file_bytes = buf.getvalue()

        # Extract meaningful text from the document
        extracted = _extract_text(file_bytes, doc.file_type)

        # Persist extracted text so the BOM agent can include it in context
        if extracted:
            LibraryDocument.objects.filter(pk=doc.pk).update(extracted_text=extracted)
            doc.extracted_text = extracted

        # Embed extracted content; fall back to name+type if extraction produced nothing
        embed_source = extracted if extracted else f"{doc.original_name} {doc.doc_type}"
        vector = generate_embedding(embed_source)

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
