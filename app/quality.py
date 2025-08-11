import hashlib, os, re
from typing import Optional

def sha256_file(path: str, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def clean_markdown(md: str) -> str:
    if not md: return md
    # Normalize line endings
    md = md.replace("\r\n", "\n").replace("\r", "\n")
    # Trim trailing spaces
    md = "\n".join(line.rstrip() for line in md.split("\n"))
    # Collapse >2 blank lines to exactly 2
    md = re.sub(r"\n{3,}", "\n\n", md)
    # Normalize fenced code blocks ```lang ... ```
    md = re.sub(r"(```+)\s*\n", r"```\n", md)
    # Remove obvious page footer/header repeats if they appear on many lines (simple heuristic)
    # (Keep conservative: only strip 1-2 word all-caps lines repeated 10+ times)
    lines = md.split("\n")
    freq = {}
    for ln in lines:
        if 2 <= len(ln) <= 40 and ln.isupper():
            freq[ln] = freq.get(ln, 0) + 1
    common = {k for k, v in freq.items() if v >= 10}
    if common:
        lines = [ln for ln in lines if ln not in common]
        md = "\n".join(lines)
    return md.strip()

def pdf_text_fallback(path: str) -> Optional[str]:
    try:
        from pdfminer.high_level import extract_text
        txt = extract_text(path) or ""
        txt = txt.strip()
        if not txt: return None
        # naive paragraphs → markdown paragraphs
        paragraphs = [p.strip() for p in txt.split("\n\n") if p.strip()]
        return "\n\n".join(paragraphs)
    except Exception:
        return None
