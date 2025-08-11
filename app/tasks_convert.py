import tempfile, os
from celery_worker import celery
from app import create_app, db
from .models_conversion import Conversion
from .api_convert import _convert_with_markitdown
from .quality import clean_markdown, pdf_text_fallback

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
            markdown = _convert_with_markitdown(tmp_path) or ""
            if not markdown and conv.original_mime == "application/pdf":
                fb = pdf_text_fallback(tmp_path)
                if fb: markdown = fb
            conv.markdown = clean_markdown(markdown)
            conv.status = "COMPLETED"
            db.session.commit()
        except Exception as e:
            conv.status = "FAILED"
            conv.error = str(e)
            db.session.commit()
        finally:
            try: os.unlink(tmp_path)
            except Exception: pass
            
            # Delete GCS object to save storage costs
            delete_on_done = os.getenv("DELETE_GCS_ON_COMPLETE", "1").lower() in ("1","true","yes")
            if delete_on_done:
                try:
                    bucket.delete_blob(blob.path if hasattr(blob, "path") else blob.name)
                except Exception:
                    pass
