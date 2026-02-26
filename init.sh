#!/bin/bash

# Functions
error() {
    echo -e "\033[31m$1\033[0m"  # Red
}
info() {
    echo -e "\033[34m$1\033[0m"  # Blue
}
success() {
    echo -e "\033[32m$1\033[0m"  # Green
}
cleanup() {
    info "Stopping background services..."
    kill $CHROMA_PID 2>/dev/null
    docker stop $DJANGO_CONTAINER 2>/dev/null
    info "Cleanup complete."
}
trap cleanup EXIT

# Default values for the flags
DJANGO=true
INSTALL=true
WATCH=false
REBUILD=false

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -d|--django) 
            if [[ -z "$2" ]]; then
                error "Error: Missing value for $1"; exit 1
            fi
            DJANGO="$2"; shift ;;
        -i|--install) INSTALL=false ;;
        -w|--watch)
            if [[ -z "$2" ]]; then
                error "Error: Missing value for $1"; exit 1
            fi
            WATCH="$2"; shift ;;
        -r|--rebuild) REBUILD=true ;;
        *) error "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# Show the flags
success "Starting with flags:"
info "DJANGO: $DJANGO"
info "INSTALL: $INSTALL"
info "WATCH: $WATCH"

# Load .env if present (so DJANGO_PORT, FASTAPI_PORT, etc. are available)
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

# Ports and Redis from env (defaults: Django 8000, FastAPI 8001, Redis 6379)
DJANGO_PORT=${DJANGO_PORT:-8000}
FASTAPI_PORT=${FASTAPI_PORT:-8001}
REDIS_PORT=${REDIS_PORT:-6379}
info "DJANGO_PORT: $DJANGO_PORT"
info "FASTAPI_PORT: $FASTAPI_PORT"
info "REDIS_PORT: $REDIS_PORT"

# Activate virtual environment
if [[ -f "venv/bin/activate" ]]; then
    source venv/bin/activate
elif [[ -f "venv/Scripts/activate" ]]; then
    source venv/Scripts/activate
else
    error "Virtual environment not found. Please set it up first. running: py -m venv venv"; exit 1
fi

# Start PostgreSQL container
POSTGRES_CONTAINER=${POSTGRES_CONTAINER:-postgres_container}
POSTGRES_HOST=${POSTGRES_HOST:-localhost}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
PGBOUNCER_CONTAINER=${PGBOUNCER_CONTAINER:-pgbouncer_container}
PGBOUNCER_HOST=${PGBOUNCER_HOST:-localhost}
PGBOUNCER_PORT=${PGBOUNCER_PORT:-6432}

info "Checking PostgreSQL container..."
if [[ "$(docker ps -aq -f name=$POSTGRES_CONTAINER)" ]]; then
    info "Starting existing PostgreSQL container..."
    docker start $POSTGRES_CONTAINER || { error "Failed to start PostgreSQL container. Make sure it exists and is not in an invalid state."; exit 1; }
else
    error "PostgreSQL container does not exist. Please create it first running: ./createPostgres.sh. Ask for help if you need it."
    exit 1
fi

info "PostgreSQL container started."
info "Starting PGBouncer container..."

if [[ "$(docker ps -aq -f name=$PGBOUNCER_CONTAINER)" ]]; then
    info "Starting existing PGBouncer container..."
    docker start $PGBOUNCER_CONTAINER || { error "Failed to start PGBouncer container. Make sure it exists and is not in an invalid state."; exit 1; }
    success "PGBouncer container started."
else
    error "PGBouncer container does not exist. Please create it first running: ./createPostgres.sh. Ask for help if you need it."
    exit 1
fi

# Start Redis container (FastAPI notifications, Celery)
REDIS_CONTAINER=${REDIS_CONTAINER:-redis-instance}
DJANGO_CONTAINER=${DJANGO_CONTAINER:-masscer-django}
DJANGO_IMAGE=${DJANGO_IMAGE:-masscer-django-img}
NETWORK_NAME=${NETWORK_NAME:-masscer-net}
info "Checking Redis container..."
if [[ "$(docker ps -aq -f name=$REDIS_CONTAINER)" ]]; then
    info "Starting existing Redis container on port $REDIS_PORT..."
    docker start $REDIS_CONTAINER || { error "Failed to start Redis container."; exit 1; }
    success "Redis container started."
else
    info "Creating and running Redis container on port $REDIS_PORT..."
    docker run --name $REDIS_CONTAINER -d -p "${REDIS_PORT}:6379" redis:alpine || { error "Failed to run Redis container."; exit 1; }
    success "Redis container started."
fi

# === DOCKER NETWORK ===
info "Setting up Docker network '$NETWORK_NAME'..."
if ! docker network ls --format '{{.Name}}' | grep -q "^${NETWORK_NAME}$"; then
    docker network create $NETWORK_NAME
    success "Network '$NETWORK_NAME' created."
else
    info "Network '$NETWORK_NAME' already exists."
fi

# Connect infrastructure containers to the shared network
for CONTAINER in $POSTGRES_CONTAINER $PGBOUNCER_CONTAINER $REDIS_CONTAINER; do
    if docker ps -q -f name="^${CONTAINER}$" | grep -q .; then
        if ! docker network inspect $NETWORK_NAME --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null | grep -qw "$CONTAINER"; then
            docker network connect $NETWORK_NAME $CONTAINER && success "Connected $CONTAINER to $NETWORK_NAME."
        else
            info "$CONTAINER already in $NETWORK_NAME."
        fi
    fi
done

# Execute installation commands if the flag is true
if [ "$INSTALL" = true ]; then
    git pull
    pip install -q -r requirements.txt || { error "Pip install failed"; exit 1; }
    cd ./streaming
    npm i -q || { error "NPM install failed"; exit 1; }
    cd ..  # Go back to the previous directory
fi

# Start Chroma service
info "Starting Chroma service..."
chroma run --path vector_storage/ --port 8002 &
CHROMA_PID=$!
sleep 4
if ! kill -0 $CHROMA_PID 2>/dev/null; then
    error "Chroma service failed to start."; exit 1
fi

# Run Django application if the flag is true
if [ "$DJANGO" = true ]; then
    # Inside the container, services are reachable by their container name on internal ports.
    # We derive those URLs from the .env ones by replacing localhost:<any-port> with the
    # container name and its internal port.
    DB_URL_CONTAINER=$(grep "^DB_CONNECTION_STRING=" .env 2>/dev/null | cut -d= -f2- \
        | sed "s|localhost:[0-9]*|${PGBOUNCER_CONTAINER}:6432|g; s|127\.0\.0\.1:[0-9]*|${PGBOUNCER_CONTAINER}:6432|g")
    REDIS_INTERNAL="redis://${REDIS_CONTAINER}:6379"

    if [ "$REBUILD" = true ] || ! docker image inspect $DJANGO_IMAGE &>/dev/null; then
        info "Building Django image '$DJANGO_IMAGE'..."
        docker build -t $DJANGO_IMAGE . || { error "Django image build failed"; exit 1; }
    else
        info "Django image '$DJANGO_IMAGE' already exists. Skipping build (use -r to rebuild)."
    fi

    info "Running Django migrations inside container..."
    docker run --rm \
        --network $NETWORK_NAME \
        --env-file .env \
        -e DB_CONNECTION_STRING="$DB_URL_CONTAINER" \
        -e CELERY_BROKER_URL="${REDIS_INTERNAL}/0" \
        -e CELERY_RESULT_BACKEND="${REDIS_INTERNAL}/0" \
        -e REDIS_CACHE_URL="${REDIS_INTERNAL}/1" \
        -e REDIS_NOTIFICATIONS_URL="${REDIS_INTERNAL}/2" \
        -e MEDIA_ROOT=/app/storage \
        -v "$(pwd)/storage:/app/storage" \
        $DJANGO_IMAGE python manage.py migrate || { error "Django migration failed"; exit 1; }

    info "Starting Django container on port $DJANGO_PORT..."
    docker stop $DJANGO_CONTAINER 2>/dev/null || true
    docker rm $DJANGO_CONTAINER 2>/dev/null || true
    docker run -d \
        --name $DJANGO_CONTAINER \
        --network $NETWORK_NAME \
        --env-file .env \
        -e DB_CONNECTION_STRING="$DB_URL_CONTAINER" \
        -e CELERY_BROKER_URL="${REDIS_INTERNAL}/0" \
        -e CELERY_RESULT_BACKEND="${REDIS_INTERNAL}/0" \
        -e REDIS_CACHE_URL="${REDIS_INTERNAL}/1" \
        -e REDIS_NOTIFICATIONS_URL="${REDIS_INTERNAL}/2" \
        -e MEDIA_ROOT=/app/storage \
        -v "$(pwd):/app" \
        -p "${DJANGO_PORT}:${DJANGO_PORT}" \
        $DJANGO_IMAGE python manage.py runserver "0.0.0.0:${DJANGO_PORT}" || { error "Django container failed to start"; exit 1; }
    success "Django container started on port $DJANGO_PORT."
fi

cd ./streaming 

# Check the WATCH flag and execute the appropriate npm command
if [ "$WATCH" = true ]; then
    info "Running NPM watch-build..."
    npm run watch-build -q &
else
    info "Building client and widget with NPM..."
    npm run build:all -q || { error "NPM build failed"; exit 1; }
fi

# Wait a moment to ensure services are ready
sleep 6

# Run FastAPI application (reads FASTAPI_PORT from env)
info "Starting FastAPI on port $FASTAPI_PORT..."
FASTAPI_PORT=$FASTAPI_PORT python main.py || { error "FastAPI failed to start"; exit 1; }

info "All services are up and running!"
