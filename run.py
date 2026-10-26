"""Local development server for F2M Auto-Hub.

Run with:  python run.py
"""

from __future__ import annotations

import os

from f2m import create_app

app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "1").strip().lower() in {"1", "true", "yes", "on"}
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    print(f"\n  F2M Auto-Hub is starting at http://{host}:{port}\n")
    app.run(host=host, port=port, debug=debug)
