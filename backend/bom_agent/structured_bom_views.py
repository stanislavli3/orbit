"""Structured BOM API (SCRUM-22): list, review, edit rows, approve, re-extract."""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from files_api.models import UploadedFile
from part_history.history import record_bom_parts
from .bom_extraction import BOM_FILE_TYPES
from .models import Bom, BomRow
from .serializers import BomRowSerializer, BomSerializer
from .tasks import enqueue_bom_extraction

EDITABLE_FIELDS = ("part_number", "description", "material", "process", "quantity", "spec", "revision")


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
        record_bom_parts(bom, request.user)  # approved part numbers join part history (SCRUM-28)
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


# ── Design change review (SCRUM-23, SCRUM-55) ────────────────────────────────

def _cited_rows(bom: Bom) -> list[dict]:
    citation = {"bom_id": bom.pk, "reference": bom.reference, "source_name": bom.source_name}
    return [{**BomRowSerializer(r).data, "bom": citation} for r in bom.rows.all()]


class BomCompareView(APIView):
    """GET ?base=<bom>&target=<bom>[&radius=50]: change summary, conflict flags
    across the project's files, and the parts to recheck for each changed part."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from files_api.s3_service import download_file_from_s3
        from .design_change import diff_rows, find_conflicts, neighbours, part_key

        try:
            base_id, target_id = int(request.query_params["base"]), int(request.query_params["target"])
            radius = float(request.query_params.get("radius", 50))
        except (KeyError, ValueError):
            return Response({"detail": "Pass base and target BOM ids (and an optional numeric radius)."},
                            status=status.HTTP_400_BAD_REQUEST)
        base, target = _user_bom(request, base_id), _user_bom(request, target_id)
        diff = diff_rows(_cited_rows(base), _cited_rows(target))

        # Conflicts: the latest BOM of every file in the project, plus the two compared.
        latest = {}
        for bom in Bom.objects.filter(project=target.project).exclude(status="failed").prefetch_related("rows"):
            latest.setdefault(bom.source_file_id or f"bom-{bom.pk}", bom)
        boms = {b.pk: b for b in [*latest.values(), base, target]}
        conflicts = find_conflicts([r for b in boms.values() for r in _cited_rows(b)])

        # Neighbours come from the newer version's STEP assembly, else the older one's.
        changed = [c["part_number"] for c in diff["changed"]] + [a["part_number"] for a in diff["added"]]
        recheck, assembly, target_occurrences = {}, None, None
        for bom in (target, base):
            f = bom.source_file
            if f and (f.file_type or "").lower() in ("step", "stp"):
                try:
                    data = download_file_from_s3(f.s3_key)
                except Exception:
                    continue
                if bom is target:
                    from .design_change import assembly_occurrences
                    target_occurrences = assembly_occurrences(data) or None
                assembly = {"bom_id": bom.pk, "reference": bom.reference, "source_name": bom.source_name}
                for pn in changed:
                    recheck[pn] = neighbours(data, pn, radius)
                for r in diff["removed"]:
                    if part_key(r["part_number"]) and bom is base:
                        recheck[r["part_number"]] = neighbours(data, r["part_number"], radius)
                break

        from .galvanic import galvanic_flags

        galvanic = galvanic_flags(_cited_rows(target), target_occurrences,
                                  _environment(request), radius)
        return Response({
            "galvanic": galvanic,
            "base": {"id": base.pk, "reference": base.reference, "source_name": base.source_name},
            "target": {"id": target.pk, "reference": target.reference, "source_name": target.source_name},
            **diff,
            "conflicts": conflicts,
            "recheck": recheck,
            "assembly": assembly,
        })


# ── Buyer handoff (SCRUM-69) and galvanic pairs (SCRUM-77) ───────────────────

def _assembly_occurrences(bom: Bom):
    """Placed parts from the BOM's STEP file, or None when there is no readable assembly."""
    from files_api.s3_service import download_file_from_s3
    from .design_change import assembly_occurrences

    f = bom.source_file
    if not f or (f.file_type or "").lower() not in ("step", "stp"):
        return None
    try:
        return assembly_occurrences(download_file_from_s3(f.s3_key)) or None
    except Exception:
        return None


def _environment(request) -> str:
    return "harsh" if request.query_params.get("environment") == "harsh" else "general"


class BomHandoffView(APIView):
    """GET: read-only buyer handoff for one BOM (?environment=harsh tightens galvanic checks)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        from .handoff import build_handoff

        bom = _user_bom(request, pk)
        return Response(build_handoff(bom, request.user, environment=_environment(request),
                                      occurrences=_assembly_occurrences(bom)))
