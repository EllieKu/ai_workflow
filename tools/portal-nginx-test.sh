#!/usr/bin/env bash

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PORTAL_DIR="$PROJECT_DIR/dify-portal"
DIFY_DOCKER_DIR="$PROJECT_DIR/dify/docker"
OVERRIDE_FILE="$SCRIPT_DIR/dify-compose.portal-nginx.yaml"
AUTH_SECRET_FILE="$PORTAL_DIR/.portal-auth-secret"
DJANGO_SECRET_FILE="$PORTAL_DIR/.secret-key"
PORTAL_DB="$PORTAL_DIR/data/db.sqlite3"
BACKUP_DIR="$PORTAL_DIR/backups"

usage() {
    cat <<EOF
Usage: $0 <command>

Daily commands:
  start          Back up Portal SQLite, then build and start Dify with Portal
  status         Show Portal and Nginx service status
  logs           Show the latest Portal and Nginx logs

Maintenance commands:
  check          Validate required files and the merged Compose configuration
  reload-nginx   Recreate Dify Nginx after changing its template
  rollback       Stop Portal and restore the original Dify Nginx configuration
EOF
}

ensure_files() {
    if [[ ! -f "$DJANGO_SECRET_FILE" ]]; then
        echo "ERROR: missing $DJANGO_SECRET_FILE"
        exit 1
    fi
    if [[ ! -f "$PORTAL_DB" ]]; then
        echo "ERROR: missing $PORTAL_DB"
        exit 1
    fi
    if [[ ! -x "$PORTAL_DIR/.venv/bin/python" ]]; then
        echo "ERROR: missing Portal virtual environment"
        exit 1
    fi
}

ensure_auth_secret() {
    if [[ ! -f "$AUTH_SECRET_FILE" ]]; then
        openssl rand -hex 32 > "$AUTH_SECRET_FILE"
        chmod 600 "$AUTH_SECRET_FILE"
        echo "Created local auth secret: $AUTH_SECRET_FILE"
    fi
    DIFY_AUTH_REQUEST_SECRET="$(<"$AUTH_SECRET_FILE")"
    if [[ ${#DIFY_AUTH_REQUEST_SECRET} -lt 32 ]]; then
        echo "ERROR: Portal auth secret must contain at least 32 characters"
        exit 1
    fi
    export DIFY_AUTH_REQUEST_SECRET
}

compose_with_portal() {
    (
        cd "$DIFY_DOCKER_DIR"
        docker compose -f docker-compose.yaml -f "$OVERRIDE_FILE" "$@"
    )
}

compose_base() {
    (
        cd "$DIFY_DOCKER_DIR"
        docker compose -f docker-compose.yaml "$@"
    )
}

backup_database() {
    mkdir -p "$BACKUP_DIR"
    backup_path="$BACKUP_DIR/db-$(date +%Y%m%d-%H%M%S).sqlite3"
    "$PORTAL_DIR/.venv/bin/python" - "$PORTAL_DB" "$backup_path" <<'PY'
import sqlite3
import sys

source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect(sys.argv[2])
try:
    source.backup(target)
finally:
    target.close()
    source.close()
PY
    chmod 600 "$backup_path"
    echo "Created SQLite backup: $backup_path"
}

command="${1:-}"
case "$command" in
    start)
        ensure_files
        ensure_auth_secret
        backup_database
        compose_with_portal config --quiet
        compose_with_portal up -d --build
        compose_with_portal ps portal nginx
        ;;
    check)
        ensure_files
        ensure_auth_secret
        compose_with_portal config --quiet
        echo "Compose configuration is valid."
        ;;
    status)
        ensure_auth_secret
        compose_with_portal ps portal nginx
        ;;
    logs)
        ensure_auth_secret
        compose_with_portal logs --tail 160 portal nginx
        ;;
    reload-nginx)
        ensure_auth_secret
        compose_with_portal config --quiet
        compose_with_portal up -d --no-deps --force-recreate nginx
        compose_with_portal ps nginx
        ;;
    rollback)
        ensure_auth_secret
        compose_with_portal stop portal
        compose_base up -d --no-deps --force-recreate nginx
        compose_base ps nginx
        ;;
    *)
        usage
        exit 2
        ;;
esac
