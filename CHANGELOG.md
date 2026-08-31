# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

- (nothing yet)

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
