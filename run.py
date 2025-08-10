"""
Entry point for running the mdraft application locally.

The application is created by calling create_app() from the app package.  This
pattern follows the factory design used by many Flask projects and allows
configuration to be deferred until runtime.  When executed directly, this
module will read environment variables from a .env file (if present) and
start the development server.
"""
import os

try:
    # Use python-dotenv if available.  This library simplifies loading
    # environment variables from a .env file.  It is declared in
    # requirements.txt, but falling back allows the script to run even
    # if dependencies have not yet been installed.
    from dotenv import load_dotenv  # type: ignore
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore


# Load environment variables from .env at the project root.  The .env file
# should never be committed to version control.  See `.env.example` for a
# template of the required variables.
ENV_PATH = os.path.join(os.path.dirname(__file__), '..', '.env')
if load_dotenv is not None:
    load_dotenv(ENV_PATH)  # type: ignore[arg-type]
else:
    # Manual .env loader as a fallback.  Supports simple KEY=value lines
    # and ignores comments or blank lines.
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, 'r', encoding='utf-8') as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    # Remove possible surrounding quotes
                    value = value.strip().strip('"').strip("'")
                    os.environ.setdefault(key, value)

from app import create_app  # noqa: E402  # import after loading env


def main() -> None:
    """Run the Flask application."""
    app = create_app()
    # Read the port from the environment or default to 5000
    port = int(os.environ.get("PORT", 5000))
    # When FLASK_DEBUG is true the reloader will run this function twice; to
    # avoid duplicate background workers or other side effects, heavy logic
    # should live in the factory itself.
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()