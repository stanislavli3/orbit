"""Quote COTS override (SCRUM-31) and RFQ spec sheets (SCRUM-32).

PATCH /api/bom/quotes/<id>/                                 — human COTS override
POST  /api/bom/structured/<pk>/rows/<row_id>/rfq/           — draft an RFQ from a BOM row
GET/PATCH /api/bom/rfqs/<id>/                               — view / edit a draft
GET   /api/bom/rfqs/<id>/export/                            — printable HTML spec sheet
"""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BomRow, RfqDraft, SupplierQuote
from .serializers import RfqDraftSerializer, SupplierQuoteSerializer


class SupplierQuoteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        quote = get_object_or_404(SupplierQuote, pk=pk, line_item__run__created_by=request.user)
        serializer = SupplierQuoteSerializer(quote, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        extra = {"is_cots_source": "human"} if "is_cots" in serializer.validated_data else {}
        serializer.save(**extra)
        return Response(serializer.data)


def draft_from_row(row: BomRow, user) -> RfqDraft:
    """Copy what the BOM row actually states; leave the rest blank to be confirmed."""
    context = " — ".join(v for v in (row.description, row.spec) if v)
    return RfqDraft.objects.create(
        bom_row=row,
        created_by=user,
        part_number=row.part_number,
        part_context=context,
        material=row.material,
        process=row.process,
        quantity=row.quantity or None,
    )


class BomRowRfqView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, row_id):
        row = get_object_or_404(BomRow, pk=row_id, bom_id=pk, bom__project__owner=request.user)
        rfq = draft_from_row(row, request.user)
        return Response(RfqDraftSerializer(rfq).data, status=status.HTTP_201_CREATED)


def _user_rfq(request, pk) -> RfqDraft:
    return get_object_or_404(
        RfqDraft.objects.select_related("bom_row__bom"), pk=pk, created_by=request.user
    )


class RfqDraftView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        return Response(RfqDraftSerializer(_user_rfq(request, pk)).data)

    def patch(self, request, pk):
        serializer = RfqDraftSerializer(_user_rfq(request, pk), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class RfqExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        rfq = _user_rfq(request, pk)
        rows = [
            (label, getattr(rfq, field))
            for field, label in [("part_number", "Part number"), *RfqDraft.CRITICAL_FIELDS.items(), ("process", "Process")]
        ]
        html = render_to_string("bom_agent/rfq_spec_sheet.html", {"rfq": rfq, "rows": rows})
        response = HttpResponse(html, content_type="text/html; charset=utf-8")
        response["Content-Disposition"] = f'inline; filename="rfq-{rfq.pk}.html"'
        return response
