from __future__ import annotations
import os
import uuid
from typing import Iterable

_DEFAULT_ALLOWED = {"pdf","doc","docx","xls","xlsx","ppt","pptx","txt","rtf"}

def _parse_allowed_env(value: str | None) -> set[str]:
    if not value:
        return set(_DEFAULT_ALLOWED)
    return {p.strip().lstrip(".").lower() for p in value.split(",") if p.strip()}

def is_file_allowed(filename: str, allowed: Iterable[str] | None = None) -> bool:
    """
    True if the file's extension is in the allowlist.
    Uses env ALLOWED_EXTENSIONS="pdf,docx,..." if provided; falls back to sane defaults.
    """
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower()
    allowed_set = set(a.lower().lstrip(".") for a in (allowed or _parse_allowed_env(os.getenv("ALLOWED_EXTENSIONS"))))
    return ext in allowed_set

def generate_job_id() -> str:
    """Return a unique job id."""
    return str(uuid.uuid4())
