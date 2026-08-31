# Lead CRM — Marketing Lead Management & Conversion Application

A web-based CRM for managing marketing leads through their full lifecycle:
capture (manual or Excel import) → assignment → follow-up → conversion,
with role-based access control, team/staff performance reporting, and an
audit trail. Built to run on Ubuntu 22.04 LTS.

## Stack

- **Backend**: Python 3 / FastAPI, SQLAlchemy ORM, JWT authentication
- **Database**: PostgreSQL (production) — SQLite works out of the box for local testing
- **Frontend**: Responsive single-page app in vanilla JS + Bootstrap 5 (no build step required)
- **Import**: XLSX via openpyxl, with column mapping, validation, and duplicate detection
- **Reports**: On-screen, printable, and exportable to PDF (reportlab) and XLSX (openpyxl)

## Project layout

```
leadcrm/
  .github/workflows/ci.yml   CI: backend smoke test, lint, JS syntax check, shellcheck
  LICENSE              MIT
  CONTRIBUTING.md        Branch strategy, dev setup, code map
  CHANGELOG.md             Release notes (Keep a Changelog format)
  backend/            FastAPI application
    app/
      main.py          App entrypoint, DB bootstrap, static frontend mount
      config.py         Settings (env vars)
      database.py        SQLAlchemy engine/session
      models.py           ORM models (User, Team, Lead, FollowUp, AuditLog, ...)
      schemas.py            Pydantic request/response schemas
      deps.py                 Auth + RBAC dependencies, audit logging helper
      routers/
        auth.py, users.py, teams.py, leads.py, import_xlsx.py, reports.py, audit.py
      utils/
        security.py           Password hashing + JWT
        exporters.py           PDF/XLSX report builders
    requirements.txt
    run.py                    `python run.py` for local dev
  frontend/            Static single-page app (served by FastAPI or Nginx)
    index.html
    css/style.css
    js/api.js, ui.js, views.js, app.js
  deploy/
    install_ubuntu22.sh   One-shot Ubuntu 22.04 installer (Postgres, venv, systemd, Nginx)
    reset_admin_password.sh  Reset any user's password directly (see Troubleshooting)
    leadcrm-backend.service   systemd unit
    nginx_leadcrm.conf         Nginx reverse-proxy config
    .env.example                 Environment variable template
```

## Roles & permissions

| Role | Capabilities |
|---|---|
| **Super Admin** | Everything, including creating other admins |
| **Site Admin** | Manage users/teams/settings, view audit log, full lead visibility |
| **Marketing Manager** | Full lead visibility, assign leads, manage teams, view all reports |
| **Team Leader** | Manage & assign leads within their own team, view team reports |
| **Marketing Staff** | View/update only leads assigned to them, log follow-ups, change status |

Enforcement happens **server-side** in `app/deps.py` and in each router
(`app/routers/leads.py` in particular) — the frontend hides UI a role
can't use, but the API independently rejects anything out of scope.

## Quick start (local testing, no install script)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Uses SQLite by default (./leadcrm.db) — fine for trying things out.
# For Postgres, set DATABASE_URL first (see deploy/.env.example).
python run.py
```

Then open `http://localhost:8000/` — FastAPI serves the frontend
directly when `frontend/` is next to `backend/` (or set `FRONTEND_DIR`).

On first run against an empty database, a **Super Admin** account is
created automatically:
- username: `admin`
- password: `ChangeMe123!` (or whatever you set `BOOTSTRAP_ADMIN_PASSWORD` to)

**Log in and change this password immediately** — create yourself a
proper admin account and disable/change the bootstrap one.

## Production install on Ubuntu 22.04

From a copy of this whole `leadcrm/` folder on the target server:

```bash
sudo bash deploy/install_ubuntu22.sh
```

This will:
1. Install Python 3, PostgreSQL, and Nginx via apt
2. Create a dedicated `leadcrm` system user and `/opt/leadcrm`
3. Create a PostgreSQL database + role with a random generated password
4. Set up a Python virtualenv and install backend dependencies
5. Write `/opt/leadcrm/backend/.env` with a random `SECRET_KEY` and DB credentials
6. Install and start a `leadcrm-backend` systemd service (Uvicorn on 127.0.0.1:8000)
7. Configure Nginx to serve the frontend and reverse-proxy `/api/*` to the backend

At the end it prints the generated **Super Admin password** — save it,
log in, and change it right away. It also reminds you to:
- Edit `/etc/nginx/sites-available/leadcrm` to set your real `server_name`
- Set up HTTPS, e.g.: `sudo apt install certbot python3-certbot-nginx && sudo certbot --nginx`

### Useful operational commands

```bash
sudo systemctl status leadcrm-backend       # check service health
sudo journalctl -u leadcrm-backend -f       # tail backend logs
sudo systemctl restart leadcrm-backend      # restart after config changes
sudo nginx -t && sudo systemctl reload nginx
```

To redeploy after code changes, copy the updated `backend/` and
`frontend/` folders into `/opt/leadcrm/`, reinstall any new Python
dependencies into the venv, then `sudo systemctl restart leadcrm-backend`.

## Troubleshooting

Hitting an install or deployment error? Check `TROUBLESHOOTING.md`
first — it covers the PostgreSQL connection/permission errors people
most commonly hit on first install, and how to confirm the install
script's re-run is safe.

## Contributing

See `CONTRIBUTING.md` for the branch strategy (`main` / `dev` /
feature branches), local dev setup, and where things live in the
codebase. `CHANGELOG.md` tracks notable changes release by release.
CI (`.github/workflows/ci.yml`) runs automatically on every push and
PR to `main` or `dev`: it lints and byte-compiles the backend, starts
it and checks `/api/health`, syntax-checks the frontend JS, and
shellchecks the install script.

Locked out or can't log in? `sudo bash deploy/reset_admin_password.sh`
resets any user's password directly — see `TROUBLESHOOTING.md`.

## Data model notes

- A **Lead** record doubles as the customer record through its lifecycle
  (`status`: new → contacted → follow_up → pending → converted / lost /
  closed). There's no separate "customer" table to avoid data
  duplication when a lead converts — `converted_at` is stamped instead.
- **Duplicate detection** (both on manual creation and on XLSX import)
  is based on a normalized key derived from email (preferred) or phone.
  A second lead with the same email/phone is rejected/skipped rather
  than silently duplicated.
- Every status change, assignment, and import batch writes a row to
  `lead_status_history` / `audit_logs` for traceability.

## Security notes

- Passwords are hashed with bcrypt; sessions use short-lived JWTs
  (default 8 hours, configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).
- RBAC is enforced in the API layer, not just the UI.
- The `.env` file contains secrets (DB password, JWT signing key) —
  it's created with `chmod 600` by the install script; keep it that way.
- For real production use beyond a first deployment, consider adding:
  refresh-token rotation, account lockout/rate limiting on login,
  email-based password resets, and moving `CORS_ORIGINS` from `*` to
  your actual domain.
