## v2.7.0 Mobile UX

Version 2.7.0 is the complete mobile-friendly UI release. Desktop layouts remain table-oriented while phone layouts use cards, stacked filters, touch-sized actions, mobile navigation and full-screen forms/modals.

### Mobile phases included
- Phase 1: Core mobile UX — navigation, Leads cards, Lead Details actions, New/Edit Lead forms, full-screen modals, touch targets and sticky actions.
- Phase 2: Reports — responsive filters, report cards, mobile export/action menu and Incentive Sales Detail presentation.
- Phase 3: Dashboard — responsive KPI cards/charts, follow-up cards and recent-lead cards.
- Phase 4: Polish — loading/empty states, safe-area support, reduced motion, overflow prevention and mobile interaction polish.

## v2.6.5 Product Performance Accuracy Fix

Version 2.6.5 clarifies Product Performance & Sales by distinguishing products attached to leads from actual recorded sales. The report now shows Lead Customers, Converted Leads, Sold Customers, Units Sold, and Sales Revenue. Converted Leads are based on the lead lifecycle status; Sold Customers, Units Sold, and Sales Revenue are based only on Conversion/ConversionItem records and remain the authoritative incentive figures.

This release builds on v2.6.4 and requires no database migration.
## v2.6.3 Reports: KPI Summary & Incentive Sales Detail

Version 2.6.3 separates staff lead-performance KPIs from transaction-level sales used for offline incentive calculations. It also keeps Product Performance focused on actual converted sales and preserves seller attribution from v2.6.0.

### Reports
- Staff Performance Summary: lead KPIs only.
- Incentive Sales Detail: one row per converted product line with conversion date, staff, team, customer, phone, lead ID, product, SKU, quantity, unit price, sales amount, and Converted By.
- Product Performance & Sales: aggregate actual converted sales by product and attributed staff.
- Date filters on Incentive Sales Detail and Product Performance use conversion date.

## v2.5.7 PDF branding

Version 2.6.2 updates the Leads list to show **Place / Area** and the products attached to each lead, while removing the Company and Source columns from the main list. Product names are display information only; incentive-eligible sales remain based on conversion records.
PDF reports now render configured SVG logos by converting them to an in-memory PNG for ReportLab. PNG, JPEG and WebP logos remain supported. No database migration is required.

# Lead CRM — Marketing Lead Management & Conversion Application

## v2.6.2 Leads List Area & Products

Version 2.6.1 extends the existing product/conversion reporting so offline incentive calculations can identify **which marketing staff sold which products**. At conversion time, the application snapshots the lead's assigned marketing staff as the seller while retaining the actual user who performed the conversion separately.

Reports now provide:
- Product → Sold By → Team → Units Sold → Converted Leads → Revenue
- Staff → Product → SKU → Units Sold → Sales Revenue → Conversion Date → Lead/Customer → Converted By
- The same attribution is used for on-screen reports, XLSX, PDF, and emailed reports.
- Existing conversions are backfilled from their current lead assignment where possible.

Upgrade with the normal `deploy/upgrade_ubuntu22.sh` workflow; migration `0005_sales_attribution.sql` is applied automatically.


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
    migrate.sh                Applies pending schema migrations to an existing install
    migrations/                  Tracked .sql migration files, applied in order once each
    diagnose.sh               Checks Postgres/env/schema/service health, suggests fixes
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

Locked out, or the app doesn't seem to be working? Start with
`sudo bash deploy/diagnose.sh` — see `TROUBLESHOOTING.md`.

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
- **Place/Area** on a lead is free text (like Company). **Referred By**
  is a controlled dropdown: its options are managed under Settings
  (Super Admin / Site Admin only) via `SettingOption` rows grouped by
  `category` — currently just `referred_by`, but the table is generic
  so more admin-managed lists can reuse it later without a schema
  change. Deactivating an option is a soft delete (`is_active=false`)
  so historical leads keep showing whatever value they were given
  even after it's removed from the dropdown; re-adding the same value
  reactivates it instead of erroring.

## Applying schema changes to an existing install

`Base.metadata.create_all()` (run automatically on every backend
startup) only creates tables that don't exist yet — it never alters a
table that's already there. Since `leads` already exists on any
running install, adding columns to it (like `place_area` and
`referred_by`) needs an explicit migration:

```bash
sudo bash deploy/migrate.sh
sudo systemctl restart leadcrm-backend
```

This applies any `.sql` files under `deploy/migrations/` that haven't
been applied yet (tracked in a `schema_migrations` table), so it's
safe to run any time — already-applied migrations are skipped. Brand
new tables (like `setting_options`) don't need a migration file; the
next backend restart creates them automatically via `create_all()`.

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

## Upgrade an existing Ubuntu 22.04 installation

Copy the complete Lead CRM v2 package to the server and run the upgrade script from its project root:

```bash
sudo bash deploy/upgrade_ubuntu22.sh
```

The upgrade preserves `backend/.env`, the PostgreSQL database, uploaded branding assets, and an existing Nginx site configuration. It installs the complete `deploy/` directory, updates Python dependencies, applies all pending migrations, and restarts the service. A timestamped `.env` backup is saved under `/var/backups/leadcrm/`.

For a fresh server, use:

```bash
sudo bash deploy/install_ubuntu22.sh
```

The installer initializes the SQLAlchemy schema first and then runs the idempotent migrations. It also installs the deployment/migration files into `/opt/leadcrm/deploy/` so future upgrades can be performed on the server without relying on the original source directory.

## v2.3 Products & Conversion

v2.3 adds a product catalogue, product categories, lead product interests, conversion records with price/tax/discount snapshots, product performance reporting, and product-aware Excel lead import.

For an existing installation, run the standard upgrade script from the package root:

```bash
sudo bash deploy/upgrade_ubuntu22.sh
```

The upgrade preserves `backend/.env`, uploads, the PostgreSQL database, and the existing installation while applying migration `0003_products_conversion.sql`.

The migration also creates ten safe demo products and links several existing `demo.leadXX@example.com` records to products when those demo leads exist.
