"""WSGI entry point used by Gunicorn on Render: ``gunicorn wsgi:app``."""

from f2m import create_app

app = create_app()

if __name__ == "__main__":  # pragma: no cover - convenience for local use
    app.run(host="127.0.0.1", port=5000, debug=False)
