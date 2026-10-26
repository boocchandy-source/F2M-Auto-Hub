# F2M Auto-Hub Management System

A web version of the F2M Auto-Hub Tires & Mags Trading customer-service and
automotive-shop system. The original Tkinter desktop program is still included as
`armian F2M system.py`; this Flask application is the deployable web port.

## What it does

- Administrator sign-in with CSRF protection, login rate limiting, secure session
  cookies, and hardened response headers.
- Dashboard with customer, vehicle, request, appointment, and concern totals.
- Customer records with automatic vehicle creation and search.
- Vehicle information with plate-number duplicate checks.
- Daily Customer Record browser: **1,221 imported visit rows** across 127 dates,
  with date selection, search, and pagination.
- Service requests; marking a request **Completed** also creates a service-history
  entry.
- Appointment scheduling with duplicate protection.
- Service history, feedback/concerns, and a notification log.
- Daily, weekly, and monthly reports with a formatted Excel (`.xlsx`) export:
  summary sheet, one Daily Customer Record sheet per date, plus customer,
  appointment, request, history, feedback, and notification sheets.
- Responsive red/black/white admin UI, printable reports, and a `/healthz` endpoint
  for Render health checks.
- First-run import is idempotent: restarts and redeploys do not duplicate data.

## Requirements

- Python **3.12** (the project is pinned to 3.12.8 in `.python-version`)
- pip
- A modern browser

The production dependency list is in `requirements.txt`. Tests additionally need
`requirements-dev.txt`.

## Run locally (Windows PowerShell)

From this folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set at least:

```dotenv
SECRET_KEY=replace-with-a-long-random-string
ADMIN_USERNAME=admin
ADMIN_PASSWORD=choose-a-strong-password
SESSION_COOKIE_SECURE=0
```

Generate a secret key with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Start the development server:

```powershell
python run.py
```

Open <http://127.0.0.1:5000> and sign in with the credentials from `.env`.

If PowerShell blocks virtual-environment activation, run the app directly:

```powershell
.\.venv\Scripts\python run.py
```

On macOS/Linux the equivalent commands are:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

### Default login warning

If neither `ADMIN_PASSWORD` nor `ADMIN_PASSWORD_HASH` is set, the app uses the
original desktop credentials:

```text
username: admin
password: admin123
```

The interface shows a warning while this default is active. Always set a strong
`ADMIN_PASSWORD` before exposing the app publicly.

## Run the tests

```powershell
pip install -r requirements-dev.txt
pytest
```

The suite covers authentication, CSRF rejection, login rate limiting, customer
and vehicle CRUD, service-request completion, appointments, feedback,
notifications, cascade deletes, the first-run workbook import, report rendering,
Excel export, error pages, security headers, redirect/validation helpers, and
Render's Postgres URL formats. It currently contains **44 tests**.

Useful checks:

```powershell
python -m compileall f2m wsgi.py run.py
pytest -q
```

## Deploy to Render

### Prepare the repository

Render deploys from a Git repository. From this folder, create one and push it to
GitHub (or GitLab):

```powershell
git init
git add .
git commit -m "F2M Auto-Hub web system"
git branch -M main
# Create an empty repository on GitHub first, then:
git remote add origin https://github.com/YOUR-ACCOUNT/YOUR-REPO.git
git push -u origin main
```

`.gitignore` already excludes `.venv/`, local databases, `.env`, and caches, so
secrets and local data are not published. Do not commit a filled-in `.env`.

### Option A — free demo (default `render.yaml`)

This Blueprint creates a free Python web service plus a free Render Postgres
database.

1. Push this folder to a GitHub (or GitLab) repository.
2. In the Render Dashboard choose **New → Blueprint**.
3. Connect the repository. Render reads `render.yaml` automatically.
4. When prompted, enter a strong value for `ADMIN_PASSWORD`.
5. Apply the Blueprint and wait for the deploy and health check to pass.
6. Open the service URL and sign in as `admin` with the password you entered.

The first boot imports the 1,221 Daily Customer Record rows. Demo records are
disabled by default in the Blueprint; set `SEED_DEMO_DATA=1` and redeploy on an
empty database if you want sample workflow data.

**Important free-plan limits**

- **Render free Postgres databases expire 30 days after creation.** After that the
  service cannot connect and the app will fail its health check. Plan for this
  before the expiry date. Options:
  - upgrade the database to a paid Render Postgres plan;
  - point `DATABASE_URL` at a durable external Postgres (for example Neon or
    Supabase);
  - use the paid persistent-disk Blueprint below.
- Free web services spin down after 15 minutes without traffic. The next request
  can take roughly 30–60 seconds while the instance starts.
- Free instances have limited CPU/RAM and no persistent disk.
- Recreating or replacing a free database starts from an empty database; the app
  will seed the workbook again, but any data entered through the web app is lost
  unless it was backed up.

### Option B — durable single-instance deployment (`render.disk.yaml`)

This Blueprint uses a paid web service plus a 1 GB persistent disk and keeps the
database in SQLite on that disk. It does not use Render Postgres.

1. Rename/replace `render.yaml` with `render.disk.yaml`, or configure Render to use
   `render.disk.yaml` as the Blueprint path.
2. Apply the Blueprint and enter `ADMIN_PASSWORD`.
3. The database is stored at `/var/data/f2m_autohub.db` and survives restarts and
   deploys.

Cost note: the Blueprint uses the paid `0.5c-512mb` instance (about $7/month at
the time of writing) plus a 1 GB disk (about $0.25/GB/month). Verify current
Render pricing before deploying. Keep this deployment at **one instance**;
persistent disks and SQLite are not suitable for multi-instance scaling.

### Option C — paid Postgres with the free web service

If you want the free web tier but durable data, keep `render.yaml` and change the
database plan from `free` to a paid Render Postgres plan (for example
`0.1c-256mb`). The database is then billed separately, while the web service can
still spin down when idle.

### Environment variables

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `SECRET_KEY` | Production: yes | Random temporary key | Signs sessions. Without it, every restart logs users out. |
| `ADMIN_USERNAME` | No | `admin` | Administrator username. |
| `ADMIN_PASSWORD` | Production: yes | `admin123` | Plain administrator password. |
| `ADMIN_PASSWORD_HASH` | No | — | Werkzeug hash; takes precedence over `ADMIN_PASSWORD`. |
| `DATABASE_URL` | No | SQLite in `instance/` | PostgreSQL URL (Render injects this) or SQLite URL. |
| `DATA_DIR` | No | `instance/` | Folder for the SQLite file when `DATABASE_URL` is unset. |
| `APP_TIMEZONE` | No | `Asia/Manila` | Timezone for dates and timestamps. |
| `SESSION_COOKIE_SECURE` | No | `1` on Render, `0` otherwise | Set `0` only for local HTTP. |
| `SEED_DATA` | No | `1` | Import the Daily Customer Record workbook on first boot. |
| `SEED_DEMO_DATA` | No | `1` (app); `0` in Blueprints | Add six demo customers and sample workflow records. |
| `TRUST_PROXY_HEADERS` | No | `1` on Render | Trust Render's proxy headers for scheme and client IP. |
| `PORT` | No | `5000` locally | Injected by Render/Gunicorn. |

To generate a password hash:

```powershell
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-password'))"
```

Then set `ADMIN_PASSWORD_HASH` and remove `ADMIN_PASSWORD` from the environment.

## Data and seeding

- The source workbook data lives in `f2m/data/customer_records.json`.
- On first boot the app imports **1,221 visits**, **1,122 customers**, and
  **1,113 vehicles**, then records `seed_version` in the `system_meta` table.
- Subsequent boots skip the import, so deploys and restarts are safe.
- `SEED_DEMO_DATA=1` adds six demo customers plus sample appointments, requests,
  history, feedback, and notifications. It is helpful for a local walkthrough or a
  showcase deployment. Both Render Blueprints set it to `0` so a production
  database starts with only the imported records.
- Visits are deduplicated on the complete row, not on `(date, record number)`,
  because the source workbook can repeat record numbers across different tables.
- Demo records can be deleted from the UI after the first boot.

Maintenance commands (run against the configured database):

```powershell
flask --app wsgi init-db     # create missing tables only
flask --app wsgi seed-db     # import the workbook if it has not been imported
flask --app wsgi reset-data  # DESTRUCTIVE: drop all tables, recreate, re-import
```

`reset-data` deletes every customer, visit, request, appointment, history record,
concern, and notification. Back up first.

## Project structure

```text
armian F2M system.py       Original Tkinter desktop app (reference only)
f2m/                        Flask application package
  __init__.py               App factory, configuration, startup bootstrap
  models.py                 SQLAlchemy models
  auth.py                   Login, logout, rate limiting
  security.py               CSRF and security headers
  seed.py                   Idempotent workbook import and demo data
  views.py                  All page routes and business logic
  export.py                 Excel workbook builder
  timeutil.py               Asia/Manila date/time helpers
  utils.py                  Shared validation and formatting helpers
  ui.py                     Navigation, icons, template filters
  data/customer_records.json
  static/                   CSS, JS, logo, favicon
  templates/                Jinja templates
tests/                      Pytest suite
requirements.txt            Production dependencies
requirements-dev.txt        Test dependencies
run.py                      Local development server
wsgi.py                     Gunicorn entry point (`gunicorn wsgi:app`)
render.yaml                 Free web + free Postgres Blueprint
render.disk.yaml            Paid web + persistent SQLite disk Blueprint
Procfile                    Generic process definition for WSGI hosts
```

## Deployment notes

- The production command is intentionally **one Gunicorn worker with eight
  threads**. This avoids two workers racing to seed the database on a cold start.
  Increase `--threads` rather than `--workers` if you need more concurrency.
- Do not scale a SQLite/persistent-disk deployment to multiple instances.
- For PostgreSQL, each deployment should point at a single database. Tables are
  created automatically at startup.
- Back up production data before changing plans or running destructive commands.
  Render's paid Postgres plans support backups; for SQLite, copy the database file
  from the persistent disk.
- `db.create_all()` creates missing tables but does not migrate existing table
  layouts. If the models change later, add an Alembic migration or plan a
  controlled reset/import rather than relying on `create_all` alone.
- The app has a single administrator account by design. It is not multi-tenant and
  does not provide per-user roles.
- Static files are served by Flask. No CDN or external font/icon service is
  required, which keeps the Content Security Policy strict.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `SECRET_KEY is not set` warning | Add `SECRET_KEY` to the environment and restart. Without it sessions reset on restart. |
| “Default administrator password is active” banner | Set `ADMIN_PASSWORD` (or `ADMIN_PASSWORD_HASH`) and redeploy. |
| Login returns “Incorrect username or password” | Check `ADMIN_USERNAME` / `ADMIN_PASSWORD`. If using a hash, regenerate it with the command above. |
| `429 Too many failed attempts` | Wait five minutes, or restart the process to clear the in-memory limiter. |
| `400` “security token is invalid” | Refresh the page before submitting. Cookies must be enabled; changing `SECRET_KEY` invalidates old sessions. |
| Health check fails on Render | Open the deploy logs. Confirm the database is available and not expired, and that `ADMIN_PASSWORD` was supplied. Startup retries database connections five times. |
| First request after idle is slow | Expected on Render's free tier; the service spins down after 15 minutes. |
| Free Postgres stopped working after a month | The free database expired after 30 days. Upgrade the database plan, attach another Postgres, or move to the persistent-disk Blueprint. Data in the expired database is not automatically migrated. |
| `database is locked` | Use one Gunicorn worker/instance with SQLite. For higher concurrency, use PostgreSQL. |
| Styling is missing | Confirm Gunicorn is started as `gunicorn wsgi:app` and that `/static/css/style.css` loads without a 404. |
| Report dates look wrong | Set `APP_TIMEZONE=Asia/Manila`; Render servers run in UTC. |

## Desktop version

The original `armian F2M system.py` remains unchanged and can still be run locally
with Python's Tkinter and SQLite libraries. It is kept for reference and as a
fallback; the web application is the deployment target.
