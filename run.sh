#!/bin/bash

# ── Helpers ───────────────────────────────────────────────────────────────────
error()   { echo -e "\033[31m$1\033[0m"; }
info()    { echo -e "\033[34m$1\033[0m"; }
success() { echo -e "\033[32m$1\033[0m"; }

cleanup() {
    info "Stopping all containers..."
    docker stop $DJANGO_CONTAINER  2>/dev/null
    docker stop $FASTAPI_CONTAINER 2>/dev/null
    docker stop $CHROMA_CONTAINER  2>/dev/null
    docker stop $NGINX_CONTAINER   2>/dev/null
    docker stop $WORKER_CONTAINER  2>/dev/null
    docker stop $BEAT_CONTAINER    2>/dev/null
    info "Done."
}
trap 'cleanup; exit 0' SIGINT SIGTERM

# ── Flags ─────────────────────────────────────────────────────────────────────
INSTALL=true
WATCH=false
REBUILD=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -i|--install) INSTALL=false ;;
        -w|--watch)   WATCH=true ;;
        -r|--rebuild) REBUILD=true ;;
        *) error "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# ── Load .env ─────────────────────────────────────────────────────────────────
if [[ -f .env ]]; then
    set -a; source .env; set +a
fi
# Prevent Git Bash from converting POSIX paths to Windows paths in Docker args
export MSYS_NO_PATHCONV=1

# ── Ports ─────────────────────────────────────────────────────────────────────
DJANGO_PORT=${DJANGO_PORT:-8000}
FASTAPI_PORT=${FASTAPI_PORT:-8001}
REDIS_PORT=${REDIS_PORT:-6379}
NGINX_PORT=${NGINX_PORT:-80}

# ── Container / image names ───────────────────────────────────────────────────
POSTGRES_CONTAINER=${POSTGRES_CONTAINER:-postgres_container}
PGBOUNCER_CONTAINER=${PGBOUNCER_CONTAINER:-pgbouncer_container}
REDIS_CONTAINER=${REDIS_CONTAINER:-redis-instance}
DJANGO_CONTAINER=${DJANGO_CONTAINER:-masscer-django}
DJANGO_IMAGE=${DJANGO_IMAGE:-masscer-django-img}
CHROMA_CONTAINER=${CHROMA_CONTAINER:-masscer-chroma}
FASTAPI_CONTAINER=${FASTAPI_CONTAINER:-masscer-fastapi}
FASTAPI_IMAGE=${FASTAPI_IMAGE:-masscer-fastapi-img}
NGINX_CONTAINER=${NGINX_CONTAINER:-masscer-nginx}
WORKER_CONTAINER=${WORKER_CONTAINER:-masscer-celery-worker}
BEAT_CONTAINER=${BEAT_CONTAINER:-masscer-celery-beat}
NETWORK_NAME=${NETWORK_NAME:-masscer-net}

success "Starting Masscer"
info "  DJANGO_PORT:  $DJANGO_PORT | FASTAPI_PORT: $FASTAPI_PORT | NGINX_PORT: $NGINX_PORT"
info "  REBUILD: $REBUILD | INSTALL: $INSTALL | WATCH: $WATCH"

# ── Virtual env (host-side tooling / pip install only) ────────────────────────
if [[ -f "venv/bin/activate" ]]; then
    source venv/bin/activate
elif [[ -f "venv/Scripts/activate" ]]; then
    source venv/Scripts/activate
else
    error "Virtual environment not found. Run: py -m venv venv"; exit 1
fi

# ── PostgreSQL & PGBouncer ────────────────────────────────────────────────────
info "Starting PostgreSQL..."
if [[ "$(docker ps -aq -f name=$POSTGRES_CONTAINER)" ]]; then
    docker start $POSTGRES_CONTAINER || { error "Failed to start PostgreSQL"; exit 1; }
else
    error "PostgreSQL container not found. Run ./createPostgres.sh first."; exit 1
fi
success "PostgreSQL ready."

info "Starting PGBouncer..."
if [[ "$(docker ps -aq -f name=$PGBOUNCER_CONTAINER)" ]]; then
    docker start $PGBOUNCER_CONTAINER || { error "Failed to start PGBouncer"; exit 1; }
else
    error "PGBouncer container not found. Run ./createPostgres.sh first."; exit 1
fi
success "PGBouncer ready."

# ── Redis ─────────────────────────────────────────────────────────────────────
info "Starting Redis..."
if [[ "$(docker ps -aq -f name=$REDIS_CONTAINER)" ]]; then
    docker start $REDIS_CONTAINER || { error "Failed to start Redis"; exit 1; }
else
    docker run --name $REDIS_CONTAINER -d -p "${REDIS_PORT}:6379" redis:alpine \
        || { error "Failed to create Redis container"; exit 1; }
fi
success "Redis ready."

# ── Docker network ────────────────────────────────────────────────────────────
info "Setting up network '$NETWORK_NAME'..."
if ! docker network ls --format '{{.Name}}' | grep -q "^${NETWORK_NAME}$"; then
    docker network create $NETWORK_NAME && success "Network '$NETWORK_NAME' created."
else
    info "Network '$NETWORK_NAME' already exists."
fi

for CONTAINER in $POSTGRES_CONTAINER $PGBOUNCER_CONTAINER $REDIS_CONTAINER; do
    if docker ps -q -f name="^${CONTAINER}$" | grep -q .; then
        if ! docker network inspect $NETWORK_NAME \
                --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null \
                | grep -qw "$CONTAINER"; then
            docker network connect $NETWORK_NAME $CONTAINER \
                && success "Connected $CONTAINER → $NETWORK_NAME."
        else
            info "$CONTAINER already in $NETWORK_NAME."
        fi
    fi
done

# ── Install (host deps + git pull) ────────────────────────────────────────────
if [ "$INSTALL" = true ]; then
    git pull
    pip install -q -r requirements.txt || { error "pip install failed"; exit 1; }
    cd ./streaming
    npm i -q || { error "npm install failed"; exit 1; }
    cd ..
fi

# ── Chroma ────────────────────────────────────────────────────────────────────
info "Starting Chroma..."
if [[ "$(docker ps -aq -f name=$CHROMA_CONTAINER)" ]]; then
    docker start $CHROMA_CONTAINER || { error "Failed to start Chroma"; exit 1; }
else
    docker run -d \
        --name $CHROMA_CONTAINER \
        -v "$(pwd)/vector_storage:/data" \
        -p "8002:8000" \
        chromadb/chroma:0.5.11 || { error "Failed to create Chroma container"; exit 1; }
fi

if ! docker network inspect $NETWORK_NAME \
        --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null \
        | grep -qw "$CHROMA_CONTAINER"; then
    docker network connect $NETWORK_NAME $CHROMA_CONTAINER \
        && success "Connected $CHROMA_CONTAINER → $NETWORK_NAME."
else
    info "$CHROMA_CONTAINER already in $NETWORK_NAME."
fi
success "Chroma ready."

# ── Build images ──────────────────────────────────────────────────────────────
if [ "$REBUILD" = true ] || ! docker image inspect $DJANGO_IMAGE &>/dev/null; then
    info "Building Django image..."
    docker build -t $DJANGO_IMAGE . || { error "Django image build failed"; exit 1; }
else
    info "Django image exists. Skipping build (use -r to rebuild)."
fi

if [ "$REBUILD" = true ] || ! docker image inspect $FASTAPI_IMAGE &>/dev/null; then
    info "Building FastAPI image..."
    docker build -t $FASTAPI_IMAGE ./streaming || { error "FastAPI image build failed"; exit 1; }
else
    info "FastAPI image exists. Skipping build (use -r to rebuild)."
fi

# ── Shared env overrides for all Django-based containers ─────────────────────
# Container-internal URLs replace localhost with container names on the Docker network.
DB_URL_CONTAINER=$(grep "^DB_CONNECTION_STRING=" .env 2>/dev/null | cut -d= -f2- \
    | sed "s|localhost:[0-9]*|${PGBOUNCER_CONTAINER}:6432|g; \
           s|127\.0\.0\.1:[0-9]*|${PGBOUNCER_CONTAINER}:6432|g")
REDIS_INTERNAL="redis://${REDIS_CONTAINER}:6379"
CHROMA_HOST_CONTAINER=${CHROMA_HOST_CONTAINER:-$CHROMA_CONTAINER}
CHROMA_PORT_CONTAINER=${CHROMA_PORT_CONTAINER:-8000}

# Bash array so we don't repeat these 8 overrides on every docker run
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

# ── Django migrations ─────────────────────────────────────────────────────────
info "Running Django migrations..."
docker run --rm \
    --network $NETWORK_NAME \
    "${DJANGO_ENV[@]}" \
    -v "$(pwd)/storage:/app/storage" \
    $DJANGO_IMAGE python manage.py migrate || { error "Migrations failed"; exit 1; }

# ── Django ────────────────────────────────────────────────────────────────────
info "Starting Django..."
docker stop $DJANGO_CONTAINER 2>/dev/null || true
docker rm   $DJANGO_CONTAINER 2>/dev/null || true
docker run -d \
    --name $DJANGO_CONTAINER \
    --network $NETWORK_NAME \
    "${DJANGO_ENV[@]}" \
    -v "$(pwd):/app" \
    -p "${DJANGO_PORT}:${DJANGO_PORT}" \
    $DJANGO_IMAGE python manage.py runserver "0.0.0.0:${DJANGO_PORT}" \
    || { error "Django failed to start"; exit 1; }
success "Django ready."

# ── Celery worker & beat ──────────────────────────────────────────────────────
run_celery_container() {
    local name=$1; shift
    docker stop $name 2>/dev/null || true
    docker rm   $name 2>/dev/null || true
    docker run -d \
        --name $name \
        --network $NETWORK_NAME \
        "${DJANGO_ENV[@]}" \
        -v "$(pwd):/app" \
        $DJANGO_IMAGE "$@"
}

info "Starting Celery worker..."
run_celery_container $WORKER_CONTAINER \
    celery -A api.celery worker --pool=gevent --loglevel=INFO \
    || { error "Celery worker failed to start"; exit 1; }
success "Celery worker ready."

info "Starting Celery beat..."
run_celery_container $BEAT_CONTAINER \
    celery -A api.celery beat --loglevel=INFO \
    || { error "Celery beat failed to start"; exit 1; }
success "Celery beat ready."

# ── Frontend build ────────────────────────────────────────────────────────────
PROJECT_ROOT=$(pwd)
cd ./streaming

if [ "$WATCH" = true ]; then
    info "Starting NPM watch..."
    npm run watch-build -q &
else
    info "Building frontend..."
    npm run build:all -q || { error "NPM build failed"; exit 1; }
fi

cd "$PROJECT_ROOT"

# ── FastAPI ───────────────────────────────────────────────────────────────────
info "Starting FastAPI..."
docker stop $FASTAPI_CONTAINER 2>/dev/null || true
docker rm   $FASTAPI_CONTAINER 2>/dev/null || true
docker run -d \
    --name $FASTAPI_CONTAINER \
    --network $NETWORK_NAME \
    --env-file .env \
    -e API_URL="http://${DJANGO_CONTAINER}:${DJANGO_PORT}" \
    -e FASTAPI_PORT=$FASTAPI_PORT \
    -e REDIS_HOST=$REDIS_CONTAINER \
    -e CELERY_BROKER_URL="${REDIS_INTERNAL}/0" \
    -e REDIS_NOTIFICATIONS_URL="${REDIS_INTERNAL}/2" \
    -v "${PROJECT_ROOT}/streaming:/app" \
    -p "${FASTAPI_PORT}:${FASTAPI_PORT}" \
    $FASTAPI_IMAGE python main.py || { error "FastAPI failed to start"; exit 1; }
success "FastAPI ready."

# ── Nginx ─────────────────────────────────────────────────────────────────────
# Single entry point — routes /v1/* and /admin/* to Django,
# /socket.io/* and everything else to FastAPI.
info "Starting Nginx..."
docker stop $NGINX_CONTAINER 2>/dev/null || true
docker rm   $NGINX_CONTAINER 2>/dev/null || true
docker run -d \
    --name $NGINX_CONTAINER \
    --network $NETWORK_NAME \
    -e DJANGO_CONTAINER=$DJANGO_CONTAINER \
    -e DJANGO_PORT=$DJANGO_PORT \
    -e FASTAPI_CONTAINER=$FASTAPI_CONTAINER \
    -e FASTAPI_PORT=$FASTAPI_PORT \
    -v "${PROJECT_ROOT}/nginx:/etc/nginx/templates" \
    -p "${NGINX_PORT}:80" \
    nginx:alpine || { error "Nginx failed to start"; exit 1; }
success "Nginx ready."

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "============================================"
success "All services are up!"
info "  App:     http://localhost:${NGINX_PORT}"
info "  Django:  http://localhost:${DJANGO_PORT}  ($DJANGO_CONTAINER)"
info "  FastAPI: http://localhost:${FASTAPI_PORT} ($FASTAPI_CONTAINER)"
info "  Worker:  $WORKER_CONTAINER"
info "  Beat:    $BEAT_CONTAINER"
info "Press Ctrl+C to stop everything."
echo "============================================"
echo ""

# ── Monitor ───────────────────────────────────────────────────────────────────
MONITORED=($DJANGO_CONTAINER $FASTAPI_CONTAINER $NGINX_CONTAINER $WORKER_CONTAINER $BEAT_CONTAINER)
while true; do
    for CONTAINER in "${MONITORED[@]}"; do
        if ! docker ps -q -f name="^${CONTAINER}$" | grep -q .; then
            error "Container '$CONTAINER' stopped unexpectedly."
            cleanup; exit 1
        fi
    done
    sleep 5
done
