# Production image for the Django API and the Celery worker (same image, different command).
# Build context is the REPO ROOT so the SAMPLE dataset in samples/ is included:
#   docker build -f backend/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./
COPY samples/ /app/samples/

# collectstatic needs a SECRET_KEY to import settings; this throwaway value is
# build-time only and never used at runtime.
RUN SECRET_KEY=collectstatic-only DEBUG=False python manage.py collectstatic --noinput

RUN useradd --create-home orbit && chown -R orbit /app
USER orbit

EXPOSE 8000
# Web: gunicorn. The worker overrides this with `celery -A config worker`.
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --workers ${WEB_CONCURRENCY:-2} --timeout 120 --access-logfile -"]
