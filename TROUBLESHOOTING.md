# Troubleshooting

## Can't log in with the auto-generated bootstrap password

The bootstrap Super Admin account is only ever created **once** — the
very first time the app starts against an empty `users` table. If
`install_ubuntu22.sh` fails partway through and you re-run it, it
generates and prints a *new* `BOOTSTRAP_ADMIN_PASSWORD` — but if an
admin account already exists from an earlier attempt (even one that
later failed for an unrelated reason), the app won't touch it. The
password printed on screen and the password actually in the database
end up being two different things.

**Check whether this is what happened:**

```bash
sudo -u postgres psql -d leadcrm -c "SELECT id, username, role, is_active, created_at FROM users;"
sudo journalctl -u leadcrm-backend --no-pager | grep -i "Bootstrapped initial Super Admin"
```

If a user already exists, or that log line only appears once and
predates your latest install run, this is the cause.

**Fix — reset the password directly:**

```bash
sudo bash deploy/reset_admin_password.sh
```

This updates the `admin` user's password in the database using the
app's own bcrypt hashing (so it's guaranteed compatible with login),
and prints a freshly generated password. To set a specific
username/password instead of the defaults:

```bash
sudo bash deploy/reset_admin_password.sh admin 'MyNewPassword123!'
```

Works for any username, not just the bootstrap admin — handy for
resetting any user's password from the CLI if they're locked out.

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

Excellent — the database schema is now successfully initialized. ✅

You now have all 7 required tables:

audit_logs
follow_ups
import_batches
lead_status_history
leads
teams
users

The original error:

psycopg2.errors.UndefinedTable:
relation "users" does not exist

is fixed.

Next: create the initial Super Admin

Your application is designed to create the admin automatically when the FastAPI application starts. However, your manual create_all() only created the tables; it did not execute the on_startup() function.

So let's start the backend once.

First check whether a LeadCRM service already exists:

sudo systemctl status leadcrm

If you get:

Unit leadcrm.service could not be found

then check:

sudo systemctl list-units --type=service | grep -i lead
If you're currently running it manually

You can start it with:

sudo -u leadcrm bash -c 'cd /opt/leadcrm/backend && source venv/bin/activate && python run.py'

You should see Uvicorn start on:

0.0.0.0:8000

and importantly, something similar to:

Bootstrapped initial Super Admin user 'admin'.

Leave that terminal running while we verify it.

Verify the admin was created

Open another SSH terminal and run:

sudo -u postgres psql -d leadcrm -c "SELECT id, username, email, role, is_active FROM users;"

Expected:

 id | username |       email       |    role     | is_active
----+----------+-------------------+-------------+-----------
  1 | admin    | admin@example.com | super_admin | t

If that appears, your initial database setup is complete.

One important security step

The database password was exposed earlier in the conversation. After we get LeadCRM running, I strongly recommend changing that PostgreSQL password and updating .env.

Also, once the admin login works, change the bootstrap admin password immediately.

For now, run:

sudo systemctl status leadcrm

and paste the output. If there is no systemd service, we'll set up the LeadCRM backend as a proper Ubuntu service so it starts automatically after reboot.

administrator@teams:/opt/leadcrm/backend$ sudo systemctl status leadcrm

Unit leadcrm.service could not be found.

administrator@teams:/opt/leadcrm/backend$ sudo systemctl list-units --type=service | grep -i lead

  leadcrm-backend.service                                                                   loaded active running Lead CRM backend (FastAPI/Uvicorn)

administrator@teams:/opt/leadcrm/backend$ sudo -u leadcrm bash -c 'cd /opt/leadcrm/backend && source venv/bin/activate && python run.py'

INFO:     Started server process [15839]

INFO:     Waiting for application startup.

INFO:     Application startup complete.

ERROR:    [Errno 98] error while attempting to bind on address ('0.0.0.0', 8000): address already in use

INFO:     Waiting for application shutdown.

INFO:     Application shutdown complete.

administrator@teams:/opt/leadcrm/backend$ 

That's actually good news. Your Lead CRM backend is already running as:

leadcrm-backend.service

The address already in use error happened because you tried to start a second copy on port 8000.

1. Check the running service

Run:

sudo systemctl status leadcrm-backend

You should see:

Active: active (running)
2. The important question: did the running service create the admin?

Because we manually created the tables after the service was already running, the existing process may not have run its startup code against the newly created tables.

The safest approach is to restart the existing service:

sudo systemctl restart leadcrm-backend

Then immediately check:

sudo systemctl status leadcrm-backend

And check its recent logs:

sudo journalctl -u leadcrm-backend -n 50 --no-pager

Look for:

Bootstrapped initial Super Admin user 'admin'
3. Verify the admin account directly

Run:

sudo -u postgres psql -d leadcrm -c "SELECT id, username, email, role, is_active FROM users;"

If everything worked, you should see something like:

 id | username |       email       |    role     | is_active
----+----------+-------------------+-------------+-----------
  1 | admin    | admin@example.com | super_admin | t
4. Test the API

Since your backend listens on port 8000, run:

curl http://127.0.0.1:8000/api/health

Expected:

{"status":"ok","app":"Lead CRM"}
Don't run python run.py again

From now on, use the existing systemd service:

sudo systemctl restart leadcrm-backend
sudo systemctl stop leadcrm-backend
sudo systemctl start leadcrm-backend
sudo systemctl status leadcrm-backend

This avoids having multiple Uvicorn processes fighting for port 8000.

Run these three commands now:

sudo systemctl restart leadcrm-backend
sudo journalctl -u leadcrm-backend -n 30 --no-pager
sudo -u postgres psql -d leadcrm -c "SELECT id, username, email, role, is_active FROM users;"

Paste the output, and we'll verify that the Super Admin was successfully created.

 id | username |       email       |    role     | is_active 

----+----------+-------------------+-------------+-----------

  1 | admin    | admin@example.com | super_admin | t

(1 row)

administrator@teams:/opt/leadcrm/backend$ 

Excellent. Lead CRM is now initialized correctly. ✅

The important result is:

id | username |      email       |    role     | is_active
---+----------+------------------+-------------+----------
 1 | admin    | admin@example.com | super_admin | t

So:

PostgreSQL connection ✅
Database leadcrm ✅
All 7 tables created ✅
users table exists ✅
Initial Super Admin created ✅
leadcrm-backend.service restarted successfully ✅
FastAPI/Uvicorn running under systemd ✅
1. Verify the API

Run:

curl http://127.0.0.1:8000/api/health

You should get:

{"status":"ok","app":"Lead CRM"}
2. Verify the service
sudo systemctl status leadcrm-backend --no-pager

You want:

Active: active (running)
3. Test from the browser

If your frontend/Nginx is already configured, open your Lead CRM URL in the browser.

If you're accessing the backend directly:

http://YOUR_SERVER_IP:8000/api/health

If your domain is configured through Nginx, use your normal Lead CRM domain.

4. Login

Your initial account is:

Username: admin
Email:    admin@example.com
Role:     super_admin

The password is whatever you configured as:

BOOTSTRAP_ADMIN_PASSWORD

in /opt/leadcrm/backend/.env.

Don't paste that password here.

One issue we should address next

Your Uvicorn logs show multiple worker processes:

Started server process [15923]
Started server process [15924]
...

That suggests your leadcrm-backend.service is probably configured with multiple workers. That's not necessarily wrong, but we should verify the service configuration before making further changes.

Run:

sudo systemctl cat leadcrm-backend

Also:

curl http://127.0.0.1:8000/api/health

If both are successful, your backend is operational and we can move on to checking the frontend → Nginx → FastAPI connection.
