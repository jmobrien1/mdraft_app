import os
import filetype
from .config import get_config

# Get size limits from centralized configuration
config = get_config()
MAX_BY_TYPE = {
    "text": config.get_file_size_limit("text"),
    "doc": config.get_file_size_limit("office"),  # office documents
    "bin": config.get_file_size_limit("binary"),  # fallback
}

ALLOWED_MIMES = {
    # text
    "text/plain": "text",
    "text/markdown": "text",
    "text/csv": "text",
    "application/json": "text",
    # common docs
    "application/pdf": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "doc",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "doc",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "doc",
}

def sniff_category(path: str, fallback_mime: str | None = None) -> tuple[str|None, str|None]:
    kind = filetype.guess(path)
    mime = kind.mime if kind else (fallback_mime or None)
    if not mime:
        return None, None
    category = ALLOWED_MIMES.get(mime)
    return mime, category

def size_ok(path: str, category: str | None) -> bool:
    size = os.path.getsize(path)
    if not category:
        return size <= MAX_BY_TYPE["bin"]
    return size <= MAX_BY_TYPE.get(category, MAX_BY_TYPE["bin"])
