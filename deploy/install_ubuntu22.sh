#!/usr/bin/env bash
#
# Installs the Lead CRM application on a fresh Ubuntu 22.04 LTS server:
#   - System packages (Python 3, PostgreSQL, Nginx)
#   - A dedicated 'leadcrm' system user and /opt/leadcrm install directory
#   - A PostgreSQL database + role
#   - A Python virtualenv with the backend dependencies
#   - A systemd service for the backend
#   - An Nginx site serving the frontend and proxying /api to the backend
#
# Run as root (or with sudo) from the directory containing this script,
# with the 'backend' and 'frontend' folders as siblings, e.g.:
#
#   leadcrm/
#     backend/
#     frontend/
#     deploy/
#       install_ubuntu22.sh   <-- run this
#
#   sudo bash deploy/install_ubuntu22.sh
#
# Safe to re-run: if it fails partway through (e.g. Postgres wasn't ready
# yet), fix the underlying issue and run it again. It reuses an existing
# backend/.env if one is already in place instead of regenerating
# credentials, and it won't clobber a customized Nginx server_name.
#
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run this script as root (e.g. with sudo)." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="/opt/leadcrm"
DB_NAME="leadcrm"
DB_USER="leadcrm"
ENV_FILE="${INSTALL_DIR}/backend/.env"

# Resolve SCRIPT_DIR/PROJECT_ROOT (paths under your home directory, say)
# *before* changing directory, then move somewhere every system account
# (including 'postgres') can traverse. Without this, `sudo -u postgres`
# calls below fail with "could not change directory ... Permission
# denied" whenever this script is invoked from inside a locked-down
# home directory (the default on most Ubuntu installs).
cd /tmp

echo "== 1/8: Updating apt and installing system packages =="
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-venv python3-pip \
  postgresql postgresql-contrib \
  nginx \
  build-essential libpq-dev \
  openssl curl rsync \
  libcairo2

echo "== 2/8: Starting PostgreSQL and waiting for it to accept connections =="
systemctl enable --now postgresql

READY=0
for _ in $(seq 1 30); do
  if sudo -u postgres pg_isready -q; then
    READY=1
    break
  fi
  sleep 1
done
if [[ "$READY" -ne 1 ]]; then
  echo
  echo "ERROR: PostgreSQL did not become ready within 30 seconds." >&2
  echo "Check its status and logs, then re-run this script:" >&2
  echo "  sudo systemctl status postgresql --no-pager" >&2
  echo "  sudo journalctl -u postgresql -n 50 --no-pager" >&2
  exit 1
fi
echo "PostgreSQL is up."

echo "== 3/8: Creating system user and install directory =="
id -u leadcrm &>/dev/null || useradd --system --create-home --shell /usr/sbin/nologin leadcrm
mkdir -p "$INSTALL_DIR"
rsync -a --delete "$PROJECT_ROOT/backend/" "$INSTALL_DIR/backend/" --exclude venv --exclude '__pycache__' --exclude '*.db' --exclude '.env'
rsync -a --delete "$PROJECT_ROOT/frontend/" "$INSTALL_DIR/frontend/"
rsync -a "$PROJECT_ROOT/deploy/" "$INSTALL_DIR/deploy/"
echo "== 4/8: Setting up PostgreSQL database =="
# Reuse credentials from an existing .env (e.g. from a prior run of this
# script) so re-running never desyncs the Postgres role's actual password
# from what's written in the app config. Only generate fresh random
# credentials the first time.
if [[ -f "$ENV_FILE" ]] && grep -q '^DATABASE_URL=' "$ENV_FILE"; then
  echo "Existing backend/.env found - reusing its DB credentials and secret key."
  DB_PASSWORD="$(grep '^DATABASE_URL=' "$ENV_FILE" | sed -E 's#.*://[^:]+:([^@]+)@.*#\1#')"
  SECRET_KEY="$(grep '^SECRET_KEY=' "$ENV_FILE" | cut -d= -f2-)"
  REUSED_ENV=1
else
  DB_PASSWORD="$(openssl rand -hex 16)"
  SECRET_KEY="$(openssl rand -hex 32)"
  REUSED_ENV=0
fi

ROLE_EXISTS="$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'")"
if [[ "$ROLE_EXISTS" == "1" ]]; then
  # Role already exists (e.g. from a previous run) - make sure its
  # password matches what we're about to write into .env.
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "ALTER ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';"
else
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';"
fi

DB_EXISTS="$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'")"
if [[ "$DB_EXISTS" != "1" ]]; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
fi

echo "== 5/8: Creating Python virtual environment and installing dependencies =="
python3 -m venv "$INSTALL_DIR/backend/venv"
"$INSTALL_DIR/backend/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/backend/venv/bin/pip" install -r "$INSTALL_DIR/backend/requirements.txt"

echo "== 6/8: Writing environment configuration =="
if [[ "$REUSED_ENV" -eq 1 ]]; then
  echo "Keeping existing backend/.env as-is."
  BOOTSTRAP_PASSWORD="(unchanged - see your original install output, or reset it from the Users screen)"
else
  BOOTSTRAP_PASSWORD="$(openssl rand -base64 12 | tr -d '=+/')"
  cat > "$ENV_FILE" <<EOF
ENV=production
DATABASE_URL=postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=480
CORS_ORIGINS=*
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=${BOOTSTRAP_PASSWORD}
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
FRONTEND_DIR=${INSTALL_DIR}/frontend
UPLOAD_DIR=${INSTALL_DIR}/uploads
PASSWORD_RESET_EXPIRE_MINUTES=30
EOF
  chmod 600 "$ENV_FILE"
fi

echo "== 7/8: Initializing database schema, applying migrations, and starting service =="
chown -R leadcrm:leadcrm "$INSTALL_DIR"
cp "$SCRIPT_DIR/leadcrm-backend.service" /etc/systemd/system/leadcrm-backend.service
systemctl daemon-reload
systemctl enable leadcrm-backend
# First start lets SQLAlchemy create the initial schema on a brand-new DB.
# Migrations are then applied for upgrades/column/index changes and are idempotent.
systemctl restart leadcrm-backend
sleep 2
bash "$INSTALL_DIR/deploy/migrate.sh"
systemctl restart leadcrm-backend

echo "== 8/8: Installing service and configuring Nginx =="
if [[ -f /etc/nginx/sites-available/leadcrm ]]; then
  echo "Nginx site already exists at /etc/nginx/sites-available/leadcrm - leaving it untouched"
  echo "(so any server_name/TLS changes you made aren't overwritten)."
else
  cp "$SCRIPT_DIR/nginx_leadcrm.conf" /etc/nginx/sites-available/leadcrm
fi
ln -sf /etc/nginx/sites-available/leadcrm /etc/nginx/sites-enabled/leadcrm
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

sleep 2
echo
echo "=================================================================="
echo " Lead CRM installed."
echo
echo " App directory:      ${INSTALL_DIR}"
echo " Database:            ${DB_NAME} (user: ${DB_USER})"
if [[ "$REUSED_ENV" -eq 1 ]]; then
  echo " DB password:         (unchanged from previous install)"
else
  echo " DB password:         ${DB_PASSWORD}"
fi
echo " Backend service:     systemctl status leadcrm-backend"
echo " Nginx site:          /etc/nginx/sites-available/leadcrm"
echo
echo " Initial Super Admin login:"
echo "   username: admin"
echo "   password: ${BOOTSTRAP_PASSWORD}"
echo
echo " IMPORTANT:"
echo "  1. Edit /etc/nginx/sites-available/leadcrm and set server_name to"
echo "     your real domain, then set up HTTPS (e.g. 'sudo apt install"
echo "     certbot python3-certbot-nginx && sudo certbot --nginx')."
echo "  2. Log in as 'admin' above and change the password immediately."
echo "  3. The DB password and secret key are saved in"
echo "     ${ENV_FILE} - keep this file secure."
echo "=================================================================="
