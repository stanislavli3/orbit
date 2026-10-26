"""Structured BOM API (SCRUM-22): list, review, edit rows, approve, re-extract."""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from files_api.models import UploadedFile
from .bom_extraction import BOM_FILE_TYPES
from .models import Bom, BomRow
from .serializers import BomRowSerializer, BomSerializer
from .tasks import enqueue_bom_extraction

EDITABLE_FIELDS = ("part_number", "description", "material", "process", "quantity", "spec")


def _user_bom(request, pk) -> Bom:
    return get_object_or_404(
        Bom.objects.prefetch_related("rows"), pk=pk, project__owner=request.user
    )


class BomListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        boms = Bom.objects.filter(project__owner=request.user).prefetch_related("rows")
        if request.query_params.get("project_id"):
            boms = boms.filter(project_id=request.query_params["project_id"])
        if request.query_params.get("file_id"):
            boms = boms.filter(source_file_id=request.query_params["file_id"])
        return Response(BomSerializer(boms, many=True).data)


class BomDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        return Response(BomSerializer(_user_bom(request, pk)).data)


class BomRowView(APIView):
    """A reviewer's correction. An edited row is trusted: its flags are cleared."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk, row_id):
        bom = _user_bom(request, pk)
        row = get_object_or_404(BomRow, pk=row_id, bom=bom)
        changes = {f: request.data[f] for f in EDITABLE_FIELDS if f in request.data}
        serializer = BomRowSerializer(row, data=changes, partial=True)
        serializer.is_valid(raise_exception=True)
        sources = dict(row.sources)
        for field in changes:
            sources[field] = f"edited by {request.user.username}"
        serializer.save(edited=True, confidence=1.0, flags=[], sources=sources)
        return Response(serializer.data)

    def delete(self, request, pk, row_id):
        bom = _user_bom(request, pk)
        get_object_or_404(BomRow, pk=row_id, bom=bom).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BomApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        bom = _user_bom(request, pk)
        if bom.status not in ("needs_review", "approved"):
            return Response(
                {"detail": f"A BOM that is {bom.get_status_display().lower()} can't be approved."},
                status=status.HTTP_409_CONFLICT,
            )
        bom.status = "approved"
        bom.approved_by = request.user
        bom.approved_at = timezone.now()
        bom.save(update_fields=["status", "approved_by", "approved_at"])
        return Response(BomSerializer(bom).data)


class FileBomExtractView(APIView):
    """(Re-)extract a BOM from an uploaded file. Earlier BOMs are kept."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, file_id):
        file = get_object_or_404(UploadedFile, pk=file_id, project__owner=request.user)
        if (file.file_type or "").lower() not in BOM_FILE_TYPES:
            return Response(
                {"detail": "BOMs can be extracted from STEP and PDF files only."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        enqueue_bom_extraction(file)
        return Response({"status": "extracting"}, status=status.HTTP_202_ACCEPTED)
