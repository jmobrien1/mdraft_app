import uuid
from datetime import datetime
from . import db

class ApiKey(db.Model):
    __tablename__ = "api_keys"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    key = db.Column(db.String(128), nullable=False, unique=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    rate_limit = db.Column(db.String(64), nullable=False, default="60 per minute")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)
