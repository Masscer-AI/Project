#!/bin/bash

# Install Python requirements
pip install -r requirements.txt

# Install npm packages
cd streaming
npm install
cd ..

# Run Django server in one terminal
gnome-terminal -- bash -c "python manage.py runserver; exec bash"

# Run streaming script in another terminal
gnome-terminal -- bash -c "python streaming/main.py; exec bash"
