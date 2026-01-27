#!/bin/bash

# Load .env if present
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

REDIS_PORT=${REDIS_PORT:-6379}
REDIS_CONTAINER=${REDIS_CONTAINER:-redis-instance}

# Check if the container exists and start it if it does
if [[ "$(docker ps -a -q -f name=$REDIS_CONTAINER)" ]]; then
    echo "Starting existing Redis container ($REDIS_CONTAINER) on port $REDIS_PORT..."
    docker start $REDIS_CONTAINER
else
    echo "Running a new Redis container on port $REDIS_PORT..."
    docker run --name $REDIS_CONTAINER -d -p "${REDIS_PORT}:6379" redis:alpine
fi

# Activate the virtual environment
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Error: Virtual environment not found"
    exit 1
fi

sleep 3

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "Stopping Celery worker and beat..."
    if [ ! -z "$WORKER_PID" ]; then
        kill $WORKER_PID 2>/dev/null || true
    fi
    if [ ! -z "$BEAT_PID" ]; then
        kill $BEAT_PID 2>/dev/null || true
    fi
}
trap 'cleanup; exit 0' SIGINT SIGTERM
trap cleanup EXIT

# Run the Celery worker in background
echo "Starting Celery worker..."
celery -A api.celery worker --pool=gevent --loglevel=INFO &
WORKER_PID=$!

# Give worker a moment to start
sleep 2

# Run Celery Beat in background
echo "Starting Celery Beat..."
celery -A api.celery beat --loglevel=INFO &
BEAT_PID=$!

echo ""
echo "=========================================="
echo "Celery worker (PID: $WORKER_PID) and Beat (PID: $BEAT_PID) are running..."
echo "Press Ctrl+C to stop both processes"
echo "=========================================="
echo ""

# Keep script running and monitor processes
while true; do
    # Check if worker is still running
    if ! kill -0 $WORKER_PID 2>/dev/null; then
        echo "Error: Celery worker process died"
        cleanup
        exit 1
    fi
    
    # Check if beat is still running
    if ! kill -0 $BEAT_PID 2>/dev/null; then
        echo "Error: Celery Beat process died"
        cleanup
        exit 1
    fi
    
    sleep 5
done

# Run the Celery Flower
# celery -A api.celery flower --port=5555
