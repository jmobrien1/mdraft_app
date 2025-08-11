import os
import filetype

# max sizes in bytes per category
MAX_BY_TYPE = {
    "text": 5 * 1024 * 1024,       # 5 MB
    "doc":  20 * 1024 * 1024,      # 20 MB (docx, pptx, xlsx, pdf)
    "bin":  10 * 1024 * 1024,      # 10 MB fallback
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
