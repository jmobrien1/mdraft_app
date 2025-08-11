import uuid
from datetime import datetime
from . import db

class Conversion(db.Model):
    __tablename__ = "conversions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="COMPLETED")  # QUEUED | PROCESSING | COMPLETED | FAILED
    markdown = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Identification & lifecycle
    sha256 = db.Column(db.String(64), index=True, nullable=True)
    original_mime = db.Column(db.String(120), nullable=True)
    original_size = db.Column(db.Integer, nullable=True)
    stored_uri = db.Column(db.String(512), nullable=True)   # e.g., gs://bucket/path
    expires_at = db.Column(db.DateTime, nullable=True)      # optional TTL
