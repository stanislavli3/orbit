"""SCRUM-17/33/34/35: RFQ Gmail send, reply parsing, review queue, resume-research loop.

Gmail is always mocked; nothing here touches the network.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from bom_agent import rfq_loop
from bom_agent.gmail_integration import upsert_gmail_credential
from bom_agent.models import Bom, BomRow, RfqDraft
from part_history.models import Quote, Supplier
from projects.models import Project


@pytest.fixture
def rfq(db, user):
    project = Project.objects.create(name="P", owner=user)
    bom = Bom.objects.create(project=project, status="approved")
    row = BomRow.objects.create(bom=bom, line_no=1, part_number="BRK-1", material="6061-T6 aluminum")
    return RfqDraft.objects.create(
        bom_row=row, created_by=user, part_number="BRK-1", material="6061-T6 aluminum",
        quantity=500, supplier_name="Acme Machining", supplier_email="quotes@acme.test",
    )


@pytest.fixture
def gmail(user):
    upsert_gmail_credential(user=user, gmail_address="me@gmail.com", access_token="tok",
                            token_expires_at=timezone.now() + timedelta(hours=1))


SENT = {"id": "m1", "threadId": "t1"}


# ── Send (SCRUM-17/33) ───────────────────────────────────────────────────────

def test_send_posts_to_gmail_and_stores_ids(auth_client, rfq, gmail):
    with patch("bom_agent.gmail_integration._gmail_request", return_value=SENT) as req:
        res = auth_client.post(f"/api/bom/rfqs/{rfq.pk}/send/")
    assert res.status_code == 200
    method, path, token, payload = req.call_args.args
    assert (method, path, token) == ("POST", "/messages/send", "tok")
    assert payload["raw"]
    rfq.refresh_from_db()
    assert (rfq.status, rfq.gmail_message_id, rfq.gmail_thread_id) == ("sent", "m1", "t1")
    assert rfq.bom_row.sourcing_status == "rfq_sent"


def test_send_failure_is_visible_not_silent(auth_client, rfq, gmail):
    with patch("bom_agent.gmail_integration._gmail_request", side_effect=RuntimeError("Gmail API error (401)")):
        res = auth_client.post(f"/api/bom/rfqs/{rfq.pk}/send/")
    assert res.status_code == 502
    assert res.json()["rfq"]["status"] == "send_failed"
    rfq.refresh_from_db()
    assert "401" in rfq.send_error


@override_settings(ORBIT_DEMO_MODE=False, DEBUG=False)
def test_send_without_gmail_fails_visibly(auth_client, rfq):
    res = auth_client.post(f"/api/bom/rfqs/{rfq.pk}/send/")
    assert res.status_code == 502
    rfq.refresh_from_db()
    assert rfq.status == "send_failed" and "No Gmail credential" in rfq.send_error


def test_send_requires_supplier_email(auth_client, rfq):
    rfq.supplier_email = ""
    rfq.save()
    assert auth_client.post(f"/api/bom/rfqs/{rfq.pk}/send/").status_code == 400


@override_settings(ORBIT_DEMO_MODE=True)
def test_demo_mode_sends_without_gmail(auth_client, rfq):
    assert auth_client.post(f"/api/bom/rfqs/{rfq.pk}/send/").status_code == 200
    rfq.refresh_from_db()
    assert rfq.status == "sent" and rfq.gmail_thread_id.startswith("demo-thread-")


# ── Parsing (SCRUM-34) ───────────────────────────────────────────────────────

def test_parse_clean_quote():
    parsed = rfq_loop.parse_supplier_reply(rfq_loop.CANNED_REPLIES["quote"])
    assert parsed["intent"] == "quote"
    assert (parsed["unit_price"], parsed["lead_time_days"], parsed["moq"]) == ("4.85", 21, 500)
    assert "tooling" in parsed["notes"]
    assert parsed["confidence"] >= rfq_loop.AUTO_COMMIT_CONFIDENCE


def test_parse_price_breaks_are_low_confidence():
    parsed = rfq_loop.parse_supplier_reply(rfq_loop.CANNED_REPLIES["unclear"])
    assert parsed["intent"] == "quote" and parsed["confidence"] < rfq_loop.AUTO_COMMIT_CONFIDENCE


def test_parse_decline_and_info():
    assert rfq_loop.parse_supplier_reply(rfq_loop.CANNED_REPLIES["decline"])["intent"] == "decline"
    assert rfq_loop.parse_supplier_reply(rfq_loop.CANNED_REPLIES["info"])["intent"] == "info_request"


# ── Polling + state machine (SCRUM-34/35) ────────────────────────────────────

def _sent(rfq):
    rfq.status, rfq.gmail_thread_id, rfq.gmail_message_id, rfq.sent_at = "sent", "t1", "m1", timezone.now()
    rfq.save()
    return rfq


def test_poll_command_commits_confident_quote(rfq, gmail):
    _sent(rfq)
    reply = {"id": "r1", "text": rfq_loop.CANNED_REPLIES["quote"]}
    with patch("bom_agent.rfq_loop.fetch_thread_reply", return_value=reply):
        call_command("poll_rfq_replies")
    rfq.refresh_from_db()
    assert rfq.status == "quoted" and rfq.bom_row.sourcing_status == "sourced"
    quote = Quote.objects.get()
    assert str(quote.unit_price) == "4.8500" and quote.lead_time_days == 21
    assert "t1" in quote.source and quote.supplier.name == "Acme Machining"


def test_poll_reads_gmail_thread(rfq, gmail):
    _sent(rfq)
    import base64
    data = base64.urlsafe_b64encode(rfq_loop.CANNED_REPLIES["quote"].encode()).decode()
    thread = {"messages": [
        {"id": "m1", "payload": {"headers": [{"name": "From", "value": "me@gmail.com"}]}},
        {"id": "r1", "payload": {"mimeType": "text/plain", "body": {"data": data},
                                 "headers": [{"name": "From", "value": "Acme <quotes@acme.test>"}]}},
    ]}
    with patch("bom_agent.gmail_integration._gmail_request", return_value=thread):
        assert rfq_loop.poll_rfq_replies() == [rfq.pk]
    rfq.refresh_from_db()
    assert rfq.gmail_reply_message_id == "r1" and rfq.status == "quoted"


def test_low_confidence_goes_to_review_then_accept(auth_client, rfq):
    _sent(rfq)
    rfq_loop.apply_reply(rfq, rfq_loop.CANNED_REPLIES["unclear"])
    assert rfq.status == "needs_review" and not Quote.objects.exists()
    queue = auth_client.get("/api/bom/rfqs/?status=needs_review").json()
    assert [r["id"] for r in queue] == [rfq.pk]
    res = auth_client.post(f"/api/bom/rfqs/{rfq.pk}/review/", {"action": "accept", "unit_price": "4.40", "moq": 2000}, format="json")
    assert res.status_code == 200 and res.json()["status"] == "quoted"
    assert str(Quote.objects.get().unit_price) == "4.4000"


def test_review_reject_flags_for_human(auth_client, rfq):
    _sent(rfq)
    rfq_loop.apply_reply(rfq, rfq_loop.CANNED_REPLIES["unclear"])
    res = auth_client.post(f"/api/bom/rfqs/{rfq.pk}/review/", {"action": "reject"}, format="json")
    assert res.json()["needs_attention"] is True and not Quote.objects.exists()


def test_decline_reruns_shortlist_excluding_supplier(rfq, user):
    from part_history.models import Part
    part = Part.objects.create(workspace_owner=user, part_number="BRK-1")
    for name in ("Acme Machining", "Beta Works"):
        s = Supplier.objects.create(workspace_owner=user, name=name, is_approved=True)
        Quote.objects.create(workspace_owner=user, supplier=s, part=part, unit_price=5, source="seed")
    _sent(rfq)
    rfq_loop.apply_reply(rfq, rfq_loop.CANNED_REPLIES["decline"])
    assert rfq.status == "declined" and rfq.excluded_suppliers == ["Acme Machining"]
    assert [s["supplier"] for s in rfq.next_suppliers] == ["Beta Works"]


def test_info_request_flags_attention(rfq):
    _sent(rfq)
    rfq_loop.apply_reply(rfq, rfq_loop.CANNED_REPLIES["info"])
    assert rfq.status == "info_requested" and rfq.needs_attention


@override_settings(RFQ_ESCALATE_AFTER_DAYS=3)
def test_silent_thread_escalates(rfq):
    _sent(rfq)
    RfqDraft.objects.filter(pk=rfq.pk).update(sent_at=timezone.now() - timedelta(days=4))
    assert rfq_loop.escalate_silent_rfqs() == [rfq.pk]
    rfq.refresh_from_db()
    assert rfq.status == "escalated" and "3 days" in rfq.attention_reason


# ── Demo mode ────────────────────────────────────────────────────────────────

@override_settings(ORBIT_DEMO_MODE=True)
def test_simulate_reply_runs_same_path(auth_client, rfq):
    auth_client.post(f"/api/bom/rfqs/{rfq.pk}/send/")
    res = auth_client.post(f"/api/bom/rfqs/{rfq.pk}/simulate-reply/", {"kind": "quote"}, format="json")
    assert res.status_code == 200 and res.json()["status"] == "quoted"
    assert res.json()["row_sourcing_status"] == "sourced"


@override_settings(ORBIT_DEMO_MODE=False, DEBUG=False)
def test_simulate_reply_hidden_outside_demo(auth_client, rfq):
    _sent(rfq)
    assert auth_client.post(f"/api/bom/rfqs/{rfq.pk}/simulate-reply/", {"kind": "quote"}, format="json").status_code == 404
