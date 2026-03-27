# Orbit

> Agentic metadata extraction for mechanical engineering files.

Upload a STEP or CAD file. Orbit automatically parses the file header, generates an AI description using Claude, and surfaces structured extraction results — all within seconds.

---

## Quick Start (TL;DR)

```bash
git clone https://github.com/stanislavli3/orbit.git
cd orbit
make setup        # install dependencies + create env files
# fill in backend/.env and apps/web/.env (see Environment Variables below)
make dev          # start everything with a single command
```

Open **http://localhost:5173** — done.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [First-Time Setup](#first-time-setup)
- [Environment Variables](#environment-variables)
- [Running the Project](#running-the-project)
- [Make Commands](#make-commands)
- [Demo Walkthrough](#demo-walkthrough)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Running Tests](#running-tests)

---

## Features

- **Authentication** — Google OAuth and email magic link via Clerk
- **Project management** — create and organize projects as collections of files
- **File upload** — supports `.step`, `.stp`, `.pdf`, `.dwg`, `.dxf`, `.iges`, `.igs` (up to 100 MB)
- **STEP header extraction** — pure-Python parser; no external CAD dependencies required
- **AI-generated descriptions** — Claude Haiku writes a plain-English summary of each file automatically on upload
- **Editable descriptions** — users can refine the AI output inline
- **Live status polling** — UI updates in real time as extraction completes in the background

---

## Tech Stack

| Layer     | Technology                                          |
| --------- | --------------------------------------------------- |
| Frontend  | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui |
| Backend   | Python 3.11, Django 5, Django REST Framework        |
| Auth      | Clerk (Google OAuth + email magic link)             |
| Storage   | AWS S3 / LocalStack (local dev)                     |
| AI        | Anthropic Claude Haiku                              |
| Database  | SQLite (dev) · PostgreSQL (production)              |

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | |
| Node.js | 18+ | |
| Docker Desktop | latest | runs LocalStack for S3 emulation |
| Clerk account | — | [clerk.com](https://clerk.com), free tier works |
| Anthropic API key | — | [console.anthropic.com](https://console.anthropic.com), optional |

---

## First-Time Setup

Run once after cloning. This creates the virtual environment, installs all dependencies, and scaffolds your env files:

```bash
make setup
```

Then fill in the two env files (see [Environment Variables](#environment-variables) below).

---

## Environment Variables

### Backend — `backend/.env`

```env
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(50))">
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# Clerk — Dashboard → API Keys
# JWT public key: click "Show JWT public key", paste the full PEM on one line with \n between lines
CLERK_JWT_KEY=-----BEGIN PUBLIC KEY-----\nMIIB...\n-----END PUBLIC KEY-----
CLERK_ISSUER=https://your-app.clerk.accounts.dev

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174

# S3 — LocalStack for local dev (do not change these)
AWS_S3_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_S3_REGION_NAME=us-east-1
AWS_STORAGE_BUCKET_NAME=orbit-local

# AI descriptions (optional — skip to disable)
ANTHROPIC_API_KEY=sk-ant-...
```

> **Finding your Clerk keys:** Dashboard → select your app → **API Keys** → copy the Publishable key and JWT public key. The Issuer URL is shown on the same page.

### Frontend — `apps/web/.env`

```env
# Clerk — Dashboard → API Keys → Publishable key (starts with pk_test_)
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...

# Django backend base URL (no trailing slash)
VITE_API_URL=http://localhost:8000
```

---

## Running the Project

### Start everything

```bash
make dev
```

This single command:
1. Starts Docker + LocalStack (S3)
2. Waits until S3 is ready
3. Creates the `orbit-local` S3 bucket if it doesn't exist
4. Runs any pending database migrations
5. Starts the Django backend on **http://localhost:8000**
6. Starts the Vite frontend on **http://localhost:5173**

Press `Ctrl+C` to stop all services at once.

### Stop everything

```bash
make stop
```

---

## Make Commands

| Command | Description |
|---|---|
| `make setup` | First-time install: venv, pip, npm, env file scaffolding |
| `make dev` | Start the full stack (LocalStack + backend + frontend) |
| `make stop` | Stop all running services |
| `make restart` | Stop then start again |
| `make migrate` | Run Django migrations manually |
| `make logs` | Tail backend and frontend logs |
| `make help` | List all available commands |

---

## Demo Walkthrough

1. Open [http://localhost:5173](http://localhost:5173) and sign in
2. Click **Create project**, enter a name, and confirm — the project appears in the grid
3. Open the project and click **Upload files** — select a `.step` or `.stp` file
4. The file row shows a spinner while extraction runs in the background
5. Status flips to **Extracted** — an AI-generated description appears below the filename
6. Click the description to edit it inline and save
7. Click the chevron ▾ to expand the row and view the full extraction result: schema, units, confidence score, and any parser warnings

---

## Project Structure

```
orbit/
├── Makefile                    # Single-command dev automation
├── docker-compose.yml          # LocalStack (S3 emulation)
├── apps/
│   └── web/                    # React frontend (Vite)
│       ├── .env.example
│       └── src/
│           ├── api/            # Typed API client + shared interfaces
│           └── app/
│               └── components/ # Pages and UI components
├── backend/                    # Django backend
│   ├── .env.example
│   ├── config/                 # Settings, root URLs, ASGI entry point
│   ├── files_api/              # Core extraction app
│   │   ├── extractor.py        # Pure-Python STEP header parser (no OCC required)
│   │   ├── ai_description.py   # Claude Haiku description generator
│   │   ├── models.py           # UploadedFile, ExtractionResult
│   │   ├── views.py            # Upload, result, and description endpoints
│   │   ├── serializers.py      # DRF serializers
│   │   └── s3_service.py       # S3 upload / download helpers
│   └── projects/               # Project CRUD
```

---

## API Reference

All endpoints require a Clerk JWT: `Authorization: Bearer <token>`

| Method  | Endpoint                         | Description                            |
| ------- | -------------------------------- | -------------------------------------- |
| `GET`   | `/api/projects/`                 | List the authenticated user's projects |
| `POST`  | `/api/projects/`                 | Create a new project                   |
| `GET`   | `/api/projects/<id>/`            | Get project details                    |
| `POST`  | `/api/files/upload/`             | Upload a file (multipart/form-data)    |
| `GET`   | `/api/files/project/<id>/`       | List files in a project                |
| `GET`   | `/api/files/<id>/result/`        | Get extraction result JSON             |
| `PATCH` | `/api/files/<id>/description/`   | Update the file's text description     |

---

## Running Tests

```bash
cd backend
pytest
```
