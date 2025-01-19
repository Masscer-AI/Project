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
    kill $CHROMA_PID $DJANGO_PID 2>/dev/null
    info "Cleanup complete."
}
trap cleanup EXIT

# Default values for the flags
DJANGO=true
INSTALL=true
WATCH=false  

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
        *) error "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# Show the flags
success "Starting with flags:"
info "DJANGO: $DJANGO"
info "INSTALL: $INSTALL"
info "WATCH: $WATCH"


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


# Execute installation commands if the flag is true
if [ "$INSTALL" = true ]; then
    git pull
    pip install -r requirements.txt || { error "Pip install failed"; exit 1; }
    cd ./streaming
    npm i || { error "NPM install failed"; exit 1; }
    cd ..  # Go back to the previous directory
fi

# Start Chroma service
info "Starting Chroma service..."
chroma run --path vector_storage/ --port 8002 &
CHROMA_PID=$!
sleep 2
if ! kill -0 $CHROMA_PID 2>/dev/null; then
    error "Chroma service failed to start."; exit 1
fi

# Run Django application if the flag is true
if [ "$DJANGO" = true ]; then
    info "Running Django migrations and server..."
    python manage.py migrate || { error "Django migration failed"; exit 1; }
    python manage.py runserver &
    DJANGO_PID=$!
fi

cd ./streaming 

# Check the WATCH flag and execute the appropriate npm command
if [ "$WATCH" = true ]; then
    info "Running NPM watch-build..."
    npm run watch-build &
else
    info "Building client with NPM..."
    npm run build || { error "NPM build failed"; exit 1; }
fi

# Wait a moment to ensure services are ready
sleep 6

# Run FastAPI application
info "Starting FastAPI..."
python main.py || { error "FastAPI failed to start"; exit 1; }

info "All services are up and running!"
