"""Supplier RFQ email loop (SCRUM-33/34/35).

send_rfq           approve + send an RfqDraft from the owner's Gmail; failures are stored, not silent
poll_rfq_replies   check every open RFQ thread for a supplier reply
apply_reply        parse a reply and run the resume-research state machine:
                     quote (confident)  -> part_history Quote, row "sourced"
                     quote (unsure)     -> human review queue
                     decline            -> shortlist re-run excluding that supplier
                     info request       -> flagged for human attention
escalate_silent_rfqs  no reply after settings.RFQ_ESCALATE_AFTER_DAYS -> escalated
simulate_reply     DEMO MODE: inject a canned reply and run the same path
"""

import re
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.jobs import record_failure
from part_history.models import Part, Quote, Supplier

from .gmail_integration import fetch_thread_reply, send_gmail_message
from .models import GmailCredential, RfqDraft

# Below this a parsed quote waits for a person instead of being committed.
AUTO_COMMIT_CONFIDENCE = 0.7
SENDABLE = {"draft", "final", "send_failed"}
OPEN_THREAD = {"sent", "escalated", "info_requested"}


def demo_mode() -> bool:
    return bool(settings.DEBUG or getattr(settings, "ORBIT_DEMO_MODE", False))


# ── Send ─────────────────────────────────────────────────────────────────────

def render_rfq_email(rfq: RfqDraft) -> tuple[str, str]:
    subject = f"RFQ: {rfq.part_number or 'part'} ({rfq.bom_row.bom.reference})"
    lines = [
        f"Hi {rfq.supplier_name or 'there'},",
        "",
        "We'd like a quote for the part below.",
        "",
        f"Part number: {rfq.part_number or '—'}",
    ]
    for field, label in [*RfqDraft.CRITICAL_FIELDS.items(), ("process", "Process")]:
        value = getattr(rfq, field)
        lines.append(f"{label}: {value if value not in (None, '') else 'to be confirmed'}")
    if rfq.notes:
        lines += ["", rfq.notes]
    lines += [
        "",
        "Please reply with unit price, lead time, MOQ and any notes (tooling, validity).",
        "",
        "Thanks",
    ]
    return subject, "\n".join(lines)


def send_rfq(rfq: RfqDraft) -> RfqDraft:
    """Send ``rfq``. Raises ValueError for bad input; Gmail failures are saved on the record and re-raised."""
    if rfq.status not in SENDABLE:
        raise ValueError(f"This RFQ was already sent (status: {rfq.status}).")
    if not rfq.supplier_email:
        raise ValueError("Add the supplier's email before sending.")

    subject, body = render_rfq_email(rfq)
    try:
        if demo_mode() and not GmailCredential.objects.filter(user=rfq.created_by).exists():
            result = {"message_id": f"demo-msg-{uuid.uuid4().hex[:10]}", "thread_id": f"demo-thread-{uuid.uuid4().hex[:10]}"}
        else:
            result = send_gmail_message(rfq.created_by, to=rfq.supplier_email, subject=subject, body=body)
    except Exception as exc:
        rfq.status = "send_failed"
        rfq.send_error = str(exc) or exc.__class__.__name__
        rfq.save(update_fields=["status", "send_error", "updated_at"])
        record_failure("rfq_send", rfq.pk, exc)
        raise

    rfq.status = "sent"
    rfq.send_error = ""
    rfq.sent_at = timezone.now()
    rfq.gmail_message_id = result.get("message_id", "")
    rfq.gmail_thread_id = result.get("thread_id", "")
    rfq.needs_attention = False
    rfq.attention_reason = ""
    rfq.save()
    row = rfq.bom_row
    if row.sourcing_status != "sourced":
        row.sourcing_status = "rfq_sent"
        row.save(update_fields=["sourcing_status"])
    return rfq


# ── Parse ────────────────────────────────────────────────────────────────────

_DECLINE = re.compile(
    r"\b(declin\w*|unable to (quote|bid|support)|can(not|'t) (quote|bid|support|make)|no[- ]bid|"
    r"not able to (quote|bid)|pass on this|no capacity|regret)\b",
    re.I,
)
_INFO = re.compile(
    r"\b(could you (send|share|provide|clarify|confirm)|please (send|share|provide|clarify|confirm)|"
    r"can you (send|share|provide|clarify|confirm)|need (the|a|more) (drawing|step|cad|info\w*|detail\w*)|"
    r"what (is|are) the)\b",
    re.I,
)
_PRICE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)|(\d[\d,]*(?:\.\d+)?)\s?(?:USD|usd)\b")
_LEAD = re.compile(r"(\d+)\s*(?:-\s*\d+\s*)?(business\s+|working\s+|calendar\s+)?(day|week)s?", re.I)
_MOQ = re.compile(r"\b(?:MOQ|minimum order(?: quantity)?|min\.? order)\b[^\d]{0,20}(\d[\d,]*)", re.I)
_NOTES = re.compile(r"^\s*(?:notes?|n\.b\.|tooling|validity|valid)\b[:\s-]*(.+)$", re.I | re.M)


def _num(text: str) -> str:
    return text.replace(",", "")


def parse_supplier_reply(text: str) -> dict:
    """Pull intent, unit price, lead time, MOQ and notes from a reply, with a 0-1 confidence."""
    result = {"intent": "unknown", "unit_price": None, "lead_time_days": None, "moq": None, "notes": "", "confidence": 0.2}
    body = (text or "").strip()
    if not body:
        return result

    prices = [_num(m.group(1) or m.group(2)) for m in _PRICE.finditer(body)]
    lead = next((m for m in _LEAD.finditer(body) if "lead" in body[max(0, m.start() - 40):m.start()].lower()), None)
    lead = lead or next(iter(_LEAD.finditer(body)), None)
    moq = _MOQ.search(body)
    notes = "; ".join(m.group(0).strip() for m in _NOTES.finditer(body))

    if lead:
        days = int(lead.group(1))
        result["lead_time_days"] = days * 7 if lead.group(3).lower() == "week" else days
    if moq:
        result["moq"] = int(_num(moq.group(1)))
    result["notes"] = notes[:500]

    if _DECLINE.search(body) and not prices:
        result.update(intent="decline", confidence=0.9)
        return result
    if prices:
        result["unit_price"] = prices[0]
        found = 1 + (result["lead_time_days"] is not None) + (result["moq"] is not None)
        confidence = {1: 0.5, 2: 0.75, 3: 0.9}[found]
        if len(set(prices)) > 1:
            # Price breaks or several figures: a person should pick the right one.
            confidence = min(confidence, 0.5)
            result["notes"] = (result["notes"] + "; " if result["notes"] else "") + f"Several prices quoted: {', '.join(prices)}"
        result.update(intent="quote", confidence=confidence)
        return result
    if _INFO.search(body) or "?" in body:
        result.update(intent="info_request", confidence=0.8)
        return result
    return result


# ── State machine ────────────────────────────────────────────────────────────

def _excluded_shortlist(rfq: RfqDraft) -> list[dict]:
    from part_history.shortlist import shortlist_row

    excluded = {name.lower() for name in rfq.excluded_suppliers}
    picks = shortlist_row(rfq.created_by, rfq.bom_row, k=10)["suppliers"]
    return [
        {"supplier": p["supplier"], "supplier_id": p["supplier_id"], "best_quote": p["best_quote"]}
        for p in picks
        if p["supplier"].lower() not in excluded
    ][:3]


@transaction.atomic
def commit_quote(rfq: RfqDraft, parsed: dict) -> Quote:
    """Write the parsed reply to part_history as a Quote and mark the BOM line sourced."""
    try:
        unit_price = Decimal(str(parsed.get("unit_price")))
    except (InvalidOperation, TypeError):
        raise ValueError("A unit price is needed to accept this quote.")
    owner = rfq.created_by
    supplier, _ = Supplier.objects.get_or_create(
        workspace_owner=owner,
        name=rfq.supplier_name or rfq.supplier_email,
        defaults={"contact_email": rfq.supplier_email},
    )
    part = None
    if rfq.part_number:
        part, _ = Part.objects.get_or_create(
            workspace_owner=owner,
            part_number=rfq.part_number,
            defaults={"description": rfq.part_context[:500], "material": rfq.material, "process": rfq.process},
        )
    lead = parsed.get("lead_time_days")
    quote = Quote.objects.create(
        workspace_owner=owner,
        supplier=supplier,
        part=part,
        material=rfq.material,
        tolerance=rfq.tolerance[:100],
        unit_price=unit_price,
        quantity=parsed.get("moq") or rfq.quantity,
        lead_time_days=int(lead) if lead not in (None, "") else None,
        source=f"RFQ #{rfq.pk} email thread {rfq.gmail_thread_id}"[:300],
    )
    rfq.parsed_reply = {**rfq.parsed_reply, **parsed}
    rfq.quote = quote
    rfq.status = "quoted"
    rfq.needs_attention = False
    rfq.attention_reason = ""
    rfq.save()
    rfq.bom_row.sourcing_status = "sourced"
    rfq.bom_row.save(update_fields=["sourcing_status"])
    return quote


def apply_reply(rfq: RfqDraft, text: str, message_id: str = "") -> RfqDraft:
    parsed = parse_supplier_reply(text)
    rfq.reply_text = text
    rfq.replied_at = timezone.now()
    rfq.gmail_reply_message_id = message_id
    rfq.parsed_reply = parsed
    rfq.needs_attention = False
    rfq.attention_reason = ""

    intent = parsed["intent"]
    if intent == "quote" and parsed["confidence"] >= AUTO_COMMIT_CONFIDENCE:
        rfq.save()
        commit_quote(rfq, parsed)
        return rfq
    if intent == "decline":
        name = rfq.supplier_name or rfq.supplier_email
        if name and name not in rfq.excluded_suppliers:
            rfq.excluded_suppliers = [*rfq.excluded_suppliers, name]
        rfq.status = "declined"
        rfq.next_suppliers = _excluded_shortlist(rfq)
        if rfq.bom_row.sourcing_status != "sourced":
            rfq.bom_row.sourcing_status = ""
            rfq.bom_row.save(update_fields=["sourcing_status"])
    elif intent == "info_request":
        rfq.status = "info_requested"
        rfq.needs_attention = True
        rfq.attention_reason = "Supplier asked for more information — reply in Gmail."
    else:
        rfq.status = "needs_review"
    rfq.save()
    return rfq


def review_rfq(rfq: RfqDraft, action: str, overrides: dict | None = None) -> RfqDraft:
    """Accept (optionally correcting fields) or reject a low-confidence parse."""
    if rfq.status != "needs_review":
        raise ValueError("Only replies waiting for review can be accepted or rejected.")
    if action == "accept":
        fields = {k: v for k, v in (overrides or {}).items() if k in {"unit_price", "lead_time_days", "moq", "notes"}}
        commit_quote(rfq, {**rfq.parsed_reply, **fields, "reviewed": True})
    elif action == "reject":
        rfq.status = "sent"
        rfq.needs_attention = True
        rfq.attention_reason = "Parsed reply rejected — read the thread and follow up by hand."
        rfq.save()
    else:
        raise ValueError("action must be 'accept' or 'reject'.")
    return rfq


# ── Polling, escalation, demo ────────────────────────────────────────────────

def poll_rfq_replies(user=None) -> list[int]:
    """Check open RFQ threads for new supplier replies. One failure never stops the rest."""
    rfqs = RfqDraft.objects.filter(status__in=OPEN_THREAD).exclude(gmail_thread_id="").select_related("bom_row__bom")
    if user is not None:
        rfqs = rfqs.filter(created_by=user)
    replied = []
    for rfq in rfqs:
        if rfq.gmail_thread_id.startswith("demo-"):
            continue
        try:
            reply = fetch_thread_reply(
                rfq.created_by,
                thread_id=rfq.gmail_thread_id,
                sender_email=rfq.supplier_email,
                skip_ids={rfq.gmail_message_id, rfq.gmail_reply_message_id},
            )
        except Exception as exc:
            record_failure("rfq_poll", rfq.pk, exc)
            continue
        rfq.last_checked_at = timezone.now()
        rfq.save(update_fields=["last_checked_at"])
        if reply:
            apply_reply(rfq, reply["text"], reply["id"])
            replied.append(rfq.pk)
    return replied


def escalate_silent_rfqs(now=None) -> list[int]:
    days = getattr(settings, "RFQ_ESCALATE_AFTER_DAYS", 5)
    cutoff = (now or timezone.now()) - timedelta(days=days)
    escalated = []
    for rfq in RfqDraft.objects.filter(status="sent", sent_at__lt=cutoff, replied_at__isnull=True):
        rfq.status = "escalated"
        rfq.needs_attention = True
        rfq.attention_reason = f"No reply after {days} days — chase the supplier or pick another."
        rfq.save()
        escalated.append(rfq.pk)
    return escalated


CANNED_REPLIES = {
    "quote": "Hi,\n\nThanks for the RFQ. Unit price $4.85 each.\nLead time: 3 weeks ARO.\nMOQ: 500 pcs.\nNotes: tooling included, quote valid 30 days.\n\nBest regards",
    "unclear": "Hi,\n\nWe can do $5.10 at 500 pcs or $4.40 at 2,000 pcs. Let us know which volume.\n\nRegards",
    "decline": "Hello,\n\nUnfortunately we have to decline this one — no capacity on our 5-axis cells this quarter.\n\nSorry",
    "info": "Hi,\n\nCould you send the STEP file and confirm the tolerance on the bore? We'll quote once we have it.\n\nThanks",
}


def simulate_reply(rfq: RfqDraft, kind: str) -> RfqDraft:
    if not demo_mode():
        raise PermissionError("Simulated replies are only available in demo mode.")
    if kind not in CANNED_REPLIES:
        raise ValueError(f"kind must be one of: {', '.join(CANNED_REPLIES)}.")
    if rfq.status not in OPEN_THREAD:
        raise ValueError("Send the RFQ first — replies can only land on a sent thread.")
    return apply_reply(rfq, CANNED_REPLIES[kind], f"demo-reply-{uuid.uuid4().hex[:10]}")
