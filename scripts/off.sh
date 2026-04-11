#!/bin/bash

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

POSTGRES_CONTAINER=${POSTGRES_CONTAINER:-postgres_container}
PGBOUNCER_CONTAINER=${PGBOUNCER_CONTAINER:-pgbouncer_container}
REDIS_CONTAINER=${REDIS_CONTAINER:-redis-instance}
DJANGO_CONTAINER=${DJANGO_CONTAINER:-masscer-django}
FASTAPI_CONTAINER=${FASTAPI_CONTAINER:-masscer-fastapi}
CHROMA_CONTAINER=${CHROMA_CONTAINER:-masscer-chroma}
NGINX_CONTAINER=${NGINX_CONTAINER:-masscer-nginx}
WORKER_CONTAINER=${WORKER_CONTAINER:-masscer-celery-worker}
BEAT_CONTAINER=${BEAT_CONTAINER:-masscer-celery-beat}

CONTAINERS=(
  "$DJANGO_CONTAINER"
  "$FASTAPI_CONTAINER"
  "$CHROMA_CONTAINER"
  "$NGINX_CONTAINER"
  "$WORKER_CONTAINER"
  "$BEAT_CONTAINER"
  "$POSTGRES_CONTAINER"
  "$PGBOUNCER_CONTAINER"
  "$REDIS_CONTAINER"
)

echo "Stopping Masscer services..."
for container in "${CONTAINERS[@]}"; do
  if docker ps -q -f "name=^${container}$" | grep -q .; then
    docker stop "$container" >/dev/null
    echo "  stopped: $container"
  else
    echo "  already stopped: $container"
  fi
done

echo "Done."
