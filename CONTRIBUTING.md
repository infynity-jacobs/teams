# Contributing to Lead CRM

Thanks for working on this project. This document covers how the repo is
organized, how to get a dev environment running, and the conventions to
follow when committing and opening PRs.

## Branch strategy

- **`main`** — always deployable. Only merged into via reviewed PRs (or
  fast-forward merges from `dev` for releases). Tag releases from here.
- **`dev`** — integration branch for day-to-day work. Feature branches
  target this branch.
- **Feature branches** — cut from `dev`, named `feature/<short-description>`,
  `fix/<short-description>`, or `chore/<short-description>`.

Typical flow:

```bash
git checkout dev
git pull
git checkout -b feature/lead-export-csv
# ... make changes, commit ...
git push -u origin feature/lead-export-csv
# open a PR into dev
```

Periodically `dev` is merged into `main` and tagged as a release once it's
been tested (see `CHANGELOG.md`).

For a solo project or small team, it's fine to commit straight to `dev`
and merge to `main` yourself when ready — the branch split just keeps
`main` stable and deployable at all times.

## Commit messages

Use short, imperative subject lines, optionally with a scope prefix:

```
leads: fix duplicate detection for phone-only records
reports: add CSV export option
frontend: fix pagination on leads list
deploy: bump nginx client_max_body_size for larger imports
```

Squash noisy WIP commits before opening a PR where practical.

## Local development setup

Backend:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../deploy/.env.example .env   # then edit as needed; SQLite works with no changes
python run.py
```

The app serves the frontend automatically at `http://localhost:8000/`
when `frontend/` is a sibling of `backend/` (default `FRONTEND_DIR`).

Frontend: plain HTML/CSS/JS, no build step. Edit files under
`frontend/` and refresh the browser — FastAPI serves them as static
files, so changes are picked up immediately.

On first run against an empty database, a bootstrap Super Admin is
created (`admin` / value of `BOOTSTRAP_ADMIN_PASSWORD`, default
`ChangeMe123!`). Change this password immediately in any environment
that isn't purely local/throwaway.

## Code layout quick reference

| Area | Where |
|---|---|
| Auth / RBAC | `backend/app/deps.py`, `backend/app/utils/security.py` |
| Data models | `backend/app/models.py` |
| API request/response shapes | `backend/app/schemas.py` |
| Lead lifecycle logic | `backend/app/routers/leads.py` |
| XLSX import | `backend/app/routers/import_xlsx.py` |
| Reports (JSON + PDF/XLSX export) | `backend/app/routers/reports.py`, `backend/app/utils/exporters.py` |
| Frontend routing/views | `frontend/js/app.js`, `frontend/js/views.js` |
| Deployment | `deploy/` |

## Testing changes before committing

There's no automated test suite yet (see "Good first issues" below) —
until then, please at least smoke-test manually:

```bash
# Backend starts cleanly and responds
cd backend && python run.py &
curl -s http://localhost:8000/api/health

# Python files import without syntax errors
python -m py_compile app/**/*.py

# JS files are syntactically valid
node --check ../frontend/js/*.js
```

CI (`.github/workflows/ci.yml`) runs these same checks automatically on
every push and PR.

## Good first issues / roadmap ideas

- Add a real automated test suite (pytest + httpx `TestClient` for the
  backend covers a lot of ground quickly).
- Refresh-token rotation and login rate limiting.
- Password reset flow (currently admin-only password resets via the
  Users screen).
- CSV import in addition to XLSX.
- Per-team custom lead fields.

## Reporting issues

Open a GitHub issue with steps to reproduce, expected vs. actual
behavior, and your environment (OS, Python version, browser). For
security-sensitive issues, please don't open a public issue — contact
the maintainer directly instead.
