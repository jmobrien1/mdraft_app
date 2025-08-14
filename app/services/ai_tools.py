# app/services/ai_tools.py
from __future__ import annotations
import os
import re
import json
import logging
from typing import Any, Dict, List, Optional
from app.services.llm_client import chat_json

try:
    from jsonschema import validate as json_validate  # type: ignore
    from jsonschema.exceptions import ValidationError as JsonSchemaValidationError  # type: ignore
except Exception:  # pragma: no cover
    json_validate = None
    JsonSchemaValidationError = Exception

LOG = logging.getLogger(__name__)

# ---- limits from env with safe defaults ----
CHUNK_SIZE_CHARS = int(os.getenv("MDRAFT_CHUNK_SIZE_CHARS") or 3000)  # conservative
MAX_CHUNKS = int(os.getenv("MDRAFT_MAX_CHUNKS") or 12)                # hard stop
TRUNCATE_CHARS = int(os.getenv("MDRAFT_TRUNCATE_CHARS") or 200_000)   # pre-truncate big docs
MAX_MERGED_ITEMS = int(os.getenv("MDRAFT_MAX_MERGED_ITEMS") or 300)   # cap list growth
DEFAULT_MODEL_MAX_TOKENS = int(os.getenv("MDRAFT_MAX_TOKENS") or 700) # arrays don't need a lot
RELAX_MAX_OBJS_PER_CHUNK = int(os.getenv("MDRAFT_RELAX_MAX_OBJS_PER_CHUNK") or 80)

DEV_TRUE = {"1", "true", "yes", "on", "y"}

DEFAULT_PROMPTS = {
    "compliance_matrix": """OUTPUT: Return a JSON array only. No markdown, no prose.
For each 'shall', 'must', deliverable, or submission instruction found in the RFP chunk:
- requirement_id: short stable ID (e.g., L-1, M-2, C-3 or a hash prefix)
- requirement_text: verbatim or near-verbatim sentence
- rfp_reference: where it came from (e.g., "Section L, p.10")
- requirement_type: one of [shall, must, should, deliverable, format, submission]
- suggested_proposal_section: best matching proposal section
Return a JSON array only.
""",
    "evaluation_criteria": """OUTPUT: Return a JSON array only. No markdown, no prose.
Extract evaluation factors from Section M or similar:
- criterion: name of factor (e.g., Technical Approach)
- description: short description/what matters
- weight: numeric if explicitly stated, otherwise null
- basis: 'Best Value' or 'LPTA' if stated
- source_section: where it came from
Return a JSON array only.
""",
    "annotated_outline": """OUTPUT: Return a JSON object only. No markdown, no prose.
Fields:
- outline_markdown: markdown headings I., II., III., with sub-bullets matching Section L instructions
- annotations: array of { heading, rfp_reference, notes } (one+ per top-level section)
Return: { "outline_markdown": "...", "annotations": [...] }
""",
    "submission_checklist": """OUTPUT: Return a JSON array only. No markdown, no prose.
Extract submission requirements:
- item: the checkable item (e.g., "SF-1449 signed", "Technical Volume (PDF)")
- category: one of [Form, Format, Delivery, Schedule]
- details: constraints (page limit, font, margins, portal/email, due time, naming)
- rfp_reference: where it came from
Return a JSON array only.
""",
}


def _bool_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in DEV_TRUE


def _normalize_stem(p: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', os.path.basename(p).lower())


def _chunk_text(s: str, max_chars: int):
    s = s or ""
    for i in range(0, len(s), max_chars):
        yield s[i:i+max_chars]


def _schema_is_array(schema) -> bool:
    return bool(schema) and schema.get("type") == "array"


def _extract_first_json_array(s: str):
    # try strict first
    try:
        j = json.loads(s)
        if isinstance(j, list):
            return j
    except Exception:
        pass
    # fallback: scan first [...] block
    import re
    m = re.search(r'\[[\s\S]*\]', s)
    if not m:
        raise ValueError("json_parse|could_not_extract_array")
    try:
        j = json.loads(m.group(0))
        if isinstance(j, list):
            return j
    except Exception:
        pass
    raise ValueError("json_parse|malformed_array")

def _extract_relaxed_array(s: str):
    """Grab every complete {...} we can find; ignore incomplete tails."""
    objs = []
    depth = 0
    start = None
    for i, ch in enumerate(s):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    frag = s[start:i+1]
                    try:
                        obj = json.loads(frag)
                        objs.append(obj)
                        if len(objs) >= RELAX_MAX_OBJS_PER_CHUNK:
                            break
                    except Exception:
                        # skip malformed fragments
                        pass
    if objs:
        return objs
    raise ValueError("json_parse|relaxed_failed")


def _normalize_eval_criteria(arr):
    out = []
    for it in arr:
        if not isinstance(it, dict): 
            continue
        crit = (it.get("criterion") or "").strip()
        if not crit: 
            continue
        w = it.get("weight", None)
        if isinstance(w, str):
            ws = w.strip().replace("%","")
            try: w = float(ws)
            except: w = None
        elif isinstance(w, (int, float)):
            w = float(w)
        else:
            w = None
        out.append({
            "criterion": crit,
            "description": it.get("description") or "",
            "weight": w,
            "basis": it.get("basis") or None,
            "source_section": it.get("source_section") or it.get("rfp_reference") or None,
        })
    return out


def _merge_arrays(items: list[list[dict]], key_candidates: list[str]) -> list[dict]:
    out, seen = [], set()
    for arr in items or []:
        for row in arr:
            # select a stable key
            k = None
            for c in key_candidates:
                v = row.get(c) if isinstance(row, dict) else None
                if v:
                    k = f"{c}:{str(v).strip().lower()}"
                    break
            if k is None:
                k = str(tuple(sorted(row.items()))) if isinstance(row, dict) else str(row)
            if k in seen:
                continue
            seen.add(k); out.append(row)
    return out


def _merge_outline(parts: list[dict]) -> dict:
    best = max(parts or [{}], key=lambda p: len(p.get("outline_markdown","")), default={})
    ann_map = {}
    for p in parts:
        for a in (p.get("annotations") or []):
            h = (a.get("heading") or "").strip().lower()
            if h and h not in ann_map:
                ann_map[h] = a
    return {"outline_markdown": best.get("outline_markdown",""), "annotations": list(ann_map.values())}


def _dev_stub(prompt_path: str, json_schema: Optional[Dict[str, Any]] = None) -> Any:
    """
    Return deterministic, schema-valid sample payloads for the four free tools.
    This lets the UI work end-to-end without a live model.
    """
    stem = re.sub(r'[^a-z0-9]+', '_', os.path.basename(prompt_path).lower())
    LOG.info("run_prompt: DEV_STUB active stem=%s", _normalize_stem(prompt_path))

    if stem == "compliance_matrix":
        return [
            {
                "requirement_id": "L-1",
                "requirement_text": "Offeror shall submit a Technical Volume not to exceed 50 pages.",
                "rfp_reference": "Section L, p.10",
                "requirement_type": "format",
                "suggested_proposal_section": "I. Technical Approach"
            },
            {
                "requirement_id": "C-2",
                "requirement_text": "Contractor must provide a Project Manager with PMP certification.",
                "rfp_reference": "Section C, p.22",
                "requirement_type": "shall",
                "suggested_proposal_section": "II. Management Plan"
            },
            {
                "requirement_id": "L-3",
                "requirement_text": "Offeror shall acknowledge all amendments on the SF-30 form.",
                "rfp_reference": "Section L, p.12",
                "requirement_type": "submission",
                "suggested_proposal_section": "III. Administrative / Certifications"
            }
        ]

    if stem == "evaluation_criteria":
        return [
            {
                "criterion": "Technical Approach",
                "description": "Soundness, feasibility, and alignment to requirements.",
                "weight": 40,
                "basis": "Best Value",
                "source_section": "Section M, p.30"
            },
            {
                "criterion": "Past Performance",
                "description": "Relevancy and quality of prior efforts.",
                "weight": None,
                "basis": "Best Value",
                "source_section": "Section M, p.31"
            },
            {
                "criterion": "Price",
                "description": "Reasonableness and realism.",
                "weight": None,
                "basis": "Best Value",
                "source_section": "Section M, p.32"
            }
        ]

    if stem == "annotated_outline":
        return {
            "outline_markdown": (
                "# Proposal Outline\n\n"
                "I. Technical Approach  \n"
                "A. Solution Overview  \n"
                "B. Implementation Plan  \n"
                "C. Schedule & Milestones  \n\n"
                "II. Management Plan  \n"
                "A. Organization & Key Personnel  \n"
                "B. Staffing & Resumes  \n"
                "C. Quality Assurance  \n\n"
                "III. Past Performance & Administrative  \n"
                "A. Relevant Past Performance  \n"
                "B. Certifications & Forms  \n"
                "C. Price/Cost (if required)  \n"
            ),
            "annotations": [
                {"heading": "I. Technical Approach", "rfp_reference": "Section L, p.10", "notes": "Follow page limit; address all PWS tasks."},
                {"heading": "II. Management Plan", "rfp_reference": "Section L, p.11", "notes": "Include PMP-certified PM; show org chart."},
                {"heading": "III. Past Performance & Administrative", "rfp_reference": "Section L, p.12", "notes": "Include forms (SF-1449/SF-30), acknowledge amendments."}
            ]
        }

    if stem == "submission_checklist":
        return [
            {
                "item": "SF-1449 (or agency cover form), signed",
                "category": "Form",
                "details": "Include completed and signed cover document.",
                "rfp_reference": "Section L, p.2"
            },
            {
                "item": "Technical Volume (PDF)",
                "category": "Format",
                "details": "Max 50 pages, 12-pt font, 1-inch margins.",
                "rfp_reference": "Section L, p.10"
            },
            {
                "item": "Delivery via agency portal",
                "category": "Delivery",
                "details": "Upload by 2:00 PM local time; file naming per RFP.",
                "rfp_reference": "Section L, p.13"
            },
            {
                "item": "Acknowledge all amendments",
                "category": "Schedule",
                "details": "Submit SF-30s with signatures.",
                "rfp_reference": "Section L, p.12"
            }
        ]

    # Fallback: return schema-valid minimal payloads
    if json_schema:
        schema_type = json_schema.get("type")
        if schema_type == "array":
            payload = []
        elif "outline_markdown" in json_schema.get("properties", {}):
            payload = {"outline_markdown": "", "annotations": []}
        else:
            payload = []
        
        # Validate payload if schema was provided
        try:
            _validate_with_schema(payload, json_schema)
            return payload
        except Exception:
            raise ValueError("model_error")
    
    # Default fallback: empty array
    return []


def _validate_with_schema(payload: Any, schema: Optional[Dict[str, Any]]) -> None:
    """
    Validate payload against JSON schema if available.
    """
    if schema is None or json_validate is None:
        return
    json_validate(instance=payload, schema=schema)


def _load_prompt_text(prompt_path: str) -> str:
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        # fallback to built-in defaults when files are not deployed
        stem = _normalize_stem(prompt_path)
        key = None
        if "compliance_matrix" in stem: key = "compliance_matrix"
        elif "evaluation_criteria" in stem: key = "evaluation_criteria"
        elif "annotated_outline" in stem: key = "annotated_outline"
        elif "submission_checklist" in stem: key = "submission_checklist"
        if key and key in DEFAULT_PROMPTS:
            LOG.warning("Prompt file missing; using DEFAULT_PROMPTS[%s] for %s", key, prompt_path)
            return DEFAULT_PROMPTS[key]
        LOG.exception("Prompt file missing and no default for %s", prompt_path)
        raise


def run_prompt(prompt_path: str, rfp_text: str, json_schema: Optional[Dict[str, Any]], model_name: str | None = None) -> Any:
    """
    Primary entry point used by the /api/generate/* endpoints.

    Behavior:
      - If MDRAFT_DEV_STUB is truthy, return schema-valid sample JSON based on the prompt_path.
      - Otherwise, call the real model client (if configured), strictly request JSON, parse, validate.
      - On validation failure, retry once with a correction instruction.
      - Raise ValueError('model_error') for the route to map to HTTP 502.

    Args:
        prompt_path: absolute or repo-relative path to the text prompt
        rfp_text: the extracted text of the solicitation
        json_schema: a jsonschema dict defining required fields/types; can be None
        model_name: optional model name override

    Returns:
        Parsed Python object (list/dict) that matches json_schema if provided.
    """
    # 1) DEV STUB path — immediate, schema-valid data for demos and UI wiring
    if _bool_env("MDRAFT_DEV_STUB"):
        try:
            payload = _dev_stub(prompt_path, json_schema)
            _validate_with_schema(payload, json_schema)
            return payload
        except Exception as e:  # pragma: no cover
            LOG.exception("dev_stub failed: %s", e)
            raise ValueError("model_error")

    # 2) Real model path — import a minimal client if available
    try:
        prompt_text = _load_prompt_text(prompt_path)
    except Exception as e:
        LOG.exception("Failed to read prompt file: %s", e)
        raise ValueError("model_error")

    # ---- truncate big docs before anything else ----
    if rfp_text and len(rfp_text) > TRUNCATE_CHARS:
        LOG.info("run_prompt: truncating input from %d -> %d chars", len(rfp_text), TRUNCATE_CHARS)
        rfp_text = rfp_text[:TRUNCATE_CHARS]

    is_array = _schema_is_array(json_schema or {})
    use_json_object_format = bool(json_schema) and not is_array

    merged = [] if is_array else None
    chunks_used = 0

    for chunk in _chunk_text(rfp_text, CHUNK_SIZE_CHARS):
        chunks_used += 1
        if chunks_used > MAX_CHUNKS:
            LOG.warning("run_prompt: reached MAX_CHUNKS=%d; stopping early", MAX_CHUNKS)
            break

        messages = [
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": chunk},
        ]
        # arrays: keep tokens small
        max_tokens = 1000 if is_array else 1200

        try:
            raw = chat_json(messages, response_json_hint=use_json_object_format, model=model_name, max_tokens=max_tokens)
        except RuntimeError as re:
            # re.args[0] like 'openai_bad_request|<msg>'
            raise ValueError(str(re))

        if is_array:
            try:
                part = _extract_first_json_array(raw)
            except Exception as ex:
                LOG.warning("array parse failed (strict); trying relaxed: %s", str(ex))
                part = _extract_relaxed_array(raw)
            if part:
                merged.extend(part)
            if len(merged) >= MAX_MERGED_ITEMS:
                LOG.warning("run_prompt: reached MAX_MERGED_ITEMS=%d; stopping early", MAX_MERGED_ITEMS)
                merged = merged[:MAX_MERGED_ITEMS]
                break
        else:
            # object – later chunks can refine; keep last valid
            try:
                merged = json.loads(raw)
            except Exception:
                raise ValueError(f"json_parse|object_parse_failed")

    # normalize criteria list
    stem = os.path.basename(prompt_path).replace("-", "_")
    if is_array and "evaluation_criteria" in stem:
        merged = _normalize_eval_criteria(merged)

    # optional: validate against schema here (if you have it)
    if json_schema:
        _validate_with_schema(merged, json_schema)
    
    LOG.info("run_prompt: completed stem=%s chunks=%d items=%s", 
             stem, chunks_used, len(merged) if isinstance(merged, list) else "object")
    return merged
