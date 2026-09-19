#!/bin/bash
# Repair the known integrations migration-history ordering issue.

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ -f .env ]]; then
    set -a; source .env; set +a
fi
export MSYS_NO_PATHCONV=1

if [[ -d "${PROJECT_ROOT}/server" ]]; then
    BACKEND_CONTEXT_PATH="${PROJECT_ROOT}/server"
else
    BACKEND_CONTEXT_PATH="${PROJECT_ROOT}"
fi

DJANGO_IMAGE=${DJANGO_IMAGE:-masscer-django-img}
NETWORK_NAME=${NETWORK_NAME:-masscer-net}
PGBOUNCER_CONTAINER=${PGBOUNCER_CONTAINER:-pgbouncer_container}

if ! docker image inspect "$DJANGO_IMAGE" &>/dev/null; then
    echo "Django image '$DJANGO_IMAGE' not found. Run ./taskfile.sh run -r first."
    exit 1
fi

DB_URL_CONTAINER=$(grep "^DB_CONNECTION_STRING=" .env 2>/dev/null | cut -d= -f2- \
    | sed "s|localhost:[0-9]*|${PGBOUNCER_CONTAINER}:6432|g; \
           s|127\.0\.0\.1:[0-9]*|${PGBOUNCER_CONTAINER}:6432|g")

echo "Checking migration history..."
docker run --rm \
    --network "$NETWORK_NAME" \
    --env-file .env \
    -e DB_CONNECTION_STRING="$DB_URL_CONTAINER" \
    -v "${BACKEND_CONTEXT_PATH}:/app" \
    "$DJANGO_IMAGE" python fix_migration_history.py
