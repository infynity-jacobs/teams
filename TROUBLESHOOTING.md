# Troubleshooting

## `install_ubuntu22.sh` fails with PostgreSQL connection/permission errors

**Symptoms:**

```
could not change directory to "/home/youruser/leadcrm": Permission denied
psql: error: connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed: No such file or directory
```

These are two different things:

- The **"could not change directory"** line is cosmetic. It happens
  because `sudo -u postgres psql ...` tries to preserve your current
  working directory, and the `postgres` system user can't traverse
  into your home directory (home dirs are locked to their owner by
  default). `psql` falls back to `/` and keeps going — by itself this
  line doesn't stop anything.
- The **"No such file or directory"** line is the real problem:
  PostgreSQL isn't actually running yet, so there's no socket to
  connect to. Because the script uses `set -euo pipefail`, it aborts
  the moment a `psql` command fails this way.

As of the current version of `install_ubuntu22.sh`, both are fixed:
the script `cd`s to `/tmp` before touching Postgres (so the chdir
issue can't happen regardless of where you run it from), and it
explicitly starts PostgreSQL and polls `pg_isready` for up to 30
seconds before proceeding, failing with a clear message if it never
comes up. If you're hitting this, pull the latest script and re-run
it — it's safe to re-run (see below).

**Manual diagnosis**, if the script still fails after that:

```bash
sudo systemctl status postgresql --no-pager
sudo journalctl -u postgresql -n 50 --no-pager
df -h /var/lib/postgresql       # rule out disk space
dpkg -l | grep postgresql       # confirm the package actually installed
```

Common causes: the disk ran out of space during `initdb`, a prior
broken install left a half-initialized data directory, or (rare on a
plain Ubuntu 22.04 VM) something is blocking services from
auto-starting.

Once you've confirmed Postgres is installed and running
(`sudo -u postgres pg_isready` should print `accepting connections`),
just re-run the install script.

## Is it safe to re-run `install_ubuntu22.sh`?

Yes. It's designed to be idempotent:

- If `backend/.env` already exists, it **reuses** the existing DB
  password and secret key instead of generating new ones — and if
  the Postgres role already exists, it runs `ALTER ROLE` to make sure
  the role's actual password matches what's in `.env`, so the two
  never drift out of sync.
- It won't overwrite an existing `/etc/nginx/sites-available/leadcrm`
  (so a `server_name`/TLS setup you've customized survives a re-run).
- `useradd`, `CREATE ROLE`/`CREATE DATABASE`, and the systemd/Nginx
  steps all check for existing state first.

If it fails partway through, fix the underlying issue (see above) and
just run it again.

## Backend service won't start after install

```bash
sudo systemctl status leadcrm-backend --no-pager
sudo journalctl -u leadcrm-backend -n 100 --no-pager
```

Common causes:
- `backend/.env` has a `DATABASE_URL` that doesn't match the actual
  Postgres role/password (see above — re-running the install script
  now fixes this automatically).
- A Python dependency failed to install into the venv — re-run
  `/opt/leadcrm/backend/venv/bin/pip install -r /opt/leadcrm/backend/requirements.txt`
  manually and read the actual error.

## Nginx returns 502 Bad Gateway

The backend isn't running or isn't listening on 127.0.0.1:8000.
Check `sudo systemctl status leadcrm-backend` first, then
`sudo nginx -t` to confirm the site config itself is valid.

## XLSX import rejects every row

Check that the "first_name" application field is actually mapped to
a column in your file — it's the one required field. The import
preview screen shows a few sample rows so you can confirm the
mapping looks right before committing.
