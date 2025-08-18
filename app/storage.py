"""
Google Cloud Storage integration for mdraft.

This module provides functions for uploading files to GCS, generating
signed URLs for downloads, and managing file lifecycle. It includes
fallback to local storage for development environments.
"""
from __future__ import annotations

import os
from werkzeug.utils import secure_filename

class LocalStorage:
    def __init__(self, base="/tmp/uploads"):
        self.base = base
        os.makedirs(self.base, exist_ok=True)
    def save(self, file_storage, subdir=""):
        d = os.path.join(self.base, subdir) if subdir else self.base
        os.makedirs(d, exist_ok=True)
        name = secure_filename(file_storage.filename or "upload.bin")
        path = os.path.join(d, name)
        file_storage.save(path)
        return {"backend": "local", "path": path, "name": name}

def init_storage(app):
    backend = (app.config.get("STORAGE_BACKEND") or os.getenv("STORAGE_BACKEND") or "local").lower()
    cred = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/etc/secrets/gcp.json")
    if backend == "gcs" and os.path.exists(cred):
        try:
            from google.cloud import storage as _gcs
            client = _gcs.Client.from_service_account_json(cred)
            bucket = client.bucket(app.config["GCS_BUCKET"])
            app.extensions["storage"] = ("gcs", (client, bucket))
            app.logger.info("GCS storage ready: %s", app.config["GCS_BUCKET"])
            return
        except Exception as e:
            app.logger.exception("GCS init failed; falling back to local: %s", e)
    else:
        if backend == "gcs":
            app.logger.error("GCS creds missing at %s; using local storage", cred)
    app.extensions["storage"] = ("local", LocalStorage(base=os.getenv("UPLOAD_DIR", "/tmp/uploads")))
