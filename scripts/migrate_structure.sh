#!/bin/bash

# Moves backend (Django/Celery) files into ./server in a safe, idempotent way.
# Usage:
#   ./migrate_structure.sh
#   ./migrate_structure.sh --dry-run

set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

SERVER_DIR="${PROJECT_ROOT}/server"

info() { echo -e "\033[34m$1\033[0m"; }
ok() { echo -e "\033[32m$1\033[0m"; }
warn() { echo -e "\033[33m$1\033[0m"; }

run_cmd() {
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "[dry-run] $*"
    else
        "$@"
    fi
}

move_path() {
    local src="$1"
    local dst="$2"

    if [[ ! -e "$src" ]]; then
        warn "Skip: missing ${src#$PROJECT_ROOT/}"
        return 0
    fi

    if [[ -e "$dst" ]]; then
        warn "Skip: destination already exists ${dst#$PROJECT_ROOT/}"
        return 0
    fi

    if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        run_cmd git mv "$src" "$dst"
    else
        run_cmd mv "$src" "$dst"
    fi

    ok "Moved ${src#$PROJECT_ROOT/} -> ${dst#$PROJECT_ROOT/}"
}

info "Preparing backend structure migration..."
run_cmd mkdir -p "$SERVER_DIR"

# Move Django backend runtime files.
move_path "${PROJECT_ROOT}/api" "${SERVER_DIR}/api"
move_path "${PROJECT_ROOT}/manage.py" "${SERVER_DIR}/manage.py"
move_path "${PROJECT_ROOT}/requirements.txt" "${SERVER_DIR}/requirements.txt"
move_path "${PROJECT_ROOT}/Dockerfile" "${SERVER_DIR}/Dockerfile"

echo ""
ok "Migration script finished."
info "Next steps:"
echo "  1) Review git diff/status."
echo "  2) Run ./taskfile.sh run -r"
echo "  3) Validate Django/FastAPI/Celery/Chroma services."
