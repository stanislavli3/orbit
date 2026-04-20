"""
Views for BOM Research Run endpoints.

POST  /api/bom/runs/                  — start a new run (scans project files)
GET   /api/bom/runs/<id>/             — run status + results
PATCH /api/bom/runs/<id>/inputs/      — submit clarifying-question answers
GET   /api/bom/runs/<id>/questions/   — structured pending questions
GET   /api/bom/runs/<id>/excel/       — presigned S3 download URL
"""

from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404

from projects.models import Project
from files_api.models import UploadedFile, ExtractionResult
from .models import BomResearchRun, BomLineItem, TeamContact
from .serializers import BomResearchRunSerializer, TeamContactSerializer


# ── Helpers ───────────────────────────────────────────────────────────────────

_STANDARD_QUESTIONS = [
    {
        "id": "production_volume",
        "type": "single_select",
        "text": "What is the expected production volume for this run?",
        "options": ["1–10 units", "50–100 units", "500–1 000 units", "1 000+ units"],
        "default": "50–100 units",
        "context_file": None,
        "matched_contact": None,
    },
    {
        "id": "compliance",
        "type": "multi_select",
        "text": "Which compliance or certification requirements apply?",
        "options": ["RoHS", "REACH", "ISO 9001", "AS9100D", "ITAR", "None"],
        "default": "None",
        "context_file": None,
        "matched_contact": None,
    },
    {
        "id": "budget",
        "type": "text",
        "text": "What is the target unit cost ceiling (USD)? Leave blank to skip.",
        "options": None,
        "default": "",
        "context_file": None,
        "matched_contact": None,
    },
    {
        "id": "preferred_suppliers",
        "type": "text",
        "text": "Any preferred suppliers or geographic regions? (e.g. 'North America only', 'Approved vendor list')",
        "options": None,
        "default": "",
        "context_file": None,
        "matched_contact": None,
    },
]

_MATERIAL_OPTIONS = [
    "6061-T6 Aluminum",
    "7075-T6 Aluminum",
    "ABS Plastic",
    "Polycarbonate",
    "304 Stainless Steel",
    "316 Stainless Steel",
    "4140 Steel",
    "Titanium Grade 5",
    "Other (specify in notes)",
]


def _find_contact_for_tag(user, tag: str):
    """Return first workspace contact whose expertise_tags contain tag (case-insensitive)."""
    for contact in TeamContact.objects.filter(workspace_owner=user, allow_automated=True):
        if tag.lower() in [t.lower() for t in contact.expertise_tags]:
            return TeamContactSerializer(contact).data
    return None


def _build_questions(run: BomResearchRun, user) -> list:
    """Build the full question list for a run."""
    questions = list(_STANDARD_QUESTIONS)  # shallow copy of standard stubs

    # Already-answered question ids
    answered_ids = set(run.inputs_json.keys())

    # Per-file material gap questions
    for item in run.line_items.filter(material_spec="").select_related("file"):
        q_id = f"material_file_{item.file_id or item.id}"
        if q_id in answered_ids:
            continue
        file_name = item.file.original_name if item.file else item.part_name
        questions.append({
            "id": q_id,
            "type": "single_select",
            "text": f'No material spec found for "{file_name}". Which material applies?',
            "options": _MATERIAL_OPTIONS,
            "default": "6061-T6 Aluminum",
            "context_file": file_name,
            "matched_contact": _find_contact_for_tag(user, "materials"),
            "_line_item_id": item.id,  # internal — stripped before response
        })

    # Filter out already-answered standard questions
    return [q for q in questions if q["id"] not in answered_ids]


# ── Views ─────────────────────────────────────────────────────────────────────

class BomRunListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get("project_id")
        runs = BomResearchRun.objects.filter(created_by=request.user).prefetch_related(
            "line_items__quotes"
        )
        if project_id:
            runs = runs.filter(project_id=project_id)
        return Response(BomResearchRunSerializer(runs, many=True).data)

    def post(self, request):
        project_id = request.data.get("project_id")
        if not project_id:
            return Response(
                {"detail": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        project = get_object_or_404(Project, pk=project_id, owner=request.user)
        run = BomResearchRun.objects.create(project=project, created_by=request.user)

        # Auto-scan: create a BomLineItem per extracted part / per file
        files = UploadedFile.objects.filter(project=project, status="processed").prefetch_related("result")
        for f in files:
            try:
                result = f.result.result_json
            except ExtractionResult.DoesNotExist:
                result = None

            parts = []
            if result:
                product_names = (result.get("products") or {}).get("product_names") or []
                parts = product_names

            if parts:
                for part_name in parts:
                    BomLineItem.objects.create(
                        run=run,
                        file=f,
                        part_name=part_name,
                        material_spec=(result or {}).get("appearance", {}).get("materials", [""])[0]
                            if (result or {}).get("appearance", {}).get("materials") else "",
                    )
            else:
                # Fall back to one item per file
                BomLineItem.objects.create(
                    run=run,
                    file=f,
                    part_name=f.original_name,
                )

        # If no processed files, create a placeholder
        if not run.line_items.exists():
            BomLineItem.objects.create(run=run, part_name="(no files processed yet)")

        return Response(BomResearchRunSerializer(run).data, status=status.HTTP_201_CREATED)


class BomRunDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        run = get_object_or_404(BomResearchRun, pk=pk, created_by=request.user)
        return Response(BomResearchRunSerializer(run).data)


class BomRunInputsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        run = get_object_or_404(BomResearchRun, pk=pk, created_by=request.user)
        if run.status not in ("gathering_inputs", "awaiting_team_input"):
            return Response(
                {"detail": f"Run is in '{run.status}' status — inputs cannot be updated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        answers = request.data.get("answers", {})
        if not isinstance(answers, dict):
            return Response(
                {"detail": "answers must be an object."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Merge new answers into existing inputs
        run.inputs_json = {**run.inputs_json, **answers}

        # Apply material answers to line items
        for key, value in answers.items():
            if key.startswith("material_file_"):
                try:
                    suffix = key[len("material_file_"):]
                    # Try file_id first, then line_item id
                    items = run.line_items.filter(file_id=suffix)
                    if not items.exists():
                        items = run.line_items.filter(id=suffix)
                    items.update(material_spec=value)
                except (ValueError, TypeError):
                    pass

        from datetime import datetime, timezone as tz
        run.status = "researching"
        run.research_log = run.research_log + [
            {
                "ts": datetime.now(tz.utc).strftime("%H:%M:%S"),
                "type": "info",
                "message": "Inputs submitted — starting research pipeline",
            }
        ]
        run.save(update_fields=["inputs_json", "status", "research_log"])

        # Start research pipeline in background (#60)
        import threading
        from .research_pipeline import run_bom_research
        threading.Thread(target=run_bom_research, args=(run.pk,), daemon=True).start()

        return Response(BomResearchRunSerializer(run).data)


class BomRunQuestionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        run = get_object_or_404(BomResearchRun, pk=pk, created_by=request.user)
        questions = _build_questions(run, request.user)

        # Strip internal keys before returning
        for q in questions:
            q.pop("_line_item_id", None)

        has_team_contacts = TeamContact.objects.filter(workspace_owner=request.user).exists()

        return Response({
            "run_id": run.id,
            "status": run.status,
            "questions": questions,
            "total": len(questions),
            "has_team_contacts": has_team_contacts,
        })


class BomRunExcelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        run = get_object_or_404(BomResearchRun, pk=pk, created_by=request.user)
        if not run.excel_s3_key:
            return Response(
                {"detail": "Excel report not yet generated."}, status=status.HTTP_404_NOT_FOUND
            )
        from files_api.s3_service import generate_presigned_url, get_s3_object_metadata

        url = generate_presigned_url(run.excel_s3_key, expires=3600)
        metadata = get_s3_object_metadata(run.excel_s3_key)
        generated_at = (
            metadata.get("last_modified").isoformat()
            if metadata.get("last_modified")
            else (run.completed_at.isoformat() if run.completed_at else None)
        )
        filename = run.excel_s3_key.rsplit("/", 1)[-1] if "/" in run.excel_s3_key else run.excel_s3_key
        return Response(
            {
                "url": url,
                "file_size": metadata.get("size"),
                "generated_at": generated_at,
                "filename": filename,
            }
        )


class BomRunLogView(APIView):
    """
    GET /api/bom/runs/<id>/log/?since=HH:MM:SS

    Returns log entries for a run, optionally filtered to only entries whose
    timestamp is strictly after `since`.  Also returns the current run status
    so the frontend knows when to stop polling (status == "completed" | "failed").

    Response:
        {
          "run_id": 42,
          "status": "researching",
          "entries": [
            {"ts": "12:04:01", "type": "search", "message": "..."},
            ...
          ]
        }
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        run = get_object_or_404(BomResearchRun, pk=pk, created_by=request.user)

        since = request.query_params.get("since", "").strip()
        entries = list(run.research_log or [])

        if since:
            entries = [e for e in entries if e.get("ts", "") > since]

        return Response({
            "run_id": run.pk,
            "status": run.status,
            "entries": entries,
        })
