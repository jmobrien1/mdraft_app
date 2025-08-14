"""
Operations API endpoints for monitoring and debugging.
"""

from flask import Blueprint, jsonify, current_app
from sqlalchemy import text
from app import db

ops = Blueprint("ops", __name__)


@ops.get("/api/ops/migration_status")
def migration_status():
    """Check migration status and schema health."""
    try:
        # Read current alembic head & DB version
        head = None
        try:
            # Read head from migrations folder
            from alembic.config import Config
            from alembic.script import ScriptDirectory
            cfg = Config("alembic.ini")
            script = ScriptDirectory.from_config(cfg)
            head = script.get_current_head()
        except Exception as e:
            current_app.logger.warning(f"Could not read alembic head: {e}")
            head = None

        current = None
        try:
            res = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
            current = res
        except Exception as e:
            current_app.logger.warning(f"Could not read current alembic version: {e}")
            current = None

        # Check required columns as specified in requirements
        checks = {}
        for table, col in [("proposals", "visitor_session_id"), ("conversions", "proposal_id")]:
            try:
                cnt = db.session.execute(text("""
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_name=:t AND column_name=:c
                """), {"t": table, "c": col}).scalar()
                checks[f"{table}.{col}"] = (cnt == 1)
            except Exception as e:
                current_app.logger.warning(f"Could not probe {table}.{col}: {e}")
                checks[f"{table}.{col}"] = False

        # Determine overall migration status
        migrated = all(checks.values()) and current is not None and head is not None and current == head

        return jsonify({
            "migrated": migrated,
            "alembic_current": current,
            "checks": checks
        })
    except Exception as e:
        current_app.logger.error(f"Migration status check failed: {e}")
        return jsonify({
            "migrated": False, 
            "error": str(e)
        }), 500
