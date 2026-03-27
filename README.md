# Orbit

Agentic metadata extraction for mechanical engineering files. Upload a STEP/CAD file, get an AI-generated description and structured extraction results back automatically.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Clerk |
| Backend | Python 3.11, Django 5, Django REST Framework |
| Auth | Clerk (Google OAuth + email magic link) |
| Storage | AWS S3 (LocalStack for local dev) |
| AI | Claude Haiku (auto-generated file descriptions) |

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (for LocalStack S3)
- A [Clerk](https://clerk.com) application (free tier is fine)
- An [Anthropic API key](https://console.anthropic.com) (optional — upload works without it, AI descriptions will be skipped)

---

## 1. Clone and install

```bash
git clone https://github.com/stanislavli3/orbit.git
cd orbit
```

### Backend dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend dependencies

```bash
cd apps/web
npm install
```

---

## 2. Environment variables

### Backend — `backend/.env`

Copy and fill in:

```env
DEBUG=True
SECRET_KEY=replace-with-a-long-random-string
ALLOWED_HOSTS=127.0.0.1,localhost

# Clerk — Dashboard → API Keys → JWT public key (PEM format)
CLERK_JWT_KEY=-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----
CLERK_ISSUER=https://<your-clerk-domain>.clerk.accounts.dev

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:5173

# LocalStack S3 (matches docker-compose.yml)
AWS_S3_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_S3_REGION_NAME=us-east-1
AWS_STORAGE_BUCKET_NAME=orbit-local

# AI descriptions (optional — skip to disable)
ANTHROPIC_API_KEY=sk-ant-...
```

### Frontend — `apps/web/.env`

```bash
cp apps/web/.env.example apps/web/.env
```

Then fill in:

```env
# Clerk — Dashboard → API Keys → Publishable key
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...

# Django backend
VITE_API_URL=http://localhost:8000
```

---

## 3. Start LocalStack (S3)

```bash
# from repo root
docker compose up -d
```

Create the S3 bucket on first run:

```bash
aws --endpoint-url=http://localhost:4566 s3 mb s3://orbit-local --region us-east-1
```

> If you don't have the AWS CLI, install it or use `pip install awscli-local` and replace `aws` with `awslocal`.

---

## 4. Run the backend

```bash
cd backend
source .venv/bin/activate

# Apply database migrations (first time and after pulls)
python manage.py migrate

# Start the dev server
python manage.py runserver
```

Backend is now at **http://localhost:8000**

---

## 5. Run the frontend

```bash
cd apps/web
npm run dev
```

Frontend is now at **http://localhost:5173**

---

## 6. Full demo flow

1. Open [http://localhost:5173](http://localhost:5173)
2. Sign in with Google or email magic link
3. Click **Create project** → enter a name → project appears in the grid
4. Open the project → click **Upload files** → pick a `.step` or `.stp` file
5. The file row shows a spinner while extraction runs in the background
6. When done, status flips to **Extracted** and an AI-generated description appears below the filename
7. Click the description to edit it inline
8. Expand the file row (chevron) to see the full extraction result: schema, units, confidence score, warnings

---

## Project structure

```
orbit/
├── apps/
│   └── web/                  # React frontend (Vite)
│       └── src/
│           ├── api/           # API client + TypeScript types
│           └── app/
│               └── components/ # Pages and UI components
├── backend/                   # Django backend
│   ├── config/                # Settings, URLs, ASGI
│   ├── files_api/             # File upload, extraction, AI description
│   │   ├── extractor.py       # Pure-Python STEP header parser
│   │   ├── ai_description.py  # Claude Haiku description generator
│   │   ├── models.py          # UploadedFile, ExtractionResult
│   │   ├── views.py           # Upload, result, description endpoints
│   │   └── s3_service.py      # S3 upload/download helpers
│   └── projects/              # Project CRUD
├── docker-compose.yml         # LocalStack (S3)
└── README.md
```

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/projects/` | List user's projects |
| `POST` | `/api/projects/` | Create a project |
| `GET` | `/api/projects/<id>/` | Get project detail |
| `POST` | `/api/files/upload/` | Upload a file (multipart) |
| `GET` | `/api/files/project/<id>/` | List files in a project |
| `GET` | `/api/files/<id>/result/` | Get extraction result JSON |
| `PATCH` | `/api/files/<id>/description/` | Update file description |

All endpoints require a Clerk JWT in the `Authorization: Bearer <token>` header.

---

## Running tests

```bash
cd backend
pytest
```
