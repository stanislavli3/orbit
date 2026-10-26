from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .history import suppliers_who_quoted
from .models import Part
from .serializers import PartDetailSerializer, PartSerializer


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
