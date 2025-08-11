import tempfile, os
from celery_worker import celery
from app import create_app, db
from .models_conversion import Conversion
from .api_convert import _convert_with_markitdown

app = create_app()

@celery.task(name="convert_from_gcs")
def convert_from_gcs(conv_id: str, gcs_uri: str):
    from google.cloud import storage

    with app.app_context():
        conv = db.session.get(Conversion, conv_id)
        if not conv:
            return
        conv.status = "PROCESSING"
        db.session.commit()

        # download to tmp
        bucket_name, blob_path = gcs_uri.replace("gs://", "").split("/", 1)
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            blob.download_to_filename(tmp.name)
            tmp_path = tmp.name

        try:
            markdown = _convert_with_markitdown(tmp_path)
            conv.markdown = markdown
            conv.status = "COMPLETED"
            db.session.commit()
        except Exception as e:
            conv.status = "FAILED"
            conv.error = str(e)
            db.session.commit()
        finally:
            try: os.unlink(tmp_path)
            except Exception: pass
