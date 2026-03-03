Masscer AI Project

## Local development (current flow)

### 1) Create and activate virtual environment

```bash
py -m venv venv
venv\Scripts\activate
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
- Redis
- Chroma

## Useful commands

```bash
# Rebuild backend + streaming images
./taskfile.sh run -r

# Skip host dependency install (pip/npm), useful for quick restarts
./taskfile.sh run -i

# Run frontend watch build
./taskfile.sh run -w

# Django migrations inside the Docker network
./taskfile.sh migrate

# Structure migration helper (backend to /server)
./taskfile.sh migrate_structure --dry-run
./taskfile.sh migrate_structure
```

## Default local URLs

- App (Nginx): `http://localhost:80`
- Django (direct): `http://localhost:8000` (or `.env` override)
- FastAPI (direct): `http://localhost:8001` (or `.env` override)
