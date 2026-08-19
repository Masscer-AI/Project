#!/bin/bash

# ── Helpers ───────────────────────────────────────────────────────────────────
error()   { echo -e "\033[31m$1\033[0m"; }
info()    { echo -e "\033[34m$1\033[0m"; }
success() { echo -e "\033[32m$1\033[0m"; }

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
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ -f .env ]]; then
    set -a; source .env; set +a
fi
# Prevent Git Bash from converting POSIX paths to Windows paths in Docker args
export MSYS_NO_PATHCONV=1

# ── Project paths ─────────────────────────────────────────────────────────────
if [[ -d "${PROJECT_ROOT}/server" ]]; then
    BACKEND_DIR="${PROJECT_ROOT}/server"
    BACKEND_CONTEXT_REL="server"
else
    BACKEND_DIR="${PROJECT_ROOT}"
    BACKEND_CONTEXT_REL="."
fi

BACKEND_DOCKERFILE="${BACKEND_DIR}/Dockerfile"
BACKEND_PYPROJECT="${BACKEND_DIR}/pyproject.toml"
BACKEND_UV_LOCK="${BACKEND_DIR}/uv.lock"
STREAMING_PYPROJECT="${PROJECT_ROOT}/streaming/pyproject.toml"
STREAMING_UV_LOCK="${PROJECT_ROOT}/streaming/uv.lock"

if [[ ! -f "$BACKEND_DOCKERFILE" ]]; then
    error "Backend Dockerfile not found at: $BACKEND_DOCKERFILE"; exit 1
fi

if [[ ! -f "$BACKEND_PYPROJECT" ]]; then
    error "Backend pyproject not found at: $BACKEND_PYPROJECT"; exit 1
fi

if [[ ! -f "$BACKEND_UV_LOCK" ]]; then
    error "Backend uv lockfile not found at: $BACKEND_UV_LOCK"; exit 1
fi

if [[ ! -f "$STREAMING_PYPROJECT" ]]; then
    error "Streaming pyproject not found at: $STREAMING_PYPROJECT"; exit 1
fi

if [[ ! -f "$STREAMING_UV_LOCK" ]]; then
    error "Streaming uv lockfile not found at: $STREAMING_UV_LOCK"; exit 1
fi

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
CHROMA_IMAGE=${CHROMA_IMAGE:-chromadb/chroma:1.5.2}
CHROMA_MODEL_CACHE_VOLUME=${CHROMA_MODEL_CACHE_VOLUME:-masscer-chroma-model-cache}
FASTAPI_CONTAINER=${FASTAPI_CONTAINER:-masscer-fastapi}
FASTAPI_IMAGE=${FASTAPI_IMAGE:-masscer-fastapi-img}
NGINX_CONTAINER=${NGINX_CONTAINER:-masscer-nginx}
DOZZLE_CONTAINER=${DOZZLE_CONTAINER:-masscer-dozzle}
DOZZLE_IMAGE=${DOZZLE_IMAGE:-amir20/dozzle:latest}
WORKER_CONTAINER=${WORKER_CONTAINER:-masscer-celery-worker}
BEAT_CONTAINER=${BEAT_CONTAINER:-masscer-celery-beat}
NETWORK_NAME=${NETWORK_NAME:-masscer-net}
LOGS_USERNAME=${LOGS_USERNAME:-admin}

success "Starting Masscer"
info "  DJANGO_PORT:  $DJANGO_PORT | FASTAPI_PORT: $FASTAPI_PORT | NGINX_PORT: $NGINX_PORT"
info "  REBUILD: $REBUILD | INSTALL: $INSTALL | WATCH: $WATCH"
info "  BACKEND_DIR: $BACKEND_DIR"
info "  BACKEND_CONTEXT: $BACKEND_CONTEXT_REL"

# ── Host tooling check ─────────────────────────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
    error "uv is required but not installed. Install from https://docs.astral.sh/uv/"; exit 1
fi

# ── PostgreSQL & PGBouncer ────────────────────────────────────────────────────
info "Starting PostgreSQL..."
if [[ "$(docker ps -aq -f name=$POSTGRES_CONTAINER)" ]]; then
    docker start $POSTGRES_CONTAINER || { error "Failed to start PostgreSQL"; exit 1; }
else
    error "PostgreSQL container not found. Run ./taskfile.sh postgres first."; exit 1
fi
success "PostgreSQL ready."

info "Starting PGBouncer..."
if [[ "$(docker ps -aq -f name=$PGBOUNCER_CONTAINER)" ]]; then
    docker start $PGBOUNCER_CONTAINER || { error "Failed to start PGBouncer"; exit 1; }
else
    error "PGBouncer container not found. Run ./taskfile.sh postgres first."; exit 1
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
    uv sync --project "$BACKEND_CONTEXT_REL" --frozen --no-dev || {
        error "Backend uv sync failed"; exit 1;
    }
    uv sync --project "streaming" --frozen --no-dev || {
        error "Streaming uv sync failed"; exit 1;
    }
    cd ./streaming
    npm i -q || { error "npm install failed"; exit 1; }
    cd ..
fi

# ── Chroma ────────────────────────────────────────────────────────────────────
# HOME=/data keeps any cache Chroma writes on the vector_storage volume instead
# of the ephemeral container FS. Note the ONNX embedding model is NOT downloaded
# here: the chromadb client embeds in-process, so the model lives in the Django
# and Celery containers (see CHROMA_MODEL_CACHE_VOLUME below).
info "Starting Chroma..."
mkdir -p "${PROJECT_ROOT}/vector_storage"

if [ "$REBUILD" = true ]; then
    info "Rebuild mode: refreshing Chroma image/container..."
    docker pull "$CHROMA_IMAGE" || { error "Failed to pull Chroma image"; exit 1; }
    docker stop $CHROMA_CONTAINER 2>/dev/null || true
    docker rm $CHROMA_CONTAINER 2>/dev/null || true
elif [[ "$(docker ps -aq -f name=$CHROMA_CONTAINER)" ]]; then
    # Recreate if an older container lacks the persistent model-cache HOME.
    CHROMA_HOME=$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$CHROMA_CONTAINER" 2>/dev/null | grep '^HOME=' || true)
    if [ "$CHROMA_HOME" != "HOME=/data" ]; then
        info "Recreating Chroma container to persist ONNX model cache on /data..."
        docker stop $CHROMA_CONTAINER 2>/dev/null || true
        docker rm $CHROMA_CONTAINER 2>/dev/null || true
    fi
fi

if [[ "$(docker ps -aq -f name=$CHROMA_CONTAINER)" ]]; then
    docker start $CHROMA_CONTAINER || { error "Failed to start Chroma"; exit 1; }
else
    docker run -d \
        --name $CHROMA_CONTAINER \
        -e HOME=/data \
        -v "${PROJECT_ROOT}/vector_storage:/data" \
        -p "8002:8000" \
        "$CHROMA_IMAGE" || { error "Failed to create Chroma container"; exit 1; }
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
    docker build -t $DJANGO_IMAGE -f "${BACKEND_CONTEXT_REL}/Dockerfile" "${BACKEND_CONTEXT_REL}" \
        || { error "Django image build failed"; exit 1; }
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

# Shared cache for Chroma's ONNX embedding model. The image ships it under
# /root/.cache/chroma; the volume keeps it across image rebuilds so a cold build
# never re-downloads the ~80MB model.
docker volume create "$CHROMA_MODEL_CACHE_VOLUME" >/dev/null \
    || { error "Failed to create Chroma model cache volume"; exit 1; }

# Bash array so we don't repeat these 8 overrides on every docker run
DJANGO_ENV=(
    --env-file .env
    -e DB_CONNECTION_STRING="$DB_URL_CONTAINER"
    -e CELERY_BROKER_URL="${REDIS_INTERNAL}/0"
    -e CELERY_RESULT_BACKEND=django-db
    -e REDIS_CACHE_URL="${REDIS_INTERNAL}/1"
    -e REDIS_NOTIFICATIONS_URL="${REDIS_INTERNAL}/2"
    -e MEDIA_ROOT=/app/storage
    -e CHROMA_HOST="$CHROMA_HOST_CONTAINER"
    -e CHROMA_PORT="$CHROMA_PORT_CONTAINER"
    -e INTERNAL_MCP_INTROSPECT_TOKEN="${INTERNAL_MCP_INTROSPECT_TOKEN:-}"
)

DJANGO_MOUNTS=(
    -v "${BACKEND_DIR}:/app"
    -v "${PROJECT_ROOT}/storage:/app/storage"
    -v "${CHROMA_MODEL_CACHE_VOLUME}:/root/.cache/chroma"
)

run_django_manage_oneoff() {
    docker run --rm \
        --network $NETWORK_NAME \
        "${DJANGO_ENV[@]}" \
        "${DJANGO_MOUNTS[@]}" \
        $DJANGO_IMAGE python manage.py "$@"
}

# ── Django static files ───────────────────────────────────────────────────────
info "Collecting Django static files..."
docker run --rm \
    --network $NETWORK_NAME \
    "${DJANGO_ENV[@]}" \
    "${DJANGO_MOUNTS[@]}" \
    $DJANGO_IMAGE python manage.py collectstatic --noinput || { error "Collectstatic failed"; exit 1; }

# ── Django ────────────────────────────────────────────────────────────────────
info "Starting Django..."
docker stop $DJANGO_CONTAINER 2>/dev/null || true
docker rm   $DJANGO_CONTAINER 2>/dev/null || true
docker run -d \
    --name $DJANGO_CONTAINER \
    --network $NETWORK_NAME \
    "${DJANGO_ENV[@]}" \
    "${DJANGO_MOUNTS[@]}" \
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
        "${DJANGO_MOUNTS[@]}" \
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
    -e INTERNAL_MCP_INTROSPECT_TOKEN="${INTERNAL_MCP_INTROSPECT_TOKEN:-}" \
    -v "${PROJECT_ROOT}/streaming:/app" \
    -p "${FASTAPI_PORT}:${FASTAPI_PORT}" \
    $FASTAPI_IMAGE sh -c 'uv sync --frozen --no-dev --no-install-project && exec python main.py' \
    || { error "FastAPI failed to start"; exit 1; }
success "FastAPI ready."

# ── Dozzle (local Docker logs UI) ─────────────────────────────────────────────
# Served only via nginx Host: logs.localhost — no host port publish.
if [[ -z "${LOGS_PASSWORD:-}" ]]; then
    error "LOGS_PASSWORD is required in .env for the local logs UI (http://logs.localhost)."; exit 1
fi
info "Starting Dozzle..."
mkdir -p "${PROJECT_ROOT}/.dozzle"
docker run --rm "$DOZZLE_IMAGE" generate "$LOGS_USERNAME" \
    --password "$LOGS_PASSWORD" \
    --name "$LOGS_USERNAME" \
    > "${PROJECT_ROOT}/.dozzle/users.yml" \
    || { error "Failed to generate Dozzle users.yml"; exit 1; }
docker stop $DOZZLE_CONTAINER 2>/dev/null || true
docker rm   $DOZZLE_CONTAINER 2>/dev/null || true
docker run -d \
    --name $DOZZLE_CONTAINER \
    --network $NETWORK_NAME \
    -e DOZZLE_AUTH_PROVIDER=simple \
    -e DOZZLE_NO_ANALYTICS=true \
    -v /var/run/docker.sock:/var/run/docker.sock:ro \
    -v "${PROJECT_ROOT}/.dozzle:/data" \
    $DOZZLE_IMAGE \
    || { error "Dozzle failed to start"; exit 1; }
success "Dozzle ready."

# ── Nginx ─────────────────────────────────────────────────────────────────────
# Single entry point — routes /v1/* and /admin/* to Django,
# /socket.io/* and everything else to FastAPI; logs.localhost → Dozzle.
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
    -e DOZZLE_CONTAINER=$DOZZLE_CONTAINER \
    -e NGINX_ENVSUBST_FILTER='DJANGO_|FASTAPI_|DOZZLE_' \
    -v "${PROJECT_ROOT}/nginx:/etc/nginx/templates" \
    -p "${NGINX_PORT}:80" \
    nginx:alpine || { error "Nginx failed to start"; exit 1; }
success "Nginx ready."

# ── Summary ───────────────────────────────────────────────────────────────────
if [[ "$NGINX_PORT" == "80" ]]; then
    LOGS_URL="http://logs.localhost"
    APP_URL="http://localhost"
else
    LOGS_URL="http://logs.localhost:${NGINX_PORT}"
    APP_URL="http://localhost:${NGINX_PORT}"
fi
echo ""
echo "============================================"
success "All services are up!"
info "  App:     $APP_URL"
info "  Logs:    $LOGS_URL  (user: $LOGS_USERNAME)"
info "  Django:  http://localhost:${DJANGO_PORT}  ($DJANGO_CONTAINER)"
info "  FastAPI: http://localhost:${FASTAPI_PORT} ($FASTAPI_CONTAINER)"
info "  Worker:  $WORKER_CONTAINER"
info "  Beat:    $BEAT_CONTAINER"
echo "============================================"
echo ""

# ── Post-start maintenance ────────────────────────────────────────────────────
info "Running Django migrations..."
run_django_manage_oneoff migrate || { error "Migrations failed"; exit 1; }

info "Syncing system data..."
run_django_manage_oneoff sync_system_data || {
    error "sync_system_data failed"; exit 1;
}

success "Startup completed. Services are running in background."
exit 0
