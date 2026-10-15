# Stage 7A private staging

The CPU staging stack is intentionally local-only. PostgreSQL has no published
port, the API and frontend bind to loopback, and the Compose `private` network
is internal. The frontend BFF reaches FastAPI as `http://api:8000`; browsers
only reach the Next.js port.

## Start

Create an untracked `.env` in the repository root:

```dotenv
POSTGRES_PASSWORD=<disposable-local-password>
AUTH_SECRET=<random-secret-at-least-32-characters>
POSTGRES_DB=finflowml
POSTGRES_USER=finflowml
ENVIRONMENT=mock
FINFLOW_MOCK_EXTRACTION=true
```

Then run the explicit migration and startup sequence:

```bash
docker compose build db migrations api frontend worker
docker compose up -d db
docker compose run --rm migrations
docker compose --profile mock up -d api worker frontend
docker compose ps
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
curl --fail http://127.0.0.1:3000/login
```

The API/worker use the shared `receipt_uploads` volume. The frontend is a
non-root Next standalone container and has no database or receipt-volume
access. CPU/mock and GPU workers must not be started together for the same
database.

Run workflow smoke with a seeded account and synthetic image:

```bash
SMOKE_EMAIL=admin@example.test SMOKE_PASSWORD='<test-password>' \
SMOKE_IMAGE=/path/to/synthetic.png BASE_URL=http://127.0.0.1:8000 \
./scripts/container_smoke.sh
```

Stop without deleting persistent data with `docker compose down`. For a
disposable reset only, use `docker compose down -v` after confirming the
volumes belong to this staging project.

## Backup and restore

```bash
mkdir -p /tmp/finflow-backup
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > /tmp/finflow-backup/finflow.sql
docker run --rm -v finflowml_receipt_uploads:/source -v /tmp/finflow-backup:/backup alpine \
  tar czf /backup/receipts.tgz -C /source .
```

Restore only into a separately named disposable database/volume:

```bash
docker compose exec -T db createdb -U "$POSTGRES_USER" finflowml_restore
docker compose exec -T db psql -U "$POSTGRES_USER" finflowml_restore < /tmp/finflow-backup/finflow.sql
docker run --rm -v finflowml_receipt_uploads_restore:/target -v /tmp/finflow-backup:/backup alpine \
  tar xzf /backup/receipts.tgz -C /target
```

The restore is not a production backup claim until this disposable procedure
has been executed and the application has been pointed at the restored data.

## Security gates

Use an authenticated HTTPS reverse proxy before any network-accessible staging
endpoint. Keep the current same-origin BFF and native logout behavior, use
secure random secrets with rotation, restrict CORS to explicit origins, and
move the single-process rate limiter to a shared edge/store for replicas. The
current CSP still permits `unsafe-inline` for compatibility and requires a
nonce/hash migration before production. Container image scanning and GPU
runtime validation are separate gates; this task does not run the GPU profile.
