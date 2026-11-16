# Orbit data isolation and no-training policy (SCRUM-63)

This describes what Orbit **actually does today**, verified against the code on `main`,
and lists what is **not yet in place**. It is a working policy for a pilot, not a legal
contract. Update it whenever the behaviour below changes.

## 1. Who can see what (isolation)

- **Authentication**: every API request is authenticated with a Clerk-issued JWT
  (`backend/accounts/clerk_auth.py`); views use DRF `IsAuthenticated`.
- **Scoping is per user**. There is no shared "organization" tenant yet; each user's
  data is their own workspace:
  - Projects are filtered by `owner=request.user` (`projects/views.py`).
  - Files, extraction results and downloads are looked up with
    `project__owner=request.user` (`files_api/views.py`); BOMs and estimates likewise
    (`part_history/views.py`, `bom_agent/*`).
  - Part history, suppliers, quotes, cost imports and workspace sources are filtered by
    `workspace_owner=request.user` (`part_history/`).
  - Assistant chats belong to the user (`assistant/models.py: ChatSession.user`) and the
    assistant's retrieval only searches that user's files (`assistant/rag.py`).
  - Another user's object returns **404**, not 403, so IDs don't leak existence
    (covered by tests, e.g. `part_history/test_sources.py`).
- **Design review** sharing is the one place where data is deliberately visible to
  other users, and only to members explicitly added to a review (`design_review/`).

## 2. Where data is stored

| Data | Where |
| --- | --- |
| Uploaded files (STEP, PDF, ...) and generated Excel exports | **S3-compatible object storage** bucket `AWS_STORAGE_BUCKET_NAME` (`files_api/s3_service.py`). Downloads use presigned URLs valid for **1 hour**. |
| Metadata, extracted BOMs, costs, chats, quotes | The application database (Postgres in deployment, SQLite locally). |
| Search index for the assistant | A local hashed TF-IDF vector per file in the DB (`files_api/embeddings.py`). **No external embedding service is called.** |
| Gmail OAuth tokens (if a user connects Gmail) | DB, encrypted with Fernet using `GMAIL_TOKEN_ENCRYPTION_KEY` (`bom_agent/gmail_integration.py`). |

Encryption at rest for the bucket and database depends on the hosting configuration
(e.g. S3 default encryption) — **verify per deployment**; the code does not set it itself.

## 3. Which AI providers are called, with what data

Orbit calls **one** AI provider: **Anthropic (Claude API)**, using `ANTHROPIC_API_KEY`.
If the key is not set those features degrade gracefully; nothing is sent.

| Feature | Code | Data sent to Anthropic |
| --- | --- | --- |
| File description | `files_api/ai_description.py` | File name, type and **metadata parsed from the file header** (schema, units, part info) — not the raw file |
| Assistant chat | `assistant/views.py` | The user's message, recent chat history, and extracted text/metadata of the **user's own** most relevant files |
| BOM research agent | `bom_agent/research_pipeline.py` | BOM line items (part names, numbers, materials, specs). Uses Anthropic's hosted **web search tool**, so search queries derived from those items go to the public web via Anthropic |
| Team-request drafting | `bom_agent/team_requests.py` | The missing-spec question and line-item context |

Other outbound services: **Gmail API** (only if the user connects Gmail; sends emails
they approve from their own account) and **Clerk** (sign-in).

### No training on customer data

Orbit does not train or fine-tune any model on customer data. Orbit uses the Anthropic
API under Anthropic's commercial terms; **per Anthropic's commercial terms, Anthropic
does not train its models on API inputs or outputs by default — verify the current terms
and retention period before quoting this to a customer.** API inputs/outputs may be
retained by Anthropic for a limited period for trust & safety; zero-data-retention is a
separate arrangement Orbit does not currently have.

## 4. Retention and deletion

- **No automatic expiry**: data is kept until the user deletes it.
- **Delete a file**: removes the DB row (and its extraction result and embedding via
  cascade) and **deletes the object from S3** (best-effort; S3 errors are ignored)
  (`files_api/views.py: FileDeleteView`).
- **Delete a project**: deletes its S3 objects and cascades to its files, BOMs, results
  and chats (`projects/views.py: perform_destroy`).
- **Cost imports**: the model cascades an import's costs when the import is deleted, but there is no delete endpoint in the UI/API yet (admin only).
- **Disconnect Gmail**: deletes the stored tokens.
- **Delete a workspace source**: removes the setting only, not data already imported.
- Deleting a user cascades to everything they own in the DB (`on_delete=CASCADE`).

## 5. Not yet in place (be explicit with customers)

- No organization/team tenancy or role-based access beyond owner + design-review members.
- No self-serve "delete my account and all data" button; done by an admin today.
- No audit log of reads/downloads (only exports are logged, via `projects.ExportLog`, plus the design-change approval trail).
- No configurable retention period or automatic purge; no purge of S3 objects that a
  failed delete left behind.
- No customer-managed encryption keys; no data-residency choice.
- No zero-data-retention agreement with the AI provider; web search in the research agent
  cannot be switched off per workspace yet.
- No SOC 2 / ISO 27001 certification.
- Backups (DB snapshots, S3 versioning) depend on hosting setup and may keep deleted data
  for their own retention window.
