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

DEV_TRUE = {"1", "true", "yes", "on", "y"}


def _bool_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in DEV_TRUE


def _normalize_stem(path: str) -> str:
    import os, re
    return re.sub(r'[^a-z0-9]+', '_', os.path.basename(path).lower())


def _chunk_text(s: str, max_chars: int = 8000) -> list[str]:
    # split on paragraph boundaries; never exceed max_chars
    parts, cur, total = [], [], 0
    for line in s.splitlines(True):
        ln = len(line)
        if total + ln > max_chars and cur:
            parts.append("".join(cur))
            cur, total = [], 0
        cur.append(line); total += ln
    if cur: parts.append("".join(cur))
    return parts or [""]


def _is_array_schema(schema) -> bool:
    return bool(schema) and schema.get("type") == "array"


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
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def run_prompt(prompt_path: str, rfp_text: str, json_schema: Optional[Dict[str, Any]]) -> Any:
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

    # After reading prompt_text, compute:
    stem = _normalize_stem(prompt_path)
    model_name = os.getenv("MDRAFT_MODEL") or "gpt-4o-mini"
    chunks = _chunk_text(rfp_text, max_chars=6000)
    LOG.info("run_prompt: model=%s stem=%s chunks=%d len0=%d", model_name, stem, len(chunks), len(chunks[0]) if chunks else 0)

    def _call_chunk(i, ch):
        # Build messages per-chunk WITHOUT inserting the entire doc anywhere
        messages = [
            {"role":"system","content":"You are a specialized proposal assistant. Respond with VALID JSON ONLY. No prose."},
            {"role":"user","content": f"{prompt_text}\n\n---\nRFP_CHUNK {i+1}/{len(chunks)}\nBEGIN_CHUNK\n{ch}\nEND_CHUNK"}
        ]
        try:
            raw = chat_json(messages, response_json_hint=bool(json_schema), model=model_name)
            return raw
        except RuntimeError as e:
            # Map RuntimeError codes to ValueError codes
            error_code = str(e)
            if error_code in ["openai_auth", "openai_rate_limit", "openai_timeout", "openai_other"]:
                raise ValueError(error_code)
            else:
                raise ValueError("openai_other")

    def _process_chunks() -> Any:
        partials = []
        for i, ch in enumerate(chunks):
            # Log exactly what's being sent to the model
            LOG.info("chunk %d/%d len=%d stem=%s", i+1, len(chunks), len(ch), stem)
            raw = _call_chunk(i, ch)
            try:
                parsed = json.loads(raw)
            except Exception as e:
                LOG.warning("JSON parse fail on chunk %d: %s; first 200 chars: %r", i, e, (raw or "")[:200])
                raise ValueError("json_parse")
            _validate_with_schema(parsed, json_schema)
            partials.append(parsed)

        # Merge partials:
        if _is_array_schema(json_schema):
            if "compliance_matrix" in stem:
                key_candidates = ["requirement_id","requirement_text"]
            elif "evaluation_criteria" in stem:
                key_candidates = ["criterion"]
            elif "submission_checklist" in stem:
                key_candidates = ["item"]
            else:
                key_candidates = []
            merged = _merge_arrays(partials, key_candidates)
        else:
            merged = _merge_outline(partials)

        _validate_with_schema(merged, json_schema)
        LOG.info("merged_ok stem=%s size=%s", stem, (len(merged) if isinstance(merged, list) else len(merged.get('annotations',[]))))
        return merged

    # First attempt
    try:
        return _process_chunks()
    except JsonSchemaValidationError as ve:
        LOG.warning("run_prompt: schema fail; retrying once with correction stem=%s", stem)
        # Retry once with a correction hint
        correction = (
            "\n\nIMPORTANT: Your previous response did not match the required JSON schema. "
            "Return VALID JSON ONLY that matches exactly. No prose."
        )
        try:
            # Update user message with correction hint
            def _call_chunk_with_correction(i, ch):
                # Build messages per-chunk WITHOUT inserting the entire doc anywhere
                messages = [
                    {"role":"system","content":"You are a specialized proposal assistant. Respond with VALID JSON ONLY. No prose."},
                    {"role":"user","content": f"{prompt_text}\n\n---\nRFP_CHUNK {i+1}/{len(chunks)}\nBEGIN_CHUNK\n{ch}\nEND_CHUNK{correction}"}
                ]
                try:
                    raw = chat_json(messages, response_json_hint=bool(json_schema), model=model_name)
                    return raw
                except RuntimeError as e:
                    # Map RuntimeError codes to ValueError codes
                    error_code = str(e)
                    if error_code in ["openai_auth", "openai_rate_limit", "openai_timeout", "openai_other"]:
                        raise ValueError(error_code)
                    else:
                        raise ValueError("openai_other")

            partials = []
            for i, ch in enumerate(chunks):
                # Log exactly what's being sent to the model (retry)
                LOG.info("chunk %d/%d len=%d stem=%s (retry)", i+1, len(chunks), len(ch), stem)
                raw = _call_chunk_with_correction(i, ch)
                try:
                    parsed = json.loads(raw)
                except Exception as e:
                    LOG.warning("JSON parse fail on chunk %d: %s; first 200 chars: %r", i, e, (raw or "")[:200])
                    raise ValueError("json_parse")
                _validate_with_schema(parsed, json_schema)
                partials.append(parsed)

            # Merge:
            if _is_array_schema(json_schema):
                if "compliance_matrix" in stem:
                    key_candidates = ["requirement_id","requirement_text"]
                elif "evaluation_criteria" in stem:
                    key_candidates = ["criterion"]
                elif "submission_checklist" in stem:
                    key_candidates = ["item"]
                else:
                    key_candidates = []
                merged = _merge_arrays(partials, key_candidates)
            else:
                merged = _merge_outline(partials)

            _validate_with_schema(merged, json_schema)
            LOG.info("merged_ok stem=%s size=%s", stem, (len(merged) if isinstance(merged, list) else len(merged.get('annotations',[]))))
            return merged
        except Exception as e:
            LOG.exception("Second attempt failed: %s", e)
            # Re-raise the original error if it's a ValueError with specific code
            if isinstance(e, ValueError):
                raise
            raise ValueError("openai_other")
    except Exception as e:
        LOG.exception("Model invocation failed: %s", e)
        # Re-raise the original error if it's a ValueError with specific code
        if isinstance(e, ValueError):
            raise
        raise ValueError("openai_other")
