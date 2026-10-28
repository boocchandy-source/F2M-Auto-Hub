# F2M Auto-Hub Management System

[![CI](https://github.com/boocchandy-source/F2M-Auto-Hub/actions/workflows/ci.yml/badge.svg)](https://github.com/boocchandy-source/F2M-Auto-Hub/actions/workflows/ci.yml)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/boocchandy-source/F2M-Auto-Hub)

A web version of the F2M Auto-Hub Tires & Mags Trading customer-service and
automotive-shop system. The original Tkinter desktop program is still included as
`armian F2M system.py`; this Flask application is the deployable web port.

The repository is ready for GitHub → Render deployment: GitHub Actions runs the
test suite on every push, Render's Blueprint deploys `main` after CI passes, and
the private customer dataset is mounted as a secret instead of being committed.

## What it does

- Administrator sign-in with CSRF protection, login rate limiting, secure session
  cookies, and hardened response headers.
- Dashboard with customer, vehicle, request, appointment, and concern totals.
- Customer records with automatic vehicle creation and search.
- Vehicle information with plate-number duplicate checks.
- Daily Customer Record browser with date selection, search, and pagination. It
  imports the private company workbook (1,221 visits in the current dataset) once
  a local or mounted JSON file is supplied.
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
- GitHub Actions CI, Dependabot updates, and Render auto-deploy from `main`.

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

The real customer workbook is **not stored in git**. To import it locally, place
the JSON at `f2m/data/customer_records.json`, or point `SEED_DATA_FILE` at it.
Without the file the app starts with no imported visits and logs a warning; demo
records are controlled separately by `SEED_DEMO_DATA`. See
[`f2m/data/README.md`](f2m/data/README.md) for the format and a synthetic sample.

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
Render's Postgres URL formats. Import tests use a small synthetic dataset, so they
run without the private workbook. A local-only check verifies the real 1,221-row
dataset when `f2m/data/customer_records.json` is present.

Useful checks:

```powershell
python -m compileall f2m wsgi.py run.py
pytest -q
```

GitHub Actions runs the same suite plus a production-entry-point smoke check on
every push and pull request. The workflow is
[`.github/workflows/ci.yml`](.github/workflows/ci.yml); Dependabot keeps Python
and Action versions current.

## Deploy to Render

### GitHub and continuous integration

This repository is already connected to
[`boocchandy-source/F2M-Auto-Hub`](https://github.com/boocchandy-source/F2M-Auto-Hub).
The deployment flow is:

1. Commit and push to `main`.
2. GitHub Actions installs dependencies, runs `pytest`, and smoke-tests
   `wsgi:app`.
3. Render's Blueprint deploys only after the CI check passes, then verifies
   `/healthz`.

If you recreate the repository from scratch:

```powershell
git init
git add .
git commit -m "F2M Auto-Hub web system"
git branch -M main
# Create an empty GitHub repository first, then:
git remote add origin https://github.com/YOUR-ACCOUNT/YOUR-REPO.git
git push -u origin main
```

`.gitignore` excludes `.venv/`, local databases, `.env`, caches, and
`f2m/data/*` (except the documentation and synthetic example). Never commit a
filled-in `.env` or the real customer records.

### Private customer dataset (do not commit)

The real workbook contains customer names and plate numbers, so it stays out of
git. To seed a deployment safely:

1. In the Render Dashboard open the service → **Environment** → **Secret Files**
   → **Add Secret File**.
2. Name it `customer_records.json` and paste the private JSON contents.
3. Both Blueprints already point `SEED_DATA_FILE` at their storage location
   (`/etc/secrets/customer_records.json` for the free Blueprint,
   `/var/data/customer_records.json` for the disk Blueprint), so no extra
   variable is needed when you use those names. If you use a different name or
   location, set `SEED_DATA_FILE` to the matching path.
4. Save and redeploy. The importer runs on the first boot.
5. If the service had already booted before the file was added, redeploy it. The
   app deliberately does not write `seed_version` when the file is missing, so the
   next boot imports the file. On a service with shell access,
   `flask --app wsgi seed-db --force` imports it without wiping the database.
6. With `render.disk.yaml`, copy the file onto the persistent disk at
   `/var/data/customer_records.json` (the Blueprint already points
   `SEED_DATA_FILE` there).

Without a mounted file the app starts with an empty visit list and logs a warning.
`f2m/data/customer_records.example.json` is a synthetic sample for local
development only; it is not imported automatically.

### Option A — free demo (default `render.yaml`)

This Blueprint creates a free Python web service plus a free Render Postgres
database.

1. Push this folder to a GitHub (or GitLab) repository.
2. In the Render Dashboard choose **New → Blueprint**.
3. Connect the repository. Render reads `render.yaml` automatically.
4. When prompted, enter a strong value for `ADMIN_PASSWORD`.
5. Apply the Blueprint and wait for the deploy and health check to pass.
6. Open the service URL and sign in as `admin` with the password you entered.

On first boot the app imports the mounted Daily Customer Record file (1,221 rows
for the current dataset). Without a mounted file it starts with an empty visit
list. Demo records are disabled by default in the Blueprint; set
`SEED_DEMO_DATA=1` and redeploy on an empty database if you want sample workflow
data.

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
| `SEED_DATA_FILE` | No | `f2m/data/customer_records.json` | Path to the private JSON. Both Blueprints set it to the mounted Secret File path (`/etc/secrets/customer_records.json` or `/var/data/customer_records.json`). |
| `SEED_DEMO_DATA` | No | `1` (app); `0` in Blueprints | Add six demo customers and sample workflow records. |
| `TRUST_PROXY_HEADERS` | No | `1` on Render | Trust Render's proxy headers for scheme and client IP. |
| `PORT` | No | `5000` locally | Injected by Render/Gunicorn. |

To generate a password hash:

```powershell
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-password'))"
```

Then set `ADMIN_PASSWORD_HASH` and remove `ADMIN_PASSWORD` from the environment.

## Data and seeding

- The private workbook is read from `f2m/data/customer_records.json` by default,
  or from the path in `SEED_DATA_FILE`. It is deliberately **not committed**.
- With the current company dataset, a successful first boot imports **1,221
  visits**, **1,122 customers**, and **1,113 vehicles**, then records
  `seed_version` in the `system_meta` table.
- Subsequent boots skip the import, so deploys and restarts are safe.
- If no readable workbook is found, the app logs a warning and does **not** write
  `seed_version`. Mounting the file later and restarting (or running
  `seed-db --force`) imports it without wiping existing data.
- `SEED_DEMO_DATA=1` adds six demo customers plus sample appointments, requests,
  history, feedback, and notifications. It is helpful for a local walkthrough or a
  showcase deployment. Both Render Blueprints set it to `0` so a production
  database starts with only the imported records.
- Visits are deduplicated on the complete row, not on `(date, record number)`,
  because the source workbook can repeat record numbers across different tables.
- Demo records can be deleted from the UI after the first boot.
- [`f2m/data/README.md`](f2m/data/README.md) documents the JSON format, and
  `customer_records.example.json` provides synthetic rows for development.

Maintenance commands (run against the configured database):

```powershell
flask --app wsgi init-db          # create missing tables only
flask --app wsgi seed-db          # import the workbook if it has not been imported
flask --app wsgi seed-db --force  # import missing rows even if a seed completed
flask --app wsgi reset-data       # DESTRUCTIVE: drop all tables, recreate, re-import
```

`seed-db --force` is the safe choice after mounting the private file on an
existing deployment; it does not delete data. `reset-data` deletes every customer,
visit, request, appointment, history record, concern, and notification. Back up
first.

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
  data/README.md            Private seed-file format and setup
  data/customer_records.example.json  Synthetic sample rows
  static/                   CSS, JS, logo, favicon
  templates/                Jinja templates
tests/                      Pytest suite
.github/workflows/ci.yml    GitHub Actions tests + production smoke check
.github/dependabot.yml      Weekly Python and Actions update PRs
SECURITY.md                 Vulnerability reporting and deployment baseline
requirements.txt            Production dependencies
requirements-dev.txt        Test dependencies
run.py                      Local development server
wsgi.py                     Gunicorn entry point (`gunicorn wsgi:app`)
render.yaml                 Free web + free Postgres Blueprint
render.disk.yaml            Paid web + persistent SQLite disk Blueprint
Procfile                    Generic process definition for WSGI hosts
```

## Deployment notes

- Every push to `main` runs GitHub Actions (`.github/workflows/ci.yml`). Both
  Blueprints use `autoDeployTrigger: checksPass`, so Render deploys only after
  that CI check succeeds. A failed check leaves the previous deployment live.
- The private dataset must be supplied as a mounted file. It is gitignored and is
  therefore absent from the GitHub repository and every Render build.
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
| Deployed app shows 0 visits / “data file not found” in logs | Upload the private JSON as a Render Secret File and set `SEED_DATA_FILE` to its mount path, then redeploy. On a shell-enabled service, `flask --app wsgi seed-db --force` imports it without wiping data. |
| App started empty before the data file was mounted | The seed marker is intentionally not written when the file is missing. Add `SEED_DATA_FILE`, restart or redeploy; existing demo/entered data is preserved. |
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
