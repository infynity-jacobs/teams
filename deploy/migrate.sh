#!/usr/bin/env bash
#
# Applies any pending SQL migrations from deploy/migrations/ to the
# database configured in backend/.env, tracking what's already been
# applied in a schema_migrations table so each file only ever runs
# once - safe to re-run any time.
#
# Needed because this app creates its initial schema with
# SQLAlchemy's Base.metadata.create_all() on startup, which only
# creates tables that don't exist yet - it never alters an existing
# table to add a column. Any change to an existing table (new column,
# new index, etc.) needs a migration file here instead.
#
# Usage: sudo bash deploy/migrate.sh
#
set -euo pipefail
cd /tmp || exit 1

if [[ $EUID -ne 0 ]]; then
  echo "Please run this script as root (e.g. with sudo)." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/leadcrm"
ENV_FILE="${INSTALL_DIR}/backend/.env"
VENV_PY="${INSTALL_DIR}/backend/venv/bin/python3"
MIGRATIONS_DIR="${SCRIPT_DIR}/migrations"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Is Lead CRM installed at $INSTALL_DIR?" >&2
  exit 1
fi
if [[ ! -x "$VENV_PY" ]]; then
  echo "ERROR: $VENV_PY not found. Is the backend venv installed?" >&2
  exit 1
fi
if [[ ! -d "$MIGRATIONS_DIR" ]]; then
  echo "No migrations directory found at $MIGRATIONS_DIR - nothing to do."
  exit 0
fi

DATABASE_URL="$(grep '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2-)"
if [[ -z "$DATABASE_URL" ]]; then
  echo "ERROR: DATABASE_URL not set in $ENV_FILE" >&2
  exit 1
fi

read -r DB_USER DB_PASS DB_HOST DB_PORT DB_NAME <<PARSED
$("$VENV_PY" - "$DATABASE_URL" <<'PYEOF'
import sys
from urllib.parse import urlparse
u = urlparse(sys.argv[1].replace("postgresql+psycopg2", "postgresql", 1))
print(u.username, u.password, u.hostname, u.port or 5432, u.path.lstrip("/"))
PYEOF
)
PARSED

export PGPASSWORD="$DB_PASS"
PSQL=(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1)

if ! "${PSQL[@]}" -c "SELECT 1;" >/dev/null 2>&1; then
  echo "ERROR: could not connect to the database with the credentials in ${ENV_FILE}." >&2
  echo "Run 'sudo bash deploy/diagnose.sh' to check what's wrong first." >&2
  exit 1
fi

"${PSQL[@]}" -c "CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, applied_at timestamptz DEFAULT now());" >/dev/null

APPLIED=0
shopt -s nullglob
for f in "$MIGRATIONS_DIR"/*.sql; do
  version="$(basename "$f")"
  already="$("${PSQL[@]}" -tAc "SELECT 1 FROM schema_migrations WHERE version='${version}';")"
  if [[ "$already" == "1" ]]; then
    echo "SKIP   ${version} (already applied)"
    continue
  fi
  echo "APPLY  ${version}"
  "${PSQL[@]}" -f "$f"
  "${PSQL[@]}" -c "INSERT INTO schema_migrations (version) VALUES ('${version}');" >/dev/null
  APPLIED=$((APPLIED + 1))
done
shopt -u nullglob

echo
if [[ "$APPLIED" -eq 0 ]]; then
  echo "Database is up to date - no pending migrations."
else
  echo "Applied ${APPLIED} migration(s)."
  echo "Restart the backend to pick up any new tables (e.g. setting_options):"
  echo "  sudo systemctl restart leadcrm-backend"
fi
