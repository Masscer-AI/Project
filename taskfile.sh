#!/bin/bash

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

usage() {
  echo "Usage:"
  echo "  ./taskfile.sh run [run-flags]"
  echo "  ./taskfile.sh postgres [postgres-flags]"
  echo "  ./taskfile.sh migrate [migrate-flags]"
  echo "  ./taskfile.sh migrate_structure [--dry-run]"
  echo "  ./taskfile.sh front"
  echo "  ./taskfile.sh shell"
  echo "  ./taskfile.sh autoupload \"commit message\""
  echo ""
  echo "Examples:"
  echo "  ./taskfile.sh run -r"
  echo "  ./taskfile.sh postgres -u user -p pass -d dbname"
  echo "  ./taskfile.sh migrate"
  echo "  ./taskfile.sh migrate_structure --dry-run"
  echo "  ./taskfile.sh front"
  echo "  ./taskfile.sh shell"
  echo "  ./taskfile.sh autoupload \"chore: update scripts\""
}

COMMAND="${1:-}"
if [[ -z "$COMMAND" ]]; then
  usage
  exit 1
fi
shift

case "$COMMAND" in
  run)
    exec bash "./scripts/run.sh" "$@"
    ;;
  postgres)
    exec bash "./scripts/createPostgres.sh" "$@"
    ;;
  migrate)
    exec bash "./scripts/migrate.sh" "$@"
    ;;
  migrate_structure)
    exec bash "./scripts/migrate_structure.sh" "$@"
    ;;
  front)
    cd "./streaming/client"
    exec npm run build:all "$@"
    ;;
  shell)
    if [[ -f .env ]]; then
      set -a; source .env; set +a
    fi
    DJANGO_CONTAINER=${DJANGO_CONTAINER:-masscer-django}
    exec docker exec -it "$DJANGO_CONTAINER" bash "$@"
    ;;
  autoupload)
    exec bash "./scripts/autoUpload.sh" "$@"
    ;;
  *)
    echo "Unknown command: $COMMAND"
    usage
    exit 1
    ;;
esac
