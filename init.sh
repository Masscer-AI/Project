#!/bin/bash

# Default value for the Django flag
DJANGO=true

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -d|--django) DJANGO="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

source venv/Scripts/activate

# Run Django application if the flag is true
if [ "$DJANGO" = true ]; then
    python manage.py runserver &
fi

cd ./streaming 

# Run npm watch-build in the background
npm run watch-build &

# Wait for 6 seconds to build the client
sleep 6

# Run FastAPI application
python main.py
