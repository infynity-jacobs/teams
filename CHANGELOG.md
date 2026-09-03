# v2.5.8.6 - Persistent Branding Uploads

- Fixed upgrade deployment deleting runtime branding uploads under `backend/uploads`.
- Standardized persistent production uploads to `/opt/leadcrm/uploads`.
- Existing legacy `backend/uploads` assets are migrated to the canonical upload directory during upgrade.
- Existing `.env` files without `UPLOAD_DIR` are updated to use the persistent upload directory.
- PDF branding resolves the canonical upload directory first, with backward-compatible fallbacks.
- Application upload defaults now use the persistent project-level uploads directory.

# v2.5.8.5 - Robust PDF Logo Rendering

- Fixed PDF logos that rendered as blank/tiny marks because SVG viewBox/transparent margins consumed the image area.
- Added CairoSVG as the primary SVG rasterizer with svglib/ReportLab fallback.
- Crops transparent SVG margins before embedding into ReportLab PDFs.
- Logs PDF logo rendering failures to the backend journal instead of silently hiding them.

# v2.5.8.4 - PDF Logo Rendering Restoration

- Restored the proven v2.5.6 SVG logo rendering path using svglib + ReportLab renderPM for branded PDF reports.
- Retained password-reset routing, audit actor history, category delete, and all prior v2.5.8 fixes.
- Retained PNG/JPEG/WebP logo support and dynamic PDF orientation.

## 2.5.8.3 - Category Delete Fix

- Fixed Product Categories delete buttons by binding handlers after dynamic table rendering.
- Retained PDF SVG logo rendering, password-reset routing, audit actor history, and all previous v2.5.8 fixes.

# Changelog

## 2.5.8.2 - PDF Logo Rendering Fix

- Fixed branded PDF report logos disappearing when ReportLab raster rendering backends are unavailable.
- SVG logos are now rendered directly as vector graphics using ReportLab `renderPDF`, avoiding optional `renderPM` raster backends.
- Retained PNG/JPEG/WebP logo handling and all v2.5.8 audit and password-reset fixes.

Changelog

## 2.5.8 - Audit Log Accountability Fix

### Password Reset Reliability
- Password reset links now prefer the configured Frontend URL and otherwise derive the public origin from reverse-proxy headers, avoiding internal Uvicorn URLs when deployed behind Nginx/Cloudflare.
- Stock Nginx and systemd templates explicitly forward/trust the public host and HTTPS scheme.

- Audit logs now retain actor name, username and role snapshots.
- Audit log UI displays who performed each action and the exact local date/time including seconds.
- Existing audit records are backfilled from current user accounts where possible.
- Audit-log user foreign key now uses `ON DELETE SET NULL`, preserving audit history if a user is permanently deleted.
- Super Admin user deletion no longer treats audit logs as a blocking dependency.
- Successful user deletion remains audit-logged using the acting administrator.


## 2.5.7 - Branding and Super Admin Controls

- Apply configured company logo/site name/tagline to the login screen.
- Add Super Admin-only permanent delete controls for products, categories, users, teams, and leads.
- Protect historical product/category/user/team records with dependency checks; recommend deactivation when historical references exist.
- Keep Site Admin and lower roles from destructive administrative operations.
- Add audit logging for successful destructive operations.

# v2.5.6 - PDF Logo Rendering Fix

- Fixed PDF branding when the configured company logo is SVG.
- SVG logos are converted to PNG in memory for ReportLab before rendering.
- Kept PNG/JPEG/WebP logo support and dynamic portrait/landscape PDF layout.
- Added `svglib` dependency for reliable SVG parsing.

## v2.5.5 - Reliable PDF Logo Rendering

- Fixed report logo resolution when `UPLOAD_DIR` is relative or the service working directory differs.
- Added WebP logo support by converting WebP assets to PNG for ReportLab.
- Kept dynamic portrait/landscape PDF layout and branded headers/footers.
- Bumped frontend asset cache version.

## v2.5.3
- Dynamic A4 PDF orientation: compact reports use portrait, while wide or long reports use landscape.
- Improved PDF column sizing and table readability.

## [2.5.2] - 2026-09-03

### Fixed
- Reports now automatically run when the selected report type changes.
- Product Performance immediately displays the product rows after selecting the report, without requiring a second manual click.
- Bumped frontend cache version to 2.5.2.

## [2.5.1] - 2026-09-03

### Fixed
- Lead Status History now displays the user who performed each status change.
- Added `changed_by_name` to lead history API output.
- Bumped frontend cache version to 2.5.1.

## [2.5.0] - 2026-09-02

- Added scheduled follow-up queue with overdue, today, upcoming and completed-today summaries.
- Added follow-up scheduling, editing and one-click completion from lead details and the queue.
- Added dashboard follow-up KPI cards and a clickable follow-up queue.
- Added a dedicated Follow-ups navigation page with role-scoped visibility.
- Improved follow-up timeline to show scheduled/completed timestamps and overdue/completed state.

## v2.4.1 - Dashboard Donut Charts
- Replaced dashboard status, team, staff, and product performance bar visualizations with responsive donut charts and clickable legends.
- Kept dashboard KPI cards, recent leads, and report navigation clickable.
- Added responsive dashboard donut styling for desktop and mobile layouts.


## v2.4.0 - Dashboard Analytics & Navigation
- Added dashboard lead-status visualization.
- Added team performance visualization and summary.
- Added staff performance visualization.
- Added product performance visualization linked to the Product Performance report.
- Made dashboard KPI cards clickable.
- Made dashboard chart rows and recent leads clickable.
- Added dashboard deep links into lead filters and reports.
- Added report deep-linking via `#/reports?type=...`.


All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

- (nothing yet)

## [0.2.0] - 2026-09-01

### Added
- Leads now have two new fields: **Place/Area** (free text, like
  Company) and **Referred By** (a controlled dropdown).
- New admin-managed Settings module: `SettingOption` model, grouped
  by `category` (currently just `referred_by`), so more managed lists
  can reuse the same table later without a schema change. CRUD is
  restricted to Super Admin / Site Admin via `/api/settings/options`;
  any authenticated user can read active options to populate the
  dropdown. Deactivating an option is a soft delete — historical
  leads keep showing their value even after it's removed from the
  dropdown — and re-adding a deactivated value reactivates it rather
  than erroring.
- New Settings page in the frontend (nav item visible to Super
  Admin/Site Admin only) for managing the Referred By list.
- `place_area` and `referred_by` are now mappable fields in the XLSX
  import column-mapping UI, and included in the lead lifecycle report
  export columns.
- `deploy/migrate.sh` + `deploy/migrations/`: a tracked SQL migration
  runner for existing installs. `Base.metadata.create_all()` (run on
  every backend startup) only creates missing *tables*, never adds
  columns to a table that already exists — so upgrading an existing
  database's `leads` table needs an explicit migration. Applied
  migrations are tracked in a `schema_migrations` table so the script
  is safe to re-run at any time.

### Fixed
- **`app/config.py`**: fixed a bug where the backend would crash
  instantly on startup — before ever reaching the database — if
  `backend/.env` contained any key not explicitly declared as a
  `Settings` field. `install_ubuntu22.sh` always writes `FRONTEND_DIR`
  into `.env`, so every install hit this. This was likely the actual
  root cause behind earlier reports of `leadcrm-backend` crash-looping
  and the `users` table never getting created, independent of and in
  addition to any Postgres credential mismatch. Fixed by setting
  `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`.
- `deploy/diagnose.sh` now also scans recent backend logs for this
  specific `pydantic_core.ValidationError` signature and flags it
  directly instead of only diagnosing DB-connection failures.
- `TROUBLESHOOTING.md`: documented the above as its own section, and
  documented the new `deploy/migrate.sh` step in the README.

## [0.1.3] - 2026-08-31

### Added
- `deploy/diagnose.sh`: one-command health check for a Lead CRM
  install — verifies PostgreSQL is running, that `backend/.env`'s
  credentials actually authenticate, that the app's database schema
  exists, and the backend systemd service's status, then prints a
  specific fix for whatever it finds broken. Covers the case where
  `reset_admin_password.sh` fails with `relation "users" does not
  exist` (schema never created, almost always a Postgres
  role/`.env` password mismatch left over from an earlier failed
  install attempt).
- `TROUBLESHOOTING.md`: documented this scenario and pointed to
  `diagnose.sh` as the first thing to run when anything's wrong.

## [0.1.2] - 2026-08-31

### Added
- `deploy/reset_admin_password.sh`: resets any user's password
  directly in the database using the app's own bcrypt hashing.
  Fixes the common case where the bootstrap admin password printed
  by a re-run of `install_ubuntu22.sh` doesn't match what's actually
  stored, because the bootstrap admin is only ever created once
  (the first time the app starts against an empty `users` table).
- `TROUBLESHOOTING.md`: documented this scenario and the fix.

## [0.1.1] - 2026-08-31

### Fixed
- `deploy/install_ubuntu22.sh`: no longer fails with a spurious
  "could not change directory" warning when invoked from inside a
  locked-down home directory — the script now moves to `/tmp` before
  any `sudo -u postgres` calls.
- `deploy/install_ubuntu22.sh`: explicitly starts PostgreSQL and
  waits (up to 30s) for it to accept connections before touching the
  database, instead of failing opaquely mid-script if the service
  wasn't up yet.
- `deploy/install_ubuntu22.sh`: fixed a credential desync bug where
  re-running the script after a partial failure would generate a new
  random DB password without updating the already-created Postgres
  role to match, silently breaking the app. Re-runs now reuse
  existing `backend/.env` credentials, and `ALTER ROLE` keeps the
  Postgres role in sync if it already exists.
- `deploy/install_ubuntu22.sh`: no longer overwrites an existing
  Nginx site config on re-run, so a customized `server_name`/TLS
  setup survives.

### Added
- `TROUBLESHOOTING.md` covering the above and a few other common
  first-deploy issues.

## [0.1.0] - 2026-08-31

### Added
- FastAPI backend with JWT authentication and role-based access control
  (Super Admin, Site Admin, Marketing Manager, Team Leader, Marketing Staff).
- Lead lifecycle management: create, update, assign, change status, log
  follow-ups, and view full status/follow-up history per lead.
- Customer/lead XLSX import with column-mapping UI, per-row validation,
  and duplicate detection by normalized email/phone.
- Team and user management with role-scoped visibility.
- Reports: new / follow-up / pending / converted / lost / all leads,
  staff-wise performance, team-wise performance, and conversion stats —
  filterable by date, team, staff, source, and status; exportable to
  PDF and XLSX; printable from the browser.
- Audit log of key actions (login, create/update/delete, status changes,
  assignments, imports), visible to admins.
- Responsive vanilla JS + Bootstrap 5 frontend, no build step required.
- Ubuntu 22.04 deployment tooling: automated install script
  (PostgreSQL + venv + systemd + Nginx), systemd unit, Nginx config,
  and `.env` template.
- Project scaffolding: `README.md`, `CONTRIBUTING.md`, `LICENSE`, CI
  workflow, `dev`/`main` branch structure.

## [2.0.0] - 2026-09-02

- Added comprehensive administrator Settings module and site branding.
- Added encrypted SMTP configuration and SMTP test email.
- Added report email delivery with PDF/XLSX attachments.
- Added secure single-use password reset and administrator reset email flow.
- Added password/session invalidation support and expanded audit events.
- Added safe database migrations and a dedicated existing-install upgrade script.
- Fixed deployment so `.env` is preserved during upgrades and deployment files/migrations are installed with the application.

## [2.1.0] - 2026-09-02

- Added a My Profile page for every authenticated role with self-service password change.
- Enforced password-reset privilege hierarchy: only Super Admins may reset Super Admin or Site Admin accounts.
- Prevented non-Super-Admins from using the administrator reset endpoint against higher-privileged accounts.
- Removed the admin-only password-change control from Settings in favor of the universal My Profile page.

## v2.5.4 - Branded PDF Reports

- Added site/company branding to generated PDF reports.
- Uses the configured company logo from the server-local uploads directory.
- Shows company/site name and configured contact details in the PDF header.
- Shows configured report email footer, or company/site name, in the PDF footer with page numbers.
- Applies branding consistently to downloaded and emailed PDF reports.
- Preserves dynamic portrait/landscape report orientation.
- No database migration required.

Lead CRM v2.5.8 password-reset routing fix
