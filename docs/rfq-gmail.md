# RFQ email loop (SCRUM-17/33/34/35)

Send an RFQ to a supplier from your own Gmail, pick up the reply, and act on it.

## Setup (real Gmail)

1. Google Cloud console: create an OAuth client (type "Web application"), enable the Gmail API,
   and add the redirect URI `https://<backend-host>/api/team/gmail/oauth/callback/`.
2. Backend env vars:
   - `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`
   - `GMAIL_OAUTH_REDIRECT_URI` — the exact URI registered above (needed behind a TLS proxy)
   - `GMAIL_TOKEN_ENCRYPTION_KEY` — any long secret; tokens are stored Fernet-encrypted with it
     (falls back to `SECRET_KEY`)
3. In the app: **Settings → Gmail BOM Sender → Connect Gmail**, approve the `gmail.send` and
   `gmail.readonly` scopes. You return to Settings with "Gmail connected".

## Demo path

1. Open a structured BOM (BOM review page), click **Draft RFQ** on a row.
2. Fill **Supplier** and **Supplier email**, **Save draft**.
3. **Approve & send from Gmail**. Message/thread ids are stored on the RFQ. A Gmail error
   (expired token, not connected) shows a red "Send failed" state with the reason and a
   **Retry send** button; the failure is also recorded in admin → Job failures.
4. Replies: **Check for replies** (RFQ list) polls Gmail now; otherwise the scheduled poll does.
   - Clear quote (price + lead time + MOQ) → written to Part history as a Quote
     (source `RFQ #<id> email thread <thread id>`), line marked **sourced**.
   - Unclear quote (e.g. several price breaks) → **Supplier replies to review** queue at the top
     of the BOM page; correct the numbers and **Accept**, or **Reject** (flags for a human).
   - Decline → supplier excluded; the approved-supplier shortlist is re-run without it and the
     next suppliers are shown.
   - Info request → flagged for human attention.
   - No reply after `RFQ_ESCALATE_AFTER_DAYS` (default 5) → **Escalated**.

## Demo mode (no Gmail needed)

On when `DEBUG=True` or `ORBIT_DEMO_MODE=True`. Then:
- If the user has no Gmail connected, **Approve & send** records a fake `demo-thread-…` instead
  of failing. With Gmail connected it still sends for real.
- A **Simulate supplier reply** control (clear quote / unclear / decline / info) appears on sent
  RFQs. It injects a canned reply and runs the same parser and state machine.
The simulate endpoint returns 404 outside demo mode.

## Polling schedule

- Celery beat: `celery -A config beat` runs `bom_agent.tasks.poll_rfq_replies_task` every
  `RFQ_POLL_MINUTES` (default 15). It polls open threads and escalates silent ones.
- Without beat, cron the management command instead, e.g. every 15 minutes:
  `*/15 * * * * cd backend && python manage.py poll_rfq_replies`

## API

| Method | Path | |
|---|---|---|
| GET | `/api/bom/rfqs/?bom=<id>&status=<status>` | list (review queue = `status=needs_review`) |
| POST | `/api/bom/rfqs/<id>/send/` | approve and send |
| POST | `/api/bom/rfqs/poll/` | poll now + escalate |
| POST | `/api/bom/rfqs/<id>/review/` | `{action: accept|reject, unit_price?, lead_time_days?, moq?}` |
| POST | `/api/bom/rfqs/<id>/simulate-reply/` | demo only, `{kind: quote|unclear|decline|info}` |
