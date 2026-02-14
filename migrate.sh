#!/bin/bash
# Migrate script: activate venv (cross-OS), makemigrations, migrate
# Usage:
#   ./migrate.sh                    - makemigrations + migrate
#   ./migrate.sh <app> <migration>  - revert to migration (e.g. ./migrate.sh ai_layers 0021)
#   ./migrate.sh <app> zero         - unapply all migrations for app

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Activate venv (handles both Windows and Unix layout)
if [ -f "venv/Scripts/activate" ]; then
  source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
  source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
else
  echo "No venv found. Expected venv/ or .venv/"
  exit 1
fi

if [ $# -eq 0 ]; then
  echo "Running makemigrations..."
  python manage.py makemigrations
  echo "Running migrate..."
  python manage.py migrate
elif [ $# -eq 2 ]; then
  echo "Reverting $1 to migration $2..."
  python manage.py migrate "$1" "$2"
else
  echo "Usage:"
  echo "  ./migrate.sh                    # makemigrations + migrate"
  echo "  ./migrate.sh <app> <migration>  # revert (e.g. ./migrate.sh ai_layers 0021)"
  echo "  ./migrate.sh <app> zero         # unapply all for app"
  exit 1
fi

echo "Done."
