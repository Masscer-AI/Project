#!/bin/bash

# Check if the container exists and start it if it does
if [ $(docker ps -a -q -f name=redis-instance) ]; then
    echo "Starting existing redis-instance container..."
    docker start redis-instance
else
    echo "Running a new Redis container..."
    docker run --name redis-instance -d -p 6379:6379 redis
fi

# Activate the virtual environment
source venv/Scripts/activate

# Run the Celery worker
celery -A api.celery worker --pool=gevent --loglevel=INFO &

# Run the Celery Flower
celery -A api.celery flower --port=5555
