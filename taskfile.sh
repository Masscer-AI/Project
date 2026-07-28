#!/bin/bash

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

usage() {
  echo "Usage:"
  echo "  ./taskfile.sh run [run-flags]"
  echo "  ./taskfile.sh off"
  echo "  ./taskfile.sh postgres [postgres-flags]"
  echo "  ./taskfile.sh migrate [migrate-flags]"
  echo "  ./taskfile.sh migrate_structure [--dry-run]"
  echo "  ./taskfile.sh test [app_label|test_path ...] [django-test-flags]"
  echo "  ./taskfile.sh front"
  echo "  ./taskfile.sh shell"
  echo "  ./taskfile.sh autoupload \"commit message\""
  echo ""
  echo "Examples:"
  echo "  ./taskfile.sh run -r"
  echo "  ./taskfile.sh off"
  echo "  ./taskfile.sh postgres -u user -p pass -d dbname"
  echo "  ./taskfile.sh migrate"
  echo "  ./taskfile.sh migrate_structure --dry-run"
  echo "  ./taskfile.sh test"
  echo "  ./taskfile.sh test api.document_templates"
  echo "  ./taskfile.sh test api.document_templates.tests.DocumentTemplateAPITests.test_assignment_and_render_creates_attachment"
  echo "  ./taskfile.sh test api.foo --keepdb   # reuse test DB (skips CREATE; fastest iteration)"
  echo ""
  echo "  Note: 'test' requires DB_DIRECT_CONNECTION_STRING in .env (direct Postgres, not PgBouncer)."
  echo "  Note: 'test' appends --noinput unless you pass --keepdb or --noinput, so a leftover"
  echo "        test_* database is dropped automatically instead of failing on CREATE."
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
  off)
    exec bash "./scripts/off.sh" "$@"
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
  test)
    if [[ -f .env ]]; then
      set -a; source .env; set +a
    fi
    if [[ -z "${DB_DIRECT_CONNECTION_STRING:-}" ]]; then
      echo "error: DB_DIRECT_CONNECTION_STRING is required for tests (direct Postgres, not PgBouncer)." >&2
      echo "Add it to .env — see .env.example. Django must CREATE/DROP test_* databases." >&2
      exit 1
    fi
    # If test_mydatabase (or similar) already exists, Django otherwise prompts or errors on CREATE.
    # --noinput lets Django drop a stale test DB first. Skip when the caller passes --keepdb (reuse)
    # or already passes --noinput.
    TEST_ARGS=("$@")
    _has_test_db_flag=0
    for _a in "${TEST_ARGS[@]}"; do
      if [[ "$_a" == "--noinput" || "$_a" == "--keepdb" ]]; then
        _has_test_db_flag=1
        break
      fi
    done
    if [[ $_has_test_db_flag -eq 0 ]]; then
      TEST_ARGS+=(--noinput)
    fi
    DJANGO_CONTAINER=${DJANGO_CONTAINER:-masscer-django}
    POSTGRES_CONTAINER=${POSTGRES_CONTAINER:-postgres_container}
    if docker ps -q -f name="^${DJANGO_CONTAINER}$" | grep -q .; then
      # Bypass PgBouncer: rewrite host URL to the Postgres container on the Docker network.
      DB_URL_TEST=$(echo "$DB_DIRECT_CONNECTION_STRING" | sed \
        -e "s|localhost:[0-9]*|${POSTGRES_CONTAINER}:5432|g" \
        -e "s|127\.0\.0\.1:[0-9]*|${POSTGRES_CONTAINER}:5432|g" \
        -e "s|pgbouncer_container:6432|${POSTGRES_CONTAINER}:5432|g")
      exec docker exec -e DB_CONNECTION_STRING="$DB_URL_TEST" \
        "$DJANGO_CONTAINER" python manage.py test "${TEST_ARGS[@]}"
    fi

    if [[ -d "./server" ]]; then
      cd "./server"
    fi
    exec env DB_CONNECTION_STRING="$DB_DIRECT_CONNECTION_STRING" \
      uv run python manage.py test "${TEST_ARGS[@]}"
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
