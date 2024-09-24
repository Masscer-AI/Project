#!/bin/bash

source venv/Scripts/activate

# Run Django application
python manage.py runserver &

cd ./streaming 

# Run npm watch-build in the background
npm run watch-build &

# Wait for 4 seconds to build the client
sleep 4

# Run FastAPI application
python main.py
