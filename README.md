# Orbit

## Tasks
1. Database
2. Python Django
3. PRD for AI agent
4. use localstack for MVP 


1. Authentification
2. Uploading files
3. R&D AI
4. 


Bash Check project structure and docker-compose
IN
cat docker-compose.yml 2>/dev/null || echo "no docker-compose.yml at root" && ls

OUT
version: "3.8"

services:
  localstack:
    image: localstack/localstack:latest
    container_name: localstack
    ports:
      - "4566:4566"
    environment:
      - SERVICES=s3,dynamodb
      - DEBUG=1
      - AWS_DEFAULT_REGION=us-east-1
    volumes:
      - ./localstack-data:/var/lib/localstack
      - /var/run/docker.sock:/var/run/docker.sockAGENTS.md
LICENSE
README.md
apps
backend
docker-compose.yml
docs
eval
infra
localstack-data
packages
prompts
storage
tasks
Bash Check running Docker containers
IN
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null

OUT
Tool permission request failed: Error: Stream closed
Bash Check Docker Compose service status
IN
docker compose ps 2>&1 | head -20

OUT
Tool permission request failed: Error: Stream closed
Bash Check backend env vars (non-sensitive)
IN
cat /Users/stanislav/orbit/backend/.env 2>/dev/null | grep -v "KEY\|SECRET\|PASSWORD" || echo "no .env or sensitive only"

OUT
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# Clerk — fill in from Clerk Dashboard
CLERK_ISSUER=

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:5173

# LocalStack S3 (docker compose up)
AWS_S3_ENDPOINT_URL=http://localhost:4566
AWS_S3_REGION_NAME=us-east-1
AWS_STORAGE_BUCKET_NAME=orbit-local
To run the full stack you need 3 services. Here's the startup order:

1. LocalStack (S3)


cd /Users/stanislav/orbit
docker compose up -d
2. Django backend


cd /Users/stanislav/orbit/backend
source .env  # or set env vars manually
python manage.py migrate
python manage.py runserver
3. React frontend


cd /Users/stanislav/orbit/apps/web
npm run dev