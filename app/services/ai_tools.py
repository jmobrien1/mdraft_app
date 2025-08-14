# app/services/ai_tools.py
from __future__ import annotations
import os
import re
import json
import logging
from typing import Any, Dict, List, Optional

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


def _dev_stub(prompt_path: str, json_schema: Optional[Dict[str, Any]] = None) -> Any:
    """
    Return deterministic, schema-valid sample payloads for the four free tools.
    This lets the UI work end-to-end without a live model.
    """
    stem = _normalize_stem(prompt_path)
    LOG.info("DEV STUB HIT prompt_path=%r stem=%r", prompt_path, stem)

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
            return []
        elif "outline_markdown" in json_schema.get("properties", {}):
            return {"outline_markdown": "", "annotations": []}
    
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

    # Try to use llm_client if present; otherwise, fail gracefully
    try:
        from app.services.llm_client import chat_json  # type: ignore
    except Exception:
        LOG.error("llm_client not configured; set MDRAFT_DEV_STUB=1 or wire llm_client.py")
        raise ValueError("model_error")

    def _call_and_parse(content_suffix: str = "") -> Any:
        messages = [system_msg, {"role": "user", "content": user_msg_base + content_suffix}]
        raw = chat_json(messages, response_json_hint=bool(json_schema))
        try:
            parsed = json.loads(raw)
        except Exception as e:
            LOG.warning("Model returned non-JSON or invalid JSON: %s", e)
            raise ValueError("model_error")
        _validate_with_schema(parsed, json_schema)
        return parsed

    # First attempt
    try:
        return _call_and_parse()
    except JsonSchemaValidationError as ve:
        LOG.warning("JSON schema validation failed on first try: %s", ve)
        # Retry once with a correction hint
        correction = (
            "\n\nIMPORTANT: Your previous response did not match the required JSON schema. "
            "Return VALID JSON ONLY that matches exactly. No prose."
        )
        try:
            return _call_and_parse(correction)
        except Exception as e:
            LOG.exception("Second attempt failed: %s", e)
            raise ValueError("model_error")
    except Exception as e:
        LOG.exception("Model invocation failed: %s", e)
        raise ValueError("model_error")
