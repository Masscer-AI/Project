#!/usr/bin/env bash
# exit on error

set -o errexit

git pull

python3 -m venv venv

source venv/Scripts/activate

pip install -r requirements.txt

python manage.py migrate

cp .env.example .env

cd ./streaming

npm i