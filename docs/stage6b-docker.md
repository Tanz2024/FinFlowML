# Stage 6B Docker staging

This stack is private/local by default. It runs CPU-only mock extraction in
`api` and `worker`; it does not download Qwen or require a GPU. The optional
`gpu-worker` profile is separate and mounts an external adapter read-only.

## Start

Create a local `.env` (never commit it):

```dotenv
POSTGRES_PASSWORD=use-a-local-disposable-password
AUTH_SECRET=use-a-random-secret-at-least-32-characters
ENVIRONMENT=mock
FINFLOW_MOCK_EXTRACTION=true
```

Build and start the one-shot migration, API, and worker:

```bash
docker compose build
docker compose up -d db
docker compose run --rm migrations
docker compose --profile mock up -d api worker
docker compose ps
./scripts/container_smoke.sh
```

The API is bound to `127.0.0.1:8000`; PostgreSQL is only on the private
Compose network. Migrations are explicit and API/worker do not run them.

The GPU profile requires an external adapter path and compatible NVIDIA runtime:

```bash
ADAPTER_PATH=/private/path/to/best_adapter docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu up -d gpu-worker
```

The GPU host must have the NVIDIA driver, NVIDIA Container Toolkit, and a
Docker runtime that supports `gpus: all`. Preload the pinned Hugging Face model
under the `hf_cache` volume or allow the worker's controlled Hugging Face
download through the configured network policy. CPU/mock and GPU profiles are
mutually exclusive worker choices for a staging database.

## Teardown and backup

```bash
docker compose down
docker compose down -v  # destructive: removes disposable database/uploads
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql
docker compose exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB" < backup.sql
```

Receipt storage is the `receipt_uploads` volume and should be backed up with a
volume-aware tool alongside the database dump.

## Security gates

Before private staging, use HTTPS at a reverse proxy, secret management and
rotation, a strict CORS allowlist, rate limiting, CSRF protection appropriate to
the auth flow, restricted encrypted backups, and volume access controls. The
demo CSP still permits `unsafe-inline`; review nonce/hash migration before
deployment. Do not publish Compose ports directly to the internet.
