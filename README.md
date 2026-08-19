Masscer AI Project

## Local development (current flow)

### 1) Install UV and sync lockfiles

```bash
uv sync --project server --frozen --no-dev
uv sync --project streaming --frozen --no-dev
```

### 2) Configure environment

- Copy `.env.example` to `.env` and set your values.

### 3) Ensure PostgreSQL + PgBouncer exist

```bash
./taskfile.sh postgres -u <username> -p <password> -d <database_name>
```

### 4) Start full local stack

```bash
./taskfile.sh run
```

This starts:
- Django
- Celery worker
- Celery beat
- FastAPI
- Nginx
- Dozzle (logs UI at `http://logs.localhost`)
- Redis
- Chroma

## Useful commands

```bash
# Rebuild backend + streaming images
./taskfile.sh run -r

# Skip host dependency install (uv/npm), useful for quick restarts
./taskfile.sh run -i

# Run frontend watch build
./taskfile.sh run -w

# Django migrations inside the Docker network
./taskfile.sh migrate

# Deploy to AWS from Pulumi directory (direnv-friendly)
cd pulumi && ./deploy.sh

# Skip bootstrap or migrations when needed
cd pulumi && ./deploy.sh --skip-bootstrap
cd pulumi && ./deploy.sh --skip-migrations

# Landing-only deploy (masscer.ai). Full ./deploy.sh also publishes the landing site.
cd pulumi && ./deploy-landing.sh

# Structure migration helper (backend to /server)
./taskfile.sh migrate_structure --dry-run
./taskfile.sh migrate_structure
```

## Default local URLs

- App (Nginx): `http://localhost:80`
- Logs UI (Dozzle via Nginx): `http://logs.localhost` — set `LOGS_USERNAME` / `LOGS_PASSWORD` in `.env`
- Django (direct): `http://localhost:8000` (or `.env` override)
- FastAPI (direct): `http://localhost:8001` (or `.env` override)
