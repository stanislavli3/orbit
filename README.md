# Orbit

**Mechanical drawings → sourced bills of materials.**

Drop in a CAD file. Claude reads it, agents source the parts, you get an Excel workbook.

<p align="center">
  <a href="https://drive.google.com/file/d/1D1ydU3BGLnS3GhlJLaoC5w--PERf39uv/view?usp=sharing">
  <img src="Accelerate%20Expertise.svg" alt="Orbit — Accelerate Expertise" width="100%">
</p>


<p align="center">
  <a href="https://drive.google.com/file/d/1D1ydU3BGLnS3GhlJLaoC5w--PERf39uv/view?usp=sharing"><b>▶ Watch the demo</b></a> — opens in Google Drive preview.
</p>

---

## How it works

1. **Ingest.** Files land in S3 via signed upload — `.step`, `.stp`, `.pdf`, `.dwg`, `.dxf`, `.iges`, `.igs` up to 100 MB.
2. **Extract.** A pure-Python STEP / drawing parser pulls headers, units, and geometry hints. No native CAD runtime required.
3. **Describe.** Claude Haiku generates a plain-English summary; embeddings index the file for semantic search.
4. **Act.** The BOM agent assembles the bill, runs a research pipeline against suppliers, drafts outreach via Gmail, and renders the result to an Excel workbook.

Hours of manual sourcing, done in minutes.

---

## Stack

| Layer    | Tech                                                       |
| -------- | ---------------------------------------------------------- |
| Frontend | React 18, TypeScript, Vite, Tailwind, MUI + Radix          |
| Backend  | Django 5, Django REST Framework, Python 3.11               |
| Auth     | Clerk (Google OAuth, magic link)                           |
| Storage  | AWS S3 (LocalStack v3 in dev)                              |
| Jobs     | Celery + Redis — extraction, BOM research, library ingest  |
| AI       | Anthropic Claude — Haiku for descriptions, Sonnet for agents |
| Database | SQLite in dev, PostgreSQL in prod                          |

---

## Quick start

```bash
git clone https://github.com/stanislavli3/orbit.git
cd orbit
make setup        # venv, pip, npm, env scaffolding
# fill in backend/.env and apps/web/.env (see below)
make dev          # LocalStack + Redis + backend + worker + frontend, one command
```

Open **http://localhost:5173**.

### Prerequisites

| Tool              | Version  |
| ----------------- | -------- |
| Python            | 3.11+    |
| Node              | 18+      |
| Docker Desktop    | latest   |
| Clerk account     | free tier — [clerk.com](https://clerk.com) |
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) |

---

## Environment

### `backend/.env`

```env
SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(50))">
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

CLERK_JWT_KEY=-----BEGIN PUBLIC KEY-----\nMIIB...\n-----END PUBLIC KEY-----
CLERK_ISSUER=https://your-app.clerk.accounts.dev

CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174

AWS_S3_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_S3_REGION_NAME=us-east-1
AWS_STORAGE_BUCKET_NAME=orbit-local

ANTHROPIC_API_KEY=sk-ant-...

CELERY_BROKER_URL=redis://localhost:6379/0
```

> Clerk: Dashboard → API Keys → JWT public key. Paste the full PEM on one line, escape newlines as `\n`.

### `apps/web/.env`

```env
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
VITE_API_URL=http://localhost:8000
```

---

## Make targets

| Command         | What it does                                              |
| --------------- | --------------------------------------------------------- |
| `make setup`    | First-time install — venv, pip, npm, env scaffolding      |
| `make dev`      | LocalStack + Redis + backend + Celery worker + frontend   |
| `make dev-local`| Backend + frontend only (no Docker / S3; jobs run inline) |
| `make worker`   | Celery worker in the foreground (needs Redis running)     |
| `make stop`     | Stop backend, worker, frontend + `docker compose down`    |
| `make restart`  | Stop, then start                                          |
| `make migrate`  | Run Django migrations                                     |
| `make logs`     | Tail backend + worker + frontend                          |

---

## Walkthrough

1. Sign in. Create a project.
2. Upload a CAD file. The row spinner runs while extraction works in the background.
3. Status flips to **Extracted**. An AI summary appears under the filename — edit inline if you want.
4. Expand the row to see the raw extraction: schema, units, confidence, parser warnings.
5. From the project page, kick off the BOM agent. It assembles the bill, sources parts, drafts supplier emails, and exports an Excel workbook.

---

## Repo layout

```
orbit/
├── Makefile                    # one-command dev automation
├── docker-compose.yml          # LocalStack (pinned to v3) + Redis (Celery broker)
├── apps/web/                   # Vite + React frontend
├── backend/                    # Django backend
│   ├── config/                 # settings, root URLs, ASGI
│   ├── files_api/              # upload, extraction, AI description
│   │   ├── extractor.py        #   pure-Python STEP header parser
│   │   ├── ai_description.py   #   Claude Haiku
│   │   ├── embeddings.py       #   semantic index
│   │   └── s3_service.py       #   S3 upload / download
│   ├── bom_agent/              # BOM assembly + supplier research + Gmail + Excel export
│   ├── projects/               # project CRUD
│   ├── assistant/              # in-app chat / Q&A
│   └── accounts/               # Clerk-backed auth
```

---

## API

All endpoints require `Authorization: Bearer <Clerk JWT>`.

| Method  | Path                              | Description                |
| ------- | --------------------------------- | -------------------------- |
| `GET`   | `/api/projects/`                  | List projects              |
| `POST`  | `/api/projects/`                  | Create project             |
| `GET`   | `/api/projects/<id>/`             | Project detail             |
| `POST`  | `/api/files/upload/`              | Upload (multipart)         |
| `GET`   | `/api/files/project/<id>/`        | List files in a project    |
| `GET`   | `/api/files/<id>/result/`         | Extraction result JSON     |
| `PATCH` | `/api/files/<id>/description/`    | Update file description    |

---

## Tests

```bash
cd backend
pytest
```
