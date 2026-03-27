# Orbit

> Agentic metadata extraction for mechanical engineering files.

Upload a STEP or CAD file. Orbit automatically parses the file header, generates an AI description using Claude, and surfaces structured extraction results — all within seconds.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
  - [1. Clone & Install](#1-clone--install)
  - [2. Environment Variables](#2-environment-variables)
  - [3. Start LocalStack (S3)](#3-start-localstack-s3)
  - [4. Run the Backend](#4-run-the-backend)
  - [5. Run the Frontend](#5-run-the-frontend)
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

- **Python** 3.11+
- **Node.js** 18+
- **Docker** — runs LocalStack for local S3 emulation
- **Clerk account** — [clerk.com](https://clerk.com) (free tier works)
- **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com) *(optional — upload and extraction work without it; AI descriptions are skipped)*

---

## Getting Started

### 1. Clone & Install

```bash
git clone https://github.com/stanislavli3/orbit.git
cd orbit
```

**Backend**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Frontend**

```bash
cd apps/web
npm install
```

---

### 2. Environment Variables

#### Backend — `backend/.env`

```env
DEBUG=True
SECRET_KEY=replace-with-a-long-random-string
ALLOWED_HOSTS=127.0.0.1,localhost

# Clerk — Dashboard → API Keys → JWT public key (PEM format)
CLERK_JWT_KEY=-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----
CLERK_ISSUER=https://<your-clerk-domain>.clerk.accounts.dev

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:5173

# S3 — LocalStack for local dev (matches docker-compose.yml)
AWS_S3_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_S3_REGION_NAME=us-east-1
AWS_STORAGE_BUCKET_NAME=orbit-local

# AI descriptions (optional)
ANTHROPIC_API_KEY=sk-ant-...
```

#### Frontend — `apps/web/.env`

```bash
cp apps/web/.env.example apps/web/.env
```

```env
# Clerk — Dashboard → API Keys → Publishable key
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...

# Django backend base URL (no trailing slash)
VITE_API_URL=http://localhost:8000
```

---

### 3. Start LocalStack (S3)

```bash
# From the repo root
docker compose up -d
```

Create the S3 bucket on first run:

```bash
aws --endpoint-url=http://localhost:4566 s3 mb s3://orbit-local --region us-east-1
```

> **Tip:** No AWS CLI? Run `pip install awscli-local` and use `awslocal` instead of `aws`.

---

### 4. Run the Backend

```bash
cd backend
source .venv/bin/activate

python manage.py migrate    # run once, and after every pull
python manage.py runserver
```

API available at **http://localhost:8000**

---

### 5. Run the Frontend

```bash
cd apps/web
npm run dev
```

App available at **http://localhost:5173**

---

## Demo Walkthrough

1. Open [http://localhost:5173](http://localhost:5173) and sign in
2. Click **Create project**, enter a name, and confirm — the project appears in the grid
3. Open the project and click **Upload files** — select a `.step` or `.stp` file
4. The file row shows a spinner while extraction runs in the background
5. Status flips to **Extracted** — an AI-generated description appears below the filename
6. Click the description to edit it inline and save
7. Click the chevron to expand the row and view the full extraction result: schema, units, confidence score, and any warnings

---

## Project Structure

```
orbit/
├── apps/
│   └── web/                    # React frontend (Vite)
│       └── src/
│           ├── api/            # Typed API client + shared interfaces
│           └── app/
│               └── components/ # Pages and UI components
├── backend/                    # Django backend
│   ├── config/                 # Settings, root URLs, ASGI entry point
│   ├── files_api/              # Core extraction app
│   │   ├── extractor.py        # Pure-Python STEP header parser (no OCC required)
│   │   ├── ai_description.py   # Claude Haiku description generator
│   │   ├── models.py           # UploadedFile, ExtractionResult
│   │   ├── views.py            # Upload, result, and description endpoints
│   │   ├── serializers.py      # DRF serializers
│   │   └── s3_service.py       # S3 upload / download helpers
│   └── projects/               # Project CRUD
├── docker-compose.yml          # LocalStack (S3 emulation)
└── README.md
```

---

## API Reference

All endpoints require a Clerk JWT: `Authorization: Bearer <token>`

| Method  | Endpoint                         | Description                          |
| ------- | -------------------------------- | ------------------------------------ |
| `GET`   | `/api/projects/`                 | List the authenticated user's projects |
| `POST`  | `/api/projects/`                 | Create a new project                 |
| `GET`   | `/api/projects/<id>/`            | Get project details                  |
| `POST`  | `/api/files/upload/`             | Upload a file (multipart/form-data)  |
| `GET`   | `/api/files/project/<id>/`       | List files in a project              |
| `GET`   | `/api/files/<id>/result/`        | Get extraction result JSON           |
| `PATCH` | `/api/files/<id>/description/`   | Update the file's text description   |

---

## Running Tests

```bash
cd backend
pytest
```
