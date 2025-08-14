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

        # Quick schema probe for required columns
        proposals_has_visitor_session_id = False
        try:
            probe = db.session.execute(text("""
                SELECT COUNT(*) FROM information_schema.columns
                 WHERE table_name='proposals' AND column_name='visitor_session_id'
            """)).scalar()
            proposals_has_visitor_session_id = bool(probe == 1)
        except Exception as e:
            current_app.logger.warning(f"Could not probe proposals schema: {e}")

        # Check conversions table too
        conversions_has_ownership = False
        try:
            probe = db.session.execute(text("""
                SELECT COUNT(*) FROM information_schema.columns
                 WHERE table_name='conversions' AND column_name='user_id'
            """)).scalar()
            conversions_has_ownership = bool(probe == 1)
        except Exception as e:
            current_app.logger.warning(f"Could not probe conversions schema: {e}")

        # Determine overall migration status
        migrated = (
            proposals_has_visitor_session_id and 
            conversions_has_ownership and
            current is not None and
            head is not None and
            current == head
        )

        return jsonify({
            "migrated": migrated,
            "alembic": {
                "current": current,
                "head": head,
                "at_head": current == head if current and head else False
            },
            "schema": {
                "proposals_has_visitor_session_id": proposals_has_visitor_session_id,
                "conversions_has_ownership": conversions_has_ownership
            }
        })
    except Exception as e:
        current_app.logger.error(f"Migration status check failed: {e}")
        return jsonify({
            "migrated": False, 
            "error": str(e)
        }), 500
