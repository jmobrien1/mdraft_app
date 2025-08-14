# run.py (at repo root, same level as requirements/pyproject)
from app import create_app

# Export a concrete Flask app object for Gunicorn "run:app"
app = create_app()

# Optional: local dev entrypoint (ignored by Gunicorn)
if __name__ == "__main__":
    # Use 8084 to match your local docs
    app.run(host="0.0.0.0", port=8084, debug=True)