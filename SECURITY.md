# Security policy

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Use GitHub's
[private vulnerability reporting](https://github.com/boocchandy-source/F2M-Auto-Hub/security/advisories/new)
or contact the repository owner directly. Include the affected route, steps to
reproduce, and any relevant logs. Please allow a reasonable amount of time for a
fix before public disclosure.

## Deployment baseline

Before exposing the app publicly:

1. Set `SECRET_KEY` to a long random value. Render's Blueprint generates one.
2. Set a strong `ADMIN_PASSWORD` or `ADMIN_PASSWORD_HASH`. Never keep the
   `admin123` default.
3. Keep `SESSION_COOKIE_SECURE=1` on HTTPS deployments.
4. Do not commit `.env`, `instance/`, or the real
   `f2m/data/customer_records.json`. They are excluded by `.gitignore`.
5. Upload the customer dataset as a Render Secret File (or another private
   mount), not as a repository file.
6. Use a single Gunicorn worker for the SQLite/persistent-disk deployment. Do not
   attach a persistent disk to more than one instance.
7. Back up the database before changing plans or running `reset-data`.

## Supported versions

This is a single-branch deployment project; security fixes are applied to
`main`. Keep dependencies current through Dependabot pull requests and re-run CI
before merging.
