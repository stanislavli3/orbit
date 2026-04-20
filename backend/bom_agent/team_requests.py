import json
import os
import threading
from datetime import timedelta

import anthropic
from django.utils import timezone

from .models import BomLineItem, TeamContact, TeamRequest


_CLIENT: anthropic.Anthropic | None = None


def _client() -> anthropic.Anthropic:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    return _CLIENT


def _question_tag(question: dict) -> str:
    question_id = question.get("id", "").lower()
    text = question.get("text", "").lower()

    if question_id.startswith("material_file_") or "material" in text:
        return "materials"
    if "compliance" in question_id or "certification" in text or "rohs" in text:
        return "compliance"
    if "budget" in question_id or "cost" in text or "supplier" in text:
        return "procurement"
    if "timeline" in question_id or "production" in question_id or "volume" in question_id:
        return "program"
    return "general"


def route_contact(user, question: dict) -> TeamContact | None:
    contacts = list(
        TeamContact.objects.filter(
            workspace_owner=user,
            allow_automated=True,
        ).order_by("full_name")
    )
    if not contacts:
        return None

    matched_contact = question.get("matched_contact") or {}
    matched_id = matched_contact.get("id")
    if matched_id:
        for contact in contacts:
            if contact.id == matched_id:
                return contact

    tag = _question_tag(question)
    for contact in contacts:
        tags = [value.lower() for value in contact.expertise_tags]
        if tag in tags:
            return contact

    for contact in contacts:
        haystack = " ".join(
            [
                contact.role.lower(),
                contact.department.lower(),
                " ".join(value.lower() for value in contact.expertise_tags),
            ]
        )
        if tag in haystack:
            return contact

    return contacts[0]


def item_context(run, question: dict) -> tuple[list[str], list[str], list[str]]:
    line_item_id = question.get("_line_item_id")
    known: list[str] = []
    unknown: list[str] = [question.get("text", "").strip()]

    if line_item_id:
        try:
            item = run.line_items.prefetch_related("quotes").get(pk=line_item_id)
        except Exception:
            item = None
        if item:
            parts = [item.part_name]
            if item.material_spec:
                known.append(f"Current material note: {item.material_spec}")
            if item.quotes.exists():
                known.append(
                    f"{item.quotes.count()} supplier quote(s) already captured"
                )
            return parts, known, unknown

    parts = [
        item.part_name
        for item in run.line_items.exclude(part_name="(no files processed yet)")[:5]
    ]
    known_inputs = []
    for key, value in (run.inputs_json or {}).items():
        if value in ("", None, [], {}):
            continue
        known_inputs.append(f"{key.replace('_', ' ')}: {value}")
    known.extend(known_inputs[:4])
    return parts, known, unknown


def fallback_email_render(run, contact: TeamContact, question: dict, is_follow_up: bool) -> tuple[str, str]:
    project_name = run.project.name
    reply_by = (timezone.now() + timedelta(days=3)).date().isoformat()
    part_names, known_points, unknown_points = item_context(run, question)
    part_line = ", ".join(part_names) if part_names else "the BOM research items"
    subject_prefix = "Follow-up: " if is_follow_up else ""
    subject = f"{subject_prefix}Orbit BOM question for {project_name}"

    known_block = "\n".join(f"- {value}" for value in known_points) if known_points else "- We have the current project context and BOM research run details."
    unknown_block = "\n".join(f"- {value}" for value in unknown_points) if unknown_points else "- We need clarification on this BOM research item."

    opening = (
        f"Hi {contact.full_name.split(' ')[0]},\n\n"
        f"I'm following up on a BOM research question for {project_name}."
        if is_follow_up
        else f"Hi {contact.full_name.split(' ')[0]},\n\nOrbit's BOM research agent needs your input for {project_name}."
    )
    body = (
        f"{opening}\n\n"
        f"This request relates to: {part_line}.\n\n"
        "What we already know:\n"
        f"{known_block}\n\n"
        "What we still need from you:\n"
        f"{unknown_block}\n\n"
        f"Could you reply by {reply_by}? A short reply is fine.\n\n"
        "Thanks,\n"
        "Orbit BOM Research Agent"
    )
    return subject, body


def render_email_draft(run, contact: TeamContact, question: dict, is_follow_up: bool = False) -> tuple[str, str]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return fallback_email_render(run, contact, question, is_follow_up)

    reply_by = (timezone.now() + timedelta(days=3)).date().isoformat()
    part_names, known_points, unknown_points = item_context(run, question)
    prompt = f"""Render a concise, professional email as JSON with keys "subject" and "body".

Recipient: {contact.full_name} <{contact.email}>
Project: {run.project.name}
Question: {question.get("text", "")}
Relevant parts: {", ".join(part_names) if part_names else "General BOM run"}
Known points: {json.dumps(known_points, ensure_ascii=False)}
Unknown points: {json.dumps(unknown_points, ensure_ascii=False)}
Reply-by date: {reply_by}
Follow-up: {"yes" if is_follow_up else "no"}

Requirements:
- Personalized but concise
- Mention the project name
- Mention the specific part names when available
- Separate what is known vs unknown
- Ask for a reply by the given date
- Plain email prose, no markdown
- Return valid JSON only
"""

    try:
        response = _client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        payload = json.loads(response.content[0].text.strip())
        subject = str(payload.get("subject", "")).strip()
        body = str(payload.get("body", "")).strip()
        if subject and body:
            return subject, body
    except Exception:
        pass

    return fallback_email_render(run, contact, question, is_follow_up)


def get_follow_up_total_for_contact(run, recipient_email: str) -> int:
    return sum(
        run.team_requests.filter(recipient_email=recipient_email).values_list(
            "follow_up_count", flat=True
        )
    )


def parse_reply_answer(team_request: TeamRequest, reply_text: str):
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    question_key = team_request.question_key or ""

    if api_key:
        prompt = f"""Extract the actionable answer from this team email reply as JSON.

Question key: {question_key}
Question: {team_request.question}
Raw reply:
{reply_text}

Return JSON with:
- answer_type: one of "text", "single_select", "multi_select"
- value: string or array of strings
- summary: short sentence
"""
        try:
            response = _client().messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            payload = json.loads(response.content[0].text.strip())
            if "value" in payload:
                return payload
        except Exception:
            pass

    value: str | list[str]
    if question_key == "compliance":
        raw = [part.strip() for part in reply_text.replace("\n", ",").split(",") if part.strip()]
        value = raw or ["None"]
        answer_type = "multi_select"
    else:
        value = reply_text.strip().splitlines()[0].strip() if reply_text.strip() else ""
        answer_type = "text"
    return {
        "answer_type": answer_type,
        "value": value,
        "summary": f"Parsed reply for {team_request.recipient_name}.",
    }


def apply_parsed_answer(team_request: TeamRequest, parsed: dict) -> dict:
    run = team_request.run
    question_key = team_request.question_key or ""
    raw_value = parsed.get("value", "")
    value = raw_value
    if isinstance(raw_value, list):
        value = [str(item).strip() for item in raw_value if str(item).strip()]
    elif raw_value is not None:
        value = str(raw_value).strip()

    updated_fields: dict = {"run_inputs": {}, "line_items": []}
    if question_key.startswith("material_file_"):
        line_item = team_request.line_item
        if line_item and isinstance(value, str):
            BomLineItem.objects.filter(pk=line_item.pk).update(
                material_spec=value,
                status="pending",
            )
            run.inputs_json = {**run.inputs_json, question_key: value}
            run.save(update_fields=["inputs_json"])
            updated_fields["run_inputs"][question_key] = value
            updated_fields["line_items"].append(line_item.pk)
    elif question_key:
        run.inputs_json = {**run.inputs_json, question_key: value}
        run.save(update_fields=["inputs_json"])
        updated_fields["run_inputs"][question_key] = value
    return updated_fields


def maybe_resume_research(run, message: str | None = None) -> bool:
    open_statuses = ["draft", "approved", "sent", "follow_up"]
    if run.team_requests.filter(status__in=open_statuses).exists():
        return False

    if run.status not in {"awaiting_team_input", "researching"}:
        run.status = "researching"
        run.save(update_fields=["status"])

    if message:
        log_entries = list(run.research_log or [])
        log_entries.append(
            {
                "ts": timezone.now().strftime("%H:%M:%S"),
                "type": "info",
                "message": message,
            }
        )
        run.research_log = log_entries
        run.save(update_fields=["research_log"])

    from .research_pipeline import run_bom_research

    threading.Thread(target=run_bom_research, args=(run.pk,), daemon=True).start()
    return True
