import time
from datetime import date

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from bom_agent.bom_extraction import BOM_FILE_TYPES
from bom_agent.models import Bom, BomRow
from bom_agent.tasks import build_bom
from files_api.models import UploadedFile
from files_api.s3_service import upload_file_to_s3
from files_api.tasks import describe_file
from files_api.views import MAX_UPLOAD_BYTES
from projects.models import Project
from . import handoff
from .call_sheet import NotShortlisted, call_sheet
from .compare import compare, part_side, row_side
from .estimator import DEFAULT_INFLATION, estimate_bom
from .history import suppliers_who_quoted
from .importer import ImportFileError, import_costs
from .models import ImportBatch, Part
from .quick_estimate import quick_report
from .serializers import ImportBatchSerializer, PartDetailSerializer, PartSerializer


class PartListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        parts = Part.objects.filter(workspace_owner=request.user).prefetch_related("costs__supplier")
        q = request.query_params.get("q", "").strip()
        if q:
            parts = parts.filter(Q(part_number__icontains=q) | Q(description__icontains=q))
        return Response(PartSerializer(parts[:200], many=True).data)


class PartDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        part = get_object_or_404(Part, pk=pk, workspace_owner=request.user)
        return Response(PartDetailSerializer(part).data)


class SuppliersWhoQuotedView(APIView):
    """GET ?material=&tolerance=&certification=&part_number= — any combination."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        params = request.query_params
        return Response(
            suppliers_who_quoted(
                request.user,
                material=params.get("material", "").strip(),
                tolerance=params.get("tolerance", "").strip(),
                certification=params.get("certification", "").strip(),
                part_number=params.get("part_number", "").strip(),
            )
        )


MAX_IMPORT_BYTES = 10_000_000


class CostImportView(APIView):
    """GET: past imports. POST: a .csv/.xlsx file (``dry_run=true`` to only validate)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        batches = ImportBatch.objects.filter(workspace_owner=request.user)[:50]
        return Response(ImportBatchSerializer(batches, many=True).data)

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > MAX_IMPORT_BYTES:
            return Response({"detail": "File is larger than 10 MB."}, status=status.HTTP_400_BAD_REQUEST)
        dry_run = str(request.data.get("dry_run", "")).lower() in ("1", "true", "yes")
        try:
            report = import_costs(
                request.user, upload.read(), upload.name, dry_run=dry_run, uploaded_by=request.user
            )
        except ImportFileError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(report, status=status.HTTP_200_OK if dry_run else status.HTTP_201_CREATED)


class BomEstimateView(APIView):
    """GET ?k=3&inflation=0.03 — an early cost estimate for each line of a BOM."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, bom_id):
        bom = get_object_or_404(Bom.objects.prefetch_related("rows"), pk=bom_id, project__owner=request.user)
        try:
            k = int(request.query_params.get("k", 3))
            inflation = float(request.query_params.get("inflation", DEFAULT_INFLATION))
        except ValueError:
            return Response({"detail": "k must be a whole number and inflation a decimal like 0.03."}, status=400)
        if not (1 <= k <= 10 and 0 <= inflation <= 0.5):
            return Response({"detail": "k must be 1-10 and inflation between 0 and 0.5."}, status=400)
        return Response(estimate_bom(bom, request.user, k=k, inflation=inflation))


class QuickEstimateView(APIView):
    """POST a STEP/PDF + project_id: upload, extract the BOM, estimate and shortlist in one request.
    GET <bom_id>: the same report for an existing BOM (e.g. after review edits)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, bom_id):
        bom = get_object_or_404(Bom.objects.prefetch_related("rows"), pk=bom_id, project__owner=request.user)
        return Response(quick_report(bom, request.user))

    def post(self, request):
        started = time.monotonic()
        upload = request.FILES.get("file")
        if not upload or not request.data.get("project_id"):
            return Response({"detail": "Send a file and a project_id."}, status=status.HTTP_400_BAD_REQUEST)
        ext = upload.name.rsplit(".", 1)[-1].lower() if "." in upload.name else ""
        if ext not in BOM_FILE_TYPES:
            return Response({"detail": "Upload a STEP or PDF file."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > MAX_UPLOAD_BYTES:
            return Response({"detail": "File is too large."}, status=status.HTTP_400_BAD_REQUEST)
        project = get_object_or_404(Project, pk=request.data["project_id"], owner=request.user)

        data = upload.read()
        upload.seek(0)
        file = UploadedFile.objects.create(
            project=project,
            uploaded_by=request.user,
            original_name=upload.name,
            file_type=ext,
            s3_key=upload_file_to_s3(upload, project.id),
            file_size=upload.size,
        )
        transaction.on_commit(lambda: describe_file.delay(file.id))
        bom = build_bom(file, data)  # inline: parsing takes well under a second

        report = quick_report(bom, request.user)
        report["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        return Response(report, status=status.HTTP_201_CREATED)


def _int_param(request, name):
    try:
        return int(request.query_params.get(name, ""))
    except ValueError:
        return None


class CallSheetView(APIView):
    """GET ?row_id=&supplier_id= — a phone call sheet for a shortlisted supplier and a BOM line."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        row_id, supplier_id = _int_param(request, "row_id"), _int_param(request, "supplier_id")
        if row_id is None or supplier_id is None:
            return Response({"detail": "Send row_id and supplier_id."}, status=400)
        row = get_object_or_404(BomRow.objects.select_related("bom"), pk=row_id, bom__project__owner=request.user)
        try:
            return Response(call_sheet(request.user, row, supplier_id))
        except NotShortlisted as exc:
            return Response({"detail": str(exc)}, status=404)


class PartCompareView(APIView):
    """GET ?a=<part id> or ?row_id=<BOM row id>, plus &b=<part id>: two parts side by side."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        a, row_id, b = _int_param(request, "a"), _int_param(request, "row_id"), _int_param(request, "b")
        if b is None or (a is None) == (row_id is None):
            return Response({"detail": "Send b and exactly one of a or row_id."}, status=400)
        if a is not None:
            left = part_side(get_object_or_404(Part, pk=a, workspace_owner=request.user))
        else:
            row = get_object_or_404(
                BomRow.objects.select_related("bom__project"), pk=row_id, bom__project__owner=request.user
            )
            left = row_side(row)
        right = part_side(get_object_or_404(Part, pk=b, workspace_owner=request.user))
        return Response(compare(left, right))


class HandoffTimelineView(APIView):
    """GET: elapsed time per part and step for a BOM (``?export=csv`` for a file).
    POST {step, date, part_number?}: set a step's date by hand."""

    permission_classes = [permissions.IsAuthenticated]

    def _bom(self, request, bom_id):
        return get_object_or_404(
            Bom.objects.select_related("project").prefetch_related("rows", "handoff_steps"),
            pk=bom_id, project__owner=request.user,
        )

    def get(self, request, bom_id):
        timeline = handoff.bom_timeline(self._bom(request, bom_id))
        if request.query_params.get("export") == "csv":
            response = HttpResponse(handoff.timeline_csv(timeline), content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="{timeline["reference"]}-handoff.csv"'
            return response
        return Response(timeline)

    def post(self, request, bom_id):
        bom = self._bom(request, bom_id)
        step = request.data.get("step")
        if step not in handoff.STEPS:
            return Response({"detail": f"step must be one of {', '.join(handoff.STEPS)}."}, status=400)
        try:
            day = date.fromisoformat(str(request.data.get("date", "")))
        except ValueError:
            return Response({"detail": "date must be YYYY-MM-DD."}, status=400)
        part_number = str(request.data.get("part_number", "")).strip()
        if part_number and not bom.rows.filter(part_number=part_number).exists():
            return Response({"detail": "That part isn't on this BOM."}, status=400)
        handoff.set_manual(bom, step, day, part_number=part_number)
        return Response(handoff.bom_timeline(self._bom(request, bom_id)))


class HandoffSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(handoff.summary(request.user))
