# Orbit — developer shortcuts
# Usage: make <target>
#
# First time:  make setup
# Every day:   make dev
# Shut down:   make stop

.PHONY: dev setup stop restart logs migrate help

# ── Python resolution ──────────────────────────────────────────────────────────
# Prefer the project venv; otherwise fall back to python then python3 on PATH (handles spaces).
VENV        := backend/.venv
<<<<<<< HEAD
ifeq ($(OS),Windows_NT)
PYTHON      := $(if $(wildcard $(VENV)/Scripts/python.exe),$(abspath $(VENV)/Scripts/python.exe),python)
PIP         := $(if $(wildcard $(VENV)/Scripts/pip.exe),$(abspath $(VENV)/Scripts/pip.exe),pip)
POWERSHELL  := powershell -NoProfile -ExecutionPolicy Bypass -Command
else
PYTHON      := $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python)
PIP         := $(if $(wildcard $(VENV)/bin/pip),$(VENV)/bin/pip,pip)
endif
=======
PYTHON      := $(shell \
	if [ -f $(VENV)/bin/python ]; then printf '%s' "$(abspath $(VENV))/bin/python"; \
	elif command -v python >/dev/null 2>&1; then command -v python; \
	elif command -v python3 >/dev/null 2>&1; then command -v python3; \
	else printf '%s' python; fi)
PIP         := $(shell \
	if [ -f $(VENV)/bin/pip ]; then printf '%s' "$(abspath $(VENV))/bin/pip"; \
	elif command -v pip >/dev/null 2>&1; then command -v pip; \
	elif command -v pip3 >/dev/null 2>&1; then command -v pip3; \
	else printf '%s' pip; fi)
>>>>>>> origin/main

# ── Ports ──────────────────────────────────────────────────────────────────────
BACKEND_PORT  := 8000
FRONTEND_PORT := 5173
BACKEND_LOG   := .orbit-backend.log
FRONTEND_LOG  := .orbit-frontend.log
BACKEND_ERR   := .orbit-backend.err.log
FRONTEND_ERR  := .orbit-frontend.err.log
BACKEND_PID   := .orbit-backend.pid
FRONTEND_PID  := .orbit-frontend.pid

# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC TARGETS
# ══════════════════════════════════════════════════════════════════════════════

## dev: Start the full stack — LocalStack, backend, and frontend
ifeq ($(OS),Windows_NT)
dev: _docker-up _bucket _migrate
	@echo ""
	@echo "  Backend  → http://localhost:$(BACKEND_PORT)"
	@echo "  Frontend → http://localhost:$(FRONTEND_PORT)"
	@echo "  Run 'make stop' to stop background services"
	@echo ""
	@$(POWERSHELL) "Remove-Item '$(BACKEND_LOG)','$(FRONTEND_LOG)','$(BACKEND_ERR)','$(FRONTEND_ERR)','$(BACKEND_PID)','$(FRONTEND_PID)' -ErrorAction SilentlyContinue; $$backend = Start-Process -FilePath '$(PYTHON)' -ArgumentList 'manage.py','runserver','$(BACKEND_PORT)' -WorkingDirectory 'backend' -RedirectStandardOutput '$(BACKEND_LOG)' -RedirectStandardError '$(BACKEND_ERR)' -PassThru; Set-Content -Path '$(BACKEND_PID)' -Value $$backend.Id; $$frontend = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev','--','--host','127.0.0.1','--port','$(FRONTEND_PORT)' -WorkingDirectory 'apps/web' -RedirectStandardOutput '$(FRONTEND_LOG)' -RedirectStandardError '$(FRONTEND_ERR)' -PassThru; Set-Content -Path '$(FRONTEND_PID)' -Value $$frontend.Id; Write-Host 'Background services started.'"
else
dev: _docker-up _bucket _migrate
	@echo ""
	@echo "  Backend  → http://localhost:$(BACKEND_PORT)"
	@echo "  Frontend → http://localhost:$(FRONTEND_PORT)"
	@echo "  Press Ctrl+C to stop everything"
	@echo ""
	@trap 'echo "\nStopping..."; kill %1 %2 2>/dev/null; exit 0' INT; \
	  (cd backend && "$(PYTHON)" manage.py runserver $(BACKEND_PORT) 2>&1 | sed 's/^/\033[34m[backend] \033[0m/') & \
	  (cd apps/web && npm run dev 2>&1 | sed 's/^/\033[32m[frontend]\033[0m /') & \
	  wait
endif

## setup: First-time install — create venv, install Python + Node deps, copy env files
setup:
	@echo "── Python environment ───────────────────────────────────"
<<<<<<< HEAD
	python -m venv $(VENV)
=======
	"$(PYTHON)" -m venv "$(VENV)"
>>>>>>> origin/main
	"$(PIP)" install -r backend/requirements.txt -q
	@echo "── Node dependencies ────────────────────────────────────"
	cd apps/web && npm install
	@echo "── Environment files ────────────────────────────────────"
	@"$(PYTHON)" -c "from pathlib import Path; import shutil; env=Path('backend/.env'); example=Path('backend/.env.example'); (shutil.copy(example, env), print('Created backend/.env  <- fill in your keys')) if (not env.exists() and example.exists()) else None"
	@"$(PYTHON)" -c "from pathlib import Path; import shutil; env=Path('apps/web/.env'); example=Path('apps/web/.env.example'); (shutil.copy(example, env), print('Created apps/web/.env <- fill in your keys')) if (not env.exists() and example.exists()) else None"
	@echo ""
	@echo "Done. Next steps:"
	@echo "  1. Edit backend/.env  — add CLERK_JWT_KEY, CLERK_ISSUER, ANTHROPIC_API_KEY"
	@echo "  2. Edit apps/web/.env — add VITE_CLERK_PUBLISHABLE_KEY"
	@echo "  3. Run: make dev"

## stop: Stop backend, frontend, and LocalStack

ifeq ($(OS),Windows_NT)
stop:
	@$(POWERSHELL) "foreach ($$service in @(@{Name='Backend';PidFile='$(BACKEND_PID)'}, @{Name='Frontend';PidFile='$(FRONTEND_PID)'})) { if (Test-Path $$service.PidFile) { $$processId = Get-Content $$service.PidFile | Select-Object -First 1; if ($$processId) { Stop-Process -Id ([int]$$processId) -Force -ErrorAction SilentlyContinue }; Remove-Item $$service.PidFile -ErrorAction SilentlyContinue; Write-Host ($$service.Name + ' stopped') } }; docker compose down | Out-Null; if ($$LASTEXITCODE -eq 0) { Write-Host 'LocalStack stopped' }"
else
stop:
	@kill $$(lsof -ti:$(BACKEND_PORT))  2>/dev/null && echo "Backend stopped"  || true
	@kill $$(lsof -ti:$(FRONTEND_PORT)) 2>/dev/null && echo "Frontend stopped" || true
	@kill $$(lsof -ti:5174)             2>/dev/null || true
	@docker compose down && echo "LocalStack stopped" || true
endif

## restart: Stop everything then start again
restart: stop dev

## migrate: Run Django database migrations
migrate: _migrate

## logs: Tail backend and frontend logs (when run in background)

ifeq ($(OS),Windows_NT)
logs:
	@$(POWERSHELL) "$$logs = @(); foreach ($$path in @('$(BACKEND_LOG)','$(BACKEND_ERR)','$(FRONTEND_LOG)','$(FRONTEND_ERR)')) { if (Test-Path $$path) { $$logs += $$path } }; if ($$logs.Count -eq 0) { Write-Host 'No log files found. Use make dev to start background services.'; exit 0 }; Get-Content -Path $$logs -Wait"
else
logs:
	@tail -f /tmp/django.log /tmp/vite.log 2>/dev/null || echo "No log files found. Use 'make dev' to start with inline logs."
endif

## help: Show available targets
help:
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@"$(PYTHON)" -c "import pathlib; lines=pathlib.Path('Makefile').read_text(encoding='utf-8').splitlines(); items=[line[3:].split(': ',1) for line in lines if line.startswith('## ') and ': ' in line]; [print('  %-12s %s' % (name, desc)) for name, desc in items]"
	@echo ""

# ══════════════════════════════════════════════════════════════════════════════
# INTERNAL TARGETS
# ══════════════════════════════════════════════════════════════════════════════

ifeq ($(OS),Windows_NT)
_docker-up:
	@echo "── Starting LocalStack ──────────────────────────────────"
	@docker info >NUL 2>&1 || (echo "Docker is not running. Please start Docker Desktop and try again." && exit 1)
	@docker compose up -d
	@$(POWERSHELL) "$$deadline=(Get-Date).AddSeconds(60); Write-Host -NoNewline 'Waiting for S3'; while ((Get-Date) -lt $$deadline) { try { $$health = Invoke-RestMethod 'http://localhost:4566/_localstack/health' -TimeoutSec 2; if ($$health.services.s3) { Write-Host ' ready'; exit 0 } } catch { }; Write-Host -NoNewline '.'; Start-Sleep -Seconds 1 }; Write-Host ' failed'; exit 1"
else
_docker-up:
	@echo "── Starting LocalStack ──────────────────────────────────"
	@docker info > /dev/null 2>&1 || (echo "Docker is not running. Please start Docker Desktop and try again." && exit 1)
	@docker compose up -d
	@printf "Waiting for S3"
	@until curl -s http://localhost:4566/_localstack/health 2>/dev/null | grep -q '"s3"'; do printf '.'; sleep 1; done
	@echo " ready"
endif

_bucket:
	@"$(PYTHON)" -c "\
import boto3, sys; \
c = boto3.client('s3', endpoint_url='http://localhost:4566', aws_access_key_id='test', aws_secret_access_key='test', region_name='us-east-1'); \
names = [b['Name'] for b in c.list_buckets()['Buckets']]; \
c.create_bucket(Bucket='orbit-local') if 'orbit-local' not in names else None; \
print('S3 bucket ready')"

_migrate:
	@echo "── Running migrations ───────────────────────────────────"
<<<<<<< HEAD
	@cd backend && "$(PYTHON)" manage.py migrate && echo "Migrations OK"
=======
	@cd backend && "$(PYTHON)" manage.py migrate --verbosity 0 && echo "Migrations OK"
>>>>>>> origin/main
