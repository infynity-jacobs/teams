#!/usr/bin/env bash
#
# Safely upgrades an existing Lead CRM installation in /opt/leadcrm.
# Run this script from the root of the new Lead CRM package:
#   sudo bash deploy/upgrade_ubuntu22.sh
#
# It preserves backend/.env, the PostgreSQL database, uploads, and Nginx
# customizations while installing the new application code and migrations.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run this script as root (e.g. with sudo)." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="/opt/leadcrm"
ENV_FILE="${INSTALL_DIR}/backend/.env"

cd /tmp

if [[ ! -d "$INSTALL_DIR/backend" || ! -f "$ENV_FILE" ]]; then
  echo "ERROR: Existing Lead CRM installation not found at $INSTALL_DIR" >&2
  echo "Use deploy/install_ubuntu22.sh for a fresh installation." >&2
  exit 1
fi

if [[ ! -f "$PROJECT_ROOT/backend/requirements.txt" || ! -d "$PROJECT_ROOT/frontend" || ! -d "$PROJECT_ROOT/deploy/migrations" ]]; then
  echo "ERROR: Run this script from the root of the complete Lead CRM v2 package." >&2
  exit 1
fi

echo "== 1/7: Checking required system tools =="
for cmd in rsync python3; do
  command -v "$cmd" >/dev/null || { echo "ERROR: $cmd is not installed." >&2; exit 1; }
done

systemctl stop leadcrm-backend || true

echo "== 2/7: Backing up application configuration =="
BACKUP_DIR="/var/backups/leadcrm"
mkdir -p "$BACKUP_DIR"
cp -a "$ENV_FILE" "$BACKUP_DIR/backend.env.$(date +%Y%m%d%H%M%S)"

# Keep .env out of --delete operations. Uploads are intentionally outside
# the backend/frontend sync trees and are therefore preserved.
echo "== 3/7: Installing application files =="
mkdir -p "$INSTALL_DIR/backend" "$INSTALL_DIR/frontend" "$INSTALL_DIR/deploy"
rsync -a --delete \
  --exclude 'venv' \
  --exclude '__pycache__' \
  --exclude '*.db' \
  --exclude '.env' \
  "$PROJECT_ROOT/backend/" "$INSTALL_DIR/backend/"
rsync -a --delete "$PROJECT_ROOT/frontend/" "$INSTALL_DIR/frontend/"
rsync -a "$PROJECT_ROOT/deploy/" "$INSTALL_DIR/deploy/"
mkdir -p "$INSTALL_DIR/uploads"

chown -R leadcrm:leadcrm "$INSTALL_DIR"
chmod 600 "$ENV_FILE"

if [[ -x "$INSTALL_DIR/backend/venv/bin/pip" ]]; then
  echo "== 4/7: Updating Python dependencies =="
  "$INSTALL_DIR/backend/venv/bin/pip" install -r "$INSTALL_DIR/backend/requirements.txt"
else
  echo "ERROR: Python virtualenv not found at $INSTALL_DIR/backend/venv" >&2
  exit 1
fi

echo "== 5/7: Applying database migrations =="
bash "$INSTALL_DIR/deploy/migrate.sh"

echo "== 6/7: Installing service and refreshing backend =="
cp "$INSTALL_DIR/deploy/leadcrm-backend.service" /etc/systemd/system/leadcrm-backend.service
systemctl daemon-reload
systemctl enable leadcrm-backend
systemctl restart leadcrm-backend

sleep 2
if ! systemctl is-active --quiet leadcrm-backend; then
  echo "ERROR: Backend failed to start. Recent logs:" >&2
  journalctl -u leadcrm-backend -n 80 --no-pager >&2
  exit 1
fi

echo "== 7/7: Validating Nginx =="
if [[ -f "$INSTALL_DIR/deploy/nginx_leadcrm.conf" && ! -f /etc/nginx/sites-available/leadcrm ]]; then
  cp "$INSTALL_DIR/deploy/nginx_leadcrm.conf" /etc/nginx/sites-available/leadcrm
  ln -sf /etc/nginx/sites-available/leadcrm /etc/nginx/sites-enabled/leadcrm
fi
nginx -t
systemctl reload nginx

echo
echo "=================================================================="
echo " Lead CRM v2 upgrade completed successfully."
echo
echo " Application: $INSTALL_DIR"
echo " Backend:     systemctl status leadcrm-backend"
echo " Migrations:  $INSTALL_DIR/deploy/migrations"
echo " Backup:      $BACKUP_DIR"
echo "=================================================================="
