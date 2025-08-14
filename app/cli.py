import os
from datetime import datetime
from flask import current_app
from app import create_app, db
from .models_conversion import Conversion
from .cleanup import run_cleanup_tasks

from google.cloud import storage

def _delete_gcs_uri(uri: str):
    if not uri or not uri.startswith("gs://"):
        return
    bucket_name, blob_path = uri.replace("gs://", "").split("/", 1)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    try:
        blob.delete()
    except Exception:
        pass

def cleanup_impl(retention_days: int, delete_gcs: bool):
    cutoff = datetime.utcnow().fromtimestamp(int(datetime.utcnow().timestamp() - retention_days*86400))
    q = (Conversion.query
         .filter(Conversion.created_at < cutoff))
    count = 0
    for row in q:
        if delete_gcs and row.stored_uri:
            _delete_gcs_uri(row.stored_uri)
        db.session.delete(row); count += 1
    db.session.commit()
    return count

def backfill_sha_impl():
    from .quality import sha256_file
    import tempfile, requests
    changed = 0
    for c in Conversion.query.filter(Conversion.sha256.is_(None)).all():
        # cannot rebuild without a stored file; skip unless stored_uri exists
        if not c.stored_uri or not c.stored_uri.startswith("gs://"):
            continue
        # best-effort: download to tmp
        # (skip: we do not have signed URLs here; left as placeholder)
        pass
    return changed

# Flask CLI adapters
def register_cli(app):
    @app.cli.command("cleanup")
    def cleanup_cmd():
        days = int(os.getenv("RETENTION_DAYS", "30"))
        delete_gcs = os.getenv("CLEANUP_DELETE_GCS", "1").lower() in ("1","true","yes")
        n = cleanup_impl(days, delete_gcs)
        print(f"[cleanup] deleted {n} rows older than {days} days")

    @app.cli.command("cleanup-run-once")
    def cleanup_run_once():
        """Run cleanup process once manually."""
        print("Starting manual cleanup...")
        result = run_cleanup_tasks()
        
        # Print results
        print(f"Cleanup completed at {result['timestamp']}")
        print(f"Expired proposals cleaned up: {result['expired_proposals']}")
        print(f"Orphaned documents cleaned up: {result['orphaned_documents']}")
        print(f"Orphaned requirements cleaned up: {result['orphaned_requirements']}")
        
        return 0

    @app.cli.command("backfill-sha")
    def backfill_sha():
        n = backfill_sha_impl()
        print(f"[backfill-sha] updated {n} rows")
