from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .history import suppliers_who_quoted
from .importer import ImportFileError, import_costs
from .models import ImportBatch, Part
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
