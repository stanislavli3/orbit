# Orbit — developer shortcuts
# Usage: make <target>
#
# First time:  make setup
# Every day:   make dev
# Shut down:   make stop

.PHONY: dev setup stop restart logs migrate help

# ── Python resolution ──────────────────────────────────────────────────────────
# Prefer the project venv; fall back to whatever `python` resolves to on PATH.
VENV        := backend/.venv
PYTHON      := $(shell [ -f $(VENV)/bin/python ] && echo $(VENV)/bin/python || echo python)
PIP         := $(shell [ -f $(VENV)/bin/pip    ] && echo $(VENV)/bin/pip    || echo pip)

# ── Ports ──────────────────────────────────────────────────────────────────────
BACKEND_PORT  := 8000
FRONTEND_PORT := 5173

# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC TARGETS
# ══════════════════════════════════════════════════════════════════════════════

## dev: Start the full stack — LocalStack, backend, and frontend
dev: _docker-up _bucket _migrate
	@echo ""
	@echo "  Backend  → http://localhost:$(BACKEND_PORT)"
	@echo "  Frontend → http://localhost:$(FRONTEND_PORT)"
	@echo "  Press Ctrl+C to stop everything"
	@echo ""
	@trap 'echo "\nStopping..."; kill %1 %2 2>/dev/null; exit 0' INT; \
	  (cd backend && $(PYTHON) manage.py runserver $(BACKEND_PORT) 2>&1 | sed 's/^/\033[34m[backend] \033[0m/') & \
	  (cd apps/web && npm run dev 2>&1 | sed 's/^/\033[32m[frontend]\033[0m /') & \
	  wait

## setup: First-time install — create venv, install Python + Node deps, copy env files
setup:
	@echo "── Python environment ───────────────────────────────────"
	python -m venv $(VENV)
	$(PIP) install -r backend/requirements.txt -q
	@echo "── Node dependencies ────────────────────────────────────"
	cd apps/web && npm install
	@echo "── Environment files ────────────────────────────────────"
	@[ -f backend/.env ] || (cp backend/.env.example backend/.env && echo "Created backend/.env  ← fill in your keys")
	@[ -f apps/web/.env ] || (cp apps/web/.env.example apps/web/.env && echo "Created apps/web/.env ← fill in your keys")
	@echo ""
	@echo "Done. Next steps:"
	@echo "  1. Edit backend/.env  — add CLERK_JWT_KEY, CLERK_ISSUER, ANTHROPIC_API_KEY"
	@echo "  2. Edit apps/web/.env — add VITE_CLERK_PUBLISHABLE_KEY"
	@echo "  3. Run: make dev"

## stop: Stop backend, frontend, and LocalStack
stop:
	@kill $$(lsof -ti:$(BACKEND_PORT))  2>/dev/null && echo "Backend stopped"  || true
	@kill $$(lsof -ti:$(FRONTEND_PORT)) 2>/dev/null && echo "Frontend stopped" || true
	@kill $$(lsof -ti:5174)             2>/dev/null || true
	@docker compose down && echo "LocalStack stopped" || true

## restart: Stop everything then start again
restart: stop dev

## migrate: Run Django database migrations
migrate: _migrate

## logs: Tail backend and frontend logs (when run in background)
logs:
	@tail -f /tmp/django.log /tmp/vite.log 2>/dev/null || echo "No log files found. Use 'make dev' to start with inline logs."

## help: Show available targets
help:
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## //' | awk -F': ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ══════════════════════════════════════════════════════════════════════════════
# INTERNAL TARGETS
# ══════════════════════════════════════════════════════════════════════════════

_docker-up:
	@echo "── Starting LocalStack ──────────────────────────────────"
	@docker info > /dev/null 2>&1 || (echo "Docker is not running. Please start Docker Desktop and try again." && exit 1)
	@docker compose up -d
	@printf "Waiting for S3"
	@until curl -s http://localhost:4566/_localstack/health 2>/dev/null | grep -q '"s3"'; do printf '.'; sleep 1; done
	@echo " ready"

_bucket:
	@$(PYTHON) -c "\
import boto3, sys; \
c = boto3.client('s3', endpoint_url='http://localhost:4566', aws_access_key_id='test', aws_secret_access_key='test', region_name='us-east-1'); \
names = [b['Name'] for b in c.list_buckets()['Buckets']]; \
c.create_bucket(Bucket='orbit-local', CreateBucketConfiguration={'LocationConstraint':'us-east-1'}) if 'orbit-local' not in names else None; \
print('S3 bucket ready')" 2>/dev/null || echo "S3 bucket check skipped (boto3 not available)"

_migrate:
	@echo "── Running migrations ───────────────────────────────────"
	@cd backend && $(PYTHON) manage.py migrate --verbosity 0 && echo "Migrations OK"
