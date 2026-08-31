# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

- (nothing yet)

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
