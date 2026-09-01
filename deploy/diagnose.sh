#!/usr/bin/env bash
#
# Diagnoses the most common causes of "the app doesn't work" after
# installing Lead CRM: checks PostgreSQL is running, that
# backend/.env's credentials actually authenticate against it, that
# the app has created its schema, and the backend systemd service's
# current status - then prints a specific fix for whatever it finds
# broken.
#
# Usage: sudo bash deploy/diagnose.sh
#
set -uo pipefail   # deliberately no -e: we want to run every check
                    # even if an earlier one fails, so run from a
                    # neutral directory rather than relying on set -e
                    # to stop us early.
cd /tmp || exit 1

if [[ $EUID -ne 0 ]]; then
  echo "Please run this script as root (e.g. with sudo)." >&2
  exit 1
fi

INSTALL_DIR="/opt/leadcrm"
ENV_FILE="${INSTALL_DIR}/backend/.env"
VENV_PY="${INSTALL_DIR}/backend/venv/bin/python3"
PROBLEMS=0

echo "== PostgreSQL service =="
if systemctl is-active --quiet postgresql; then
  echo "OK  postgresql.service is active"
else
  echo "FAIL  postgresql.service is NOT active"
  PROBLEMS=1
fi

if sudo -u postgres pg_isready -q 2>/dev/null; then
  echo "OK  PostgreSQL is accepting connections"
else
  echo "FAIL  PostgreSQL is NOT accepting connections"
  PROBLEMS=1
fi

echo
echo "== Lead CRM install =="
if [[ ! -f "$ENV_FILE" ]]; then
  echo "FAIL  ${ENV_FILE} not found - is the app installed at ${INSTALL_DIR}?"
  echo
  echo "Nothing more to check without a .env file. Run install_ubuntu22.sh first."
  exit 1
fi
echo "OK  ${ENV_FILE} exists"

if [[ ! -x "$VENV_PY" ]]; then
  echo "FAIL  ${VENV_PY} not found - backend venv is missing"
  PROBLEMS=1
  exit 1
fi
echo "OK  backend venv exists"

DATABASE_URL="$(grep '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2-)"
if [[ -z "$DATABASE_URL" ]]; then
  echo "FAIL  DATABASE_URL is not set in ${ENV_FILE}"
  PROBLEMS=1
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

echo
echo "== Testing DB connection using backend/.env credentials =="
echo "   (user=${DB_USER}, db=${DB_NAME}, host=${DB_HOST}:${DB_PORT})"
CONN_OK=0
if PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1;" >/dev/null 2>&1; then
  echo "OK  connected successfully"
  CONN_OK=1
else
  echo "FAIL  could not connect - the Postgres role's actual password does not match backend/.env"
  PROBLEMS=1
fi

TABLE_EXISTS=""
if [[ "$CONN_OK" -eq 1 ]]; then
  echo
  echo "== Checking the app's schema =="
  TABLE_EXISTS="$(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='users';")"
  if [[ "$TABLE_EXISTS" == "1" ]]; then
    USER_COUNT="$(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT count(*) FROM users;")"
    echo "OK  'users' table exists (${USER_COUNT} row(s))"
  else
    echo "FAIL  'users' table does not exist - the app has never successfully"
    echo "      started against this database"
    PROBLEMS=1
  fi
fi

echo
echo "== Backend service =="
if systemctl is-active --quiet leadcrm-backend; then
  echo "OK  leadcrm-backend.service is active"
else
  echo "FAIL  leadcrm-backend.service is NOT active"
  echo "      (systemd may still be restart-looping it - see logs below)"
  PROBLEMS=1
fi
echo "--- last 15 log lines ---"
journalctl -u leadcrm-backend -n 15 --no-pager 2>&1 | sed 's/^/    /'

if journalctl -u leadcrm-backend -n 50 --no-pager 2>&1 | grep -q "pydantic_core.*ValidationError\|extra_forbidden"; then
  echo
  echo "FAIL  found a pydantic ValidationError in recent logs - the backend is"
  echo "      crashing on startup due to an undeclared key in backend/.env"
  echo "      (this is fixed in current app/config.py; you're likely running"
  echo "      an older version - pull the latest code and restart)"
  PROBLEMS=1
fi

echo
echo "=================================================================="
if [[ "$PROBLEMS" -eq 0 ]]; then
  echo " Everything checks out. If login still fails, reset the admin"
  echo " password directly:"
  echo "   sudo bash deploy/reset_admin_password.sh"
elif [[ "$CONN_OK" -eq 0 ]]; then
  echo " DIAGNOSIS: the Postgres role's password doesn't match backend/.env."
  echo " Fix by resyncing it to what's already in .env, then restart:"
  echo
  echo "   sudo -u postgres psql -c \"ALTER ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASS}';\""
  echo "   sudo systemctl restart leadcrm-backend"
  echo
  echo " Then re-run this script to confirm the schema gets created."
elif [[ "$TABLE_EXISTS" != "1" ]]; then
  echo " DIAGNOSIS: credentials are fine but the schema was never created -"
  echo " the backend service isn't starting successfully. Check the log"
  echo " lines above for the actual error, or the full log with:"
  echo "   sudo journalctl -u leadcrm-backend -n 100 --no-pager"
else
  echo " DIAGNOSIS: see the FAIL line(s) above."
fi
echo "=================================================================="
