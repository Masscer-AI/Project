#!/bin/bash

docker run --name redis-instance -d -p 6379:6379 redis

docker start redis-instance
# Activate the virtual environment
source venv/Scripts/activate

# Run the Celery worker
celery -A api.celery worker --pool=gevent --loglevel=INFO &

celery -A api.celery flower --port=5555