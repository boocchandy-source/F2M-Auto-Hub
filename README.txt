F2M Auto-Hub Customer Service and Automotive Service Management System
=====================================================================

This folder contains two versions of the system:

1. armian F2M system.py  - the original Tkinter/SQLite desktop application.
2. Flask web application - the version prepared for deployment on Render.

WEB VERSION (recommended)
-------------------------
Files:
- README.md              - full local setup, deployment, and troubleshooting guide.
- run.py                 - local development server.
- wsgi.py                - production entry point (gunicorn wsgi:app).
- render.yaml            - Render Blueprint: free web service + free Postgres.
- render.disk.yaml       - Render Blueprint: paid web service + persistent SQLite disk.
- .github/workflows/ci.yml - GitHub Actions tests and production smoke check.
- SECURITY.md            - vulnerability reporting and deployment baseline.
- requirements.txt       - production Python packages.
- requirements-dev.txt   - test packages.

Quick start (Windows PowerShell):
1. py -3.12 -m venv .venv
2. .\.venv\Scripts\Activate.ps1
3. pip install -r requirements.txt
4. Copy-Item .env.example .env
5. Edit .env and set SECRET_KEY and ADMIN_PASSWORD.
6. python run.py
7. Open http://127.0.0.1:5000

If no password is configured, the default login is admin / admin123. Change it
before putting the system online.

Tests:
- pip install -r requirements-dev.txt
- pytest
- GitHub Actions runs the same suite plus a production smoke check on every push.

Private customer data:
- The real f2m/data/customer_records.json is not included in the repository
  because it contains customer names and plate numbers.
- Put it locally at f2m/data/customer_records.json, or set SEED_DATA_FILE.
- On Render, upload it as a Secret File and set
  SEED_DATA_FILE=/etc/secrets/customer_records.json.
- f2m/data/customer_records.example.json contains synthetic development rows.
- The importer is idempotent. If the app started before the file was mounted,
  redeploy or run: flask --app wsgi seed-db --force

Deploying to Render:
- Push the folder to GitHub, then create a new Blueprint in Render.
- The free render.yaml Blueprint uses Render Postgres. IMPORTANT: free Render
  Postgres databases expire 30 days after creation. See README.md for durable
  options (paid database or render.disk.yaml with a persistent disk).
- Set a strong ADMIN_PASSWORD when Render prompts for it.
- Demo records are disabled in both Blueprints. Set SEED_DEMO_DATA=1 before the
  first deploy if you want sample workflow records for a showcase.
- Free web services spin down after 15 minutes of inactivity and take a little
  longer to respond on the next request.

The web app imports the company's 1,221 Daily Customer Record rows once the
private file is available. The import is idempotent, so restarts and redeploys do
not duplicate data.

DESKTOP VERSION (original)
--------------------------
Files:
- armian F2M system.py: Main Python application.

How to run:
1. Install Python 3 if it is not already installed.
2. Open this folder in PyCharm.
3. Run "armian F2M system.py".

Notes:
- The application uses Python's built-in Tkinter and SQLite libraries.
- The SQLite database file is created beside the Python file when the application
  runs.
- Keep the Python file and its database file in the same folder so the application
  can find its data.
- The desktop file is unchanged; the web app is a separate port.
