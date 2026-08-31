#!/usr/bin/env bash
#
# Resets the password for an existing Lead CRM user directly in the
# database, using the exact same bcrypt hashing the app uses. Useful
# when you can't log in with a bootstrap password that was printed by
# install_ubuntu22.sh but doesn't match what's actually stored (this
# happens if the admin account was already created by an earlier run -
# the bootstrap admin is only ever created once, the first time the
# app starts against an empty users table; re-running the install
# script afterwards prints a new password but can't apply it).
#
# Usage:
#   sudo bash deploy/reset_admin_password.sh [username] [new-password]
#
# With no arguments, resets 'admin' and generates a random password.
# Run as root (needs to read /opt/leadcrm/backend/.env and use its venv).
#
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run this script as root (e.g. with sudo)." >&2
  exit 1
fi

INSTALL_DIR="/opt/leadcrm"
ENV_FILE="${INSTALL_DIR}/backend/.env"
VENV_PY="${INSTALL_DIR}/backend/venv/bin/python3"
USERNAME="${1:-admin}"
NEW_PASSWORD="${2:-$(openssl rand -base64 12 | tr -d '=+/')}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Is Lead CRM installed at $INSTALL_DIR?" >&2
  exit 1
fi
if [[ ! -x "$VENV_PY" ]]; then
  echo "ERROR: $VENV_PY not found. Is the backend venv installed?" >&2
  exit 1
fi

DATABASE_URL="$(grep '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2-)"
if [[ -z "$DATABASE_URL" ]]; then
  echo "ERROR: DATABASE_URL not set in $ENV_FILE" >&2
  exit 1
fi

# Compute the bcrypt hash using the app's own hashing function, so the
# result is guaranteed compatible with its login check.
HASHED="$("$VENV_PY" - "$NEW_PASSWORD" <<'PYEOF'
import sys
sys.path.insert(0, "/opt/leadcrm/backend")
from app.utils.security import hash_password
print(hash_password(sys.argv[1]))
PYEOF
)"

cd /tmp
UPDATED="$("$VENV_PY" - "$DATABASE_URL" "$USERNAME" "$HASHED" <<'PYEOF'
import sys
from sqlalchemy import create_engine, text

database_url, username, hashed = sys.argv[1], sys.argv[2], sys.argv[3]
engine = create_engine(database_url)
with engine.begin() as conn:
    result = conn.execute(
        text("UPDATE users SET hashed_password = :hashed, is_active = true WHERE username = :username"),
        {"hashed": hashed, "username": username},
    )
    print(result.rowcount)
PYEOF
)"

if [[ "$UPDATED" != "1" ]]; then
  echo "ERROR: no user named '${USERNAME}' was found (0 rows updated). Check the username and try again." >&2
  exit 1
fi

echo
echo "=================================================================="
echo " Password reset for user '${USERNAME}'."
echo
echo "   username: ${USERNAME}"
echo "   password: ${NEW_PASSWORD}"
echo
echo " Log in and change this password from the Users screen if you'd"
echo " like something more memorable."
echo "=================================================================="
