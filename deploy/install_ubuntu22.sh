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
DB_PASSWORD="$(openssl rand -hex 16)"
SECRET_KEY="$(openssl rand -hex 32)"

echo "== 1/8: Updating apt and installing system packages =="
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-venv python3-pip \
  postgresql postgresql-contrib \
  nginx \
  build-essential libpq-dev \
  openssl curl

echo "== 2/8: Creating system user and install directory =="
id -u leadcrm &>/dev/null || useradd --system --create-home --shell /usr/sbin/nologin leadcrm
mkdir -p "$INSTALL_DIR"
rsync -a --delete "$PROJECT_ROOT/backend/" "$INSTALL_DIR/backend/" --exclude venv --exclude '__pycache__' --exclude '*.db'
rsync -a --delete "$PROJECT_ROOT/frontend/" "$INSTALL_DIR/frontend/"

echo "== 3/8: Setting up PostgreSQL database =="
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

echo "== 4/8: Creating Python virtual environment and installing dependencies =="
python3 -m venv "$INSTALL_DIR/backend/venv"
"$INSTALL_DIR/backend/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/backend/venv/bin/pip" install -r "$INSTALL_DIR/backend/requirements.txt"

echo "== 5/8: Writing environment configuration =="
BOOTSTRAP_PASSWORD="$(openssl rand -base64 12 | tr -d '=+/')"
cat > "$INSTALL_DIR/backend/.env" <<EOF
ENV=production
DATABASE_URL=postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=480
CORS_ORIGINS=*
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=${BOOTSTRAP_PASSWORD}
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
FRONTEND_DIR=${INSTALL_DIR}/frontend
EOF
chmod 600 "$INSTALL_DIR/backend/.env"

echo "== 6/8: Setting file ownership =="
chown -R leadcrm:leadcrm "$INSTALL_DIR"

echo "== 7/8: Installing systemd service =="
cp "$SCRIPT_DIR/leadcrm-backend.service" /etc/systemd/system/leadcrm-backend.service
systemctl daemon-reload
systemctl enable leadcrm-backend
systemctl restart leadcrm-backend

echo "== 8/8: Configuring Nginx =="
cp "$SCRIPT_DIR/nginx_leadcrm.conf" /etc/nginx/sites-available/leadcrm
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
echo " DB password:         ${DB_PASSWORD}"
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
echo "     ${INSTALL_DIR}/backend/.env - keep this file secure."
echo "=================================================================="
