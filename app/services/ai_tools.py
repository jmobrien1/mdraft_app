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


def _normalize_stem(p: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', os.path.basename(p).lower())


def _chunk_text(s: str, max_chars: int = 10000) -> list[str]:
    # split on paragraph boundaries when possible
    parts, cur = [], []
    total = 0
    for line in s.splitlines(True):
        cur.append(line)
        total += len(line)
        if total >= max_chars and line.strip() == "":
            parts.append("".join(cur)); cur=[]; total=0
    if cur: parts.append("".join(cur))
    return parts


def _is_array_schema(schema) -> bool:
    return bool(schema) and schema.get("type") == "array"


def _merge_arrays(items: list[list[dict]], key_candidates: list[str]) -> list[dict]:
    out, seen = [], set()
    for arr in items:
        for row in arr:
            # pick first available key or stable tuple
            k = None
            for c in key_candidates:
                if isinstance(row, dict) and row.get(c):
                    k = f"{c}:{str(row[c]).strip().lower()}"
                    break
            if k is None:
                k = str(tuple(sorted(row.items())))  # fallback
            if k in seen:  # keep the longest details
                continue
            seen.add(k)
            out.append(row)
    return out


def _merge_outline(parts: list[dict]) -> dict:
    # keep longest outline_markdown; merge annotations by heading
    best = max(parts, key=lambda p: len(p.get("outline_markdown","")), default={"outline_markdown":"", "annotations":[]})
    ann_map = {}
    for p in parts:
        for a in p.get("annotations", []):
            h = (a.get("heading") or "").strip().lower()
            if h and h not in ann_map:
                ann_map[h] = a
    merged = {"outline_markdown": best.get("outline_markdown",""), "annotations": list(ann_map.values())}
    return merged


def _dev_stub(prompt_path: str, json_schema: Optional[Dict[str, Any]] = None) -> Any:
    """
    Return deterministic, schema-valid sample payloads for the four free tools.
    This lets the UI work end-to-end without a live model.
    """
    stem = re.sub(r'[^a-z0-9]+', '_', os.path.basename(prompt_path).lower())
    LOG.info("DEV STUB HIT: %s => %s", prompt_path, stem)

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

    # Build strict JSON-only messages
    system_msg = {
        "role": "system",
        "content": (
            "You are a specialized proposal assistant. "
            "Respond with VALID JSON ONLY that matches the required schema. "
            "Do not include any prose or markdown."
        ),
    }
    user_msg_base = (
        f"{prompt_text}\n\n---\n"
        f"RFP_TEXT_START\n{rfp_text}\nRFP_TEXT_END"
    )

    def _process_chunks() -> Any:
        chunks = _chunk_text(rfp_text)
        partials = []
        for i, ch in enumerate(chunks):
            messages_i = [system_msg, {"role":"user","content": user_msg_base.replace("RFP_TEXT_START", f"RFP_TEXT_CHUNK_{i}_START").replace("RFP_TEXT_END", f"RFP_TEXT_CHUNK_{i}_END").replace(rfp_text, ch)}]
            raw = chat_json(messages_i, response_json_hint=bool(json_schema))
            try:
                parsed = json.loads(raw)
            except Exception as e:
                LOG.warning("Model returned non-JSON or invalid JSON: %s", e)
                raise ValueError("model_error")
            _validate_with_schema(parsed, json_schema)
            partials.append(parsed)

        # Merge:
        if _is_array_schema(json_schema):
            # choose key candidates by file type
            key_candidates = []
            stem = _normalize_stem(prompt_path)
            if "compliance_matrix" in stem: key_candidates = ["requirement_id","requirement_text"]
            elif "evaluation_criteria" in stem: key_candidates = ["criterion"]
            elif "submission_checklist" in stem: key_candidates = ["item"]
            merged = _merge_arrays(partials, key_candidates)
        else:
            # outline schema
            merged = _merge_outline(partials)

        _validate_with_schema(merged, json_schema)
        return merged

    # First attempt
    try:
        return _process_chunks()
    except JsonSchemaValidationError as ve:
        LOG.warning("JSON schema validation failed on first try: %s", ve)
        # Retry once with a correction hint
        correction = (
            "\n\nIMPORTANT: Your previous response did not match the required JSON schema. "
            "Return VALID JSON ONLY that matches exactly. No prose."
        )
        try:
            # Update user message with correction hint
            user_msg_base_with_correction = user_msg_base + correction
            chunks = _chunk_text(rfp_text)
            partials = []
            for i, ch in enumerate(chunks):
                messages_i = [system_msg, {"role":"user","content": user_msg_base_with_correction.replace("RFP_TEXT_START", f"RFP_TEXT_CHUNK_{i}_START").replace("RFP_TEXT_END", f"RFP_TEXT_CHUNK_{i}_END").replace(rfp_text, ch)}]
                raw = chat_json(messages_i, response_json_hint=bool(json_schema))
                try:
                    parsed = json.loads(raw)
                except Exception as e:
                    LOG.warning("Model returned non-JSON or invalid JSON: %s", e)
                    raise ValueError("model_error")
                _validate_with_schema(parsed, json_schema)
                partials.append(parsed)

            # Merge:
            if _is_array_schema(json_schema):
                key_candidates = []
                stem = _normalize_stem(prompt_path)
                if "compliance_matrix" in stem: key_candidates = ["requirement_id","requirement_text"]
                elif "evaluation_criteria" in stem: key_candidates = ["criterion"]
                elif "submission_checklist" in stem: key_candidates = ["item"]
                merged = _merge_arrays(partials, key_candidates)
            else:
                merged = _merge_outline(partials)

            _validate_with_schema(merged, json_schema)
            return merged
        except Exception as e:
            LOG.exception("Second attempt failed: %s", e)
            raise ValueError("model_error")
    except Exception as e:
        LOG.exception("Model invocation failed: %s", e)
        raise ValueError("model_error")
