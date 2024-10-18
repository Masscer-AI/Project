#!/bin/bash

# Default values for the flags
DJANGO=true
INSTALL=false

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -d|--django) DJANGO="$2"; shift ;;
        -i|--install) INSTALL=true ;;  # New flag for installation
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

source venv/Scripts/activate

# Execute installation commands if the flag is true
if [ "$INSTALL" = true ]; then
    git pull
    pip install -r requirements.txt
    cd ./streaming
    npm i
    cd ..  # Go back to the previous directory
fi

# Run Django application if the flag is true
if [ "$DJANGO" = true ]; then
    python manage.py migrate
    python manage.py runserver &
fi

cd ./streaming 

# Run npm watch-build in the background
npm run watch-build &

# Wait for 6 seconds to build the client
sleep 6

# Run FastAPI application
python main.py
