#!/bin/bash
# Migrate script: runs Django management commands inside the Docker network.
# Usage:
#   ./migrate.sh                    - makemigrations + migrate
#   ./migrate.sh <app> <migration>  - revert to migration (e.g. ./migrate.sh ai_layers 0021)
#   ./migrate.sh <app> zero         - unapply all migrations for app

set -e

# Load .env
if [[ -f .env ]]; then
    set -a; source .env; set +a
fi
export MSYS_NO_PATHCONV=1

# Container / network config — must match run.sh defaults
DJANGO_IMAGE=${DJANGO_IMAGE:-masscer-django-img}
NETWORK_NAME=${NETWORK_NAME:-masscer-net}
PGBOUNCER_CONTAINER=${PGBOUNCER_CONTAINER:-pgbouncer_container}
REDIS_CONTAINER=${REDIS_CONTAINER:-redis-instance}
CHROMA_CONTAINER=${CHROMA_CONTAINER:-masscer-chroma}

if ! docker image inspect $DJANGO_IMAGE &>/dev/null; then
    echo "Django image '$DJANGO_IMAGE' not found. Run ./run.sh -r first."
    exit 1
fi

DB_URL_CONTAINER=$(grep "^DB_CONNECTION_STRING=" .env 2>/dev/null | cut -d= -f2- \
    | sed "s|localhost:[0-9]*|${PGBOUNCER_CONTAINER}:6432|g; \
           s|127\.0\.0\.1:[0-9]*|${PGBOUNCER_CONTAINER}:6432|g")
REDIS_INTERNAL="redis://${REDIS_CONTAINER}:6379"
CHROMA_HOST_CONTAINER=${CHROMA_HOST_CONTAINER:-$CHROMA_CONTAINER}
CHROMA_PORT_CONTAINER=${CHROMA_PORT_CONTAINER:-8000}

DJANGO_ENV=(
    --env-file .env
    -e DB_CONNECTION_STRING="$DB_URL_CONTAINER"
    -e CELERY_BROKER_URL="${REDIS_INTERNAL}/0"
    -e CELERY_RESULT_BACKEND="${REDIS_INTERNAL}/0"
    -e REDIS_CACHE_URL="${REDIS_INTERNAL}/1"
    -e REDIS_NOTIFICATIONS_URL="${REDIS_INTERNAL}/2"
    -e MEDIA_ROOT=/app/storage
    -e CHROMA_HOST="$CHROMA_HOST_CONTAINER"
    -e CHROMA_PORT="$CHROMA_PORT_CONTAINER"
)

run_manage() {
    docker run --rm \
        --network $NETWORK_NAME \
        "${DJANGO_ENV[@]}" \
        -v "$(pwd):/app" \
        $DJANGO_IMAGE python manage.py "$@"
}

if [ $# -eq 0 ]; then
    echo "Running makemigrations..."
    run_manage makemigrations
    echo "Running migrate..."
    run_manage migrate
elif [ $# -eq 2 ]; then
    echo "Reverting $1 to migration $2..."
    run_manage migrate "$1" "$2"
else
    echo "Usage:"
    echo "  ./migrate.sh                    # makemigrations + migrate"
    echo "  ./migrate.sh <app> <migration>  # revert (e.g. ./migrate.sh ai_layers 0021)"
    echo "  ./migrate.sh <app> zero         # unapply all for app"
    exit 1
fi

echo "Done."
