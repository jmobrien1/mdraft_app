"""
JSON schemas for free tier proposal analysis capabilities.
"""

COMPLIANCE_MATRIX_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "requirement_id": {"type": "string"},
            "requirement_text": {"type": "string"},
            "rfp_reference": {"type": "string"},
            "requirement_type": {
                "type": "string",
                "enum": ["shall", "must", "should", "will", "deliverable", "format", "submission"]
            },
            "suggested_proposal_section": {"type": "string"}
        },
        "required": ["requirement_id", "requirement_text", "rfp_reference", "requirement_type", "suggested_proposal_section"],
        "additionalProperties": True
    }
}

def normalize_requirement(item: dict) -> dict:
    """
    Normalize requirement data before validation.
    Maps common requirement verbs to canonical types for consistency.
    """
    if not isinstance(item, dict):
        return item
    
    # Normalize requirement_type
    req_type = item.get("requirement_type", "").strip().lower()
    mapping = {
        "will": "shall",  # treat 'will' as 'shall' for analytics consistency
        "shall": "shall",
        "must": "must", 
        "should": "should",
        "deliverable": "deliverable",
        "format": "format",
        "submission": "submission"
    }
    
    if req_type in mapping:
        item["requirement_type"] = mapping[req_type]
    
    return item

def normalize_compliance_matrix(data: list) -> list:
    """
    Normalize an entire compliance matrix array.
    """
    if not isinstance(data, list):
        return data
    
    return [normalize_requirement(item) for item in data]

EVAL_CRITERIA_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "criterion": {"type": "string"},
            "description": {"type": "string"},
            "weight": {  # number | string | null
                "anyOf": [{"type": "number"}, {"type": "string"}, {"type": "null"}]
            },
            "basis": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "source_section": {"anyOf": [{"type": "string"}, {"type": "null"}]}
        },
        "required": ["criterion"],
        "additionalProperties": True
    }
}

OUTLINE_SCHEMA = {
    "type": "object",
    "properties": {
        "outline_markdown": {"type": "string"},
        "annotations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "rfp_reference": {"type": "string"},
                    "notes": {"type": "string"}
                },
                "required": ["heading", "rfp_reference", "notes"]
            }
        }
    },
    "required": ["outline_markdown", "annotations"]
}

SUBMISSION_CHECKLIST_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "item": {"type": "string"},
            "category": {
                "type": "string",
                "enum": ["Form", "Volume", "Format", "Delivery", "Schedule", "Certification", "Other"]
            },
            "details": {"type": "string"},
            "rfp_reference": {"type": "string"}
        },
        "required": ["item", "category", "details", "rfp_reference"],
        "additionalProperties": True
    }
}
