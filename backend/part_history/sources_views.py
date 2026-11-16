"""Settings -> Workspace sources (SCRUM-52).

Which folders, systems, cost imports and supplier lists Orbit uses, per user.
Everything is scoped to ``request.user`` as the workspace owner.
"""

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ImportBatch, Supplier, WorkspaceSource
from .serializers import SupplierSettingsSerializer, WorkspaceSourceSerializer


class WorkspaceSourceListView(APIView):
    """GET: configured sources plus cost imports and AVL counts. POST: add a source."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sources = WorkspaceSource.objects.filter(workspace_owner=request.user)
        suppliers = Supplier.objects.filter(workspace_owner=request.user)
        imports = ImportBatch.objects.filter(workspace_owner=request.user)[:20]
        return Response(
            {
                "sources": WorkspaceSourceSerializer(sources, many=True).data,
                "kinds": [{"value": k, "label": label} for k, label in WorkspaceSource.KIND_CHOICES],
                "cost_imports": [
                    {"id": b.id, "filename": b.filename, "imported_rows": b.imported_rows, "created_at": b.created_at}
                    for b in imports
                ],
                "supplier_counts": {
                    "total": suppliers.count(),
                    "approved": suppliers.filter(is_approved=True).count(),
                },
            }
        )

    def post(self, request):
        serializer = WorkspaceSourceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if WorkspaceSource.objects.filter(
            workspace_owner=request.user, kind=serializer.validated_data["kind"], name=serializer.validated_data["name"]
        ).exists():
            return Response({"detail": "A source with this name already exists."}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(workspace_owner=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WorkspaceSourceDetailView(APIView):
    """PATCH: rename / enable / disable. DELETE: remove the source (not its data)."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        source = get_object_or_404(WorkspaceSource, pk=pk, workspace_owner=request.user)
        serializer = WorkspaceSourceSerializer(source, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        get_object_or_404(WorkspaceSource, pk=pk, workspace_owner=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SupplierSettingsListView(APIView):
    """GET ?approved=true|false — the workspace's suppliers with their AVL status."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        suppliers = Supplier.objects.filter(workspace_owner=request.user)
        approved = request.query_params.get("approved")
        if approved in ("true", "false"):
            suppliers = suppliers.filter(is_approved=approved == "true")
        return Response(SupplierSettingsSerializer(suppliers[:500], many=True).data)


class SupplierSettingsDetailView(APIView):
    """PATCH {is_approved, approval_note} — add to or remove from the approved vendor list."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        supplier = get_object_or_404(Supplier, pk=pk, workspace_owner=request.user)
        serializer = SupplierSettingsSerializer(supplier, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
