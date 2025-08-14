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
                "enum": ["shall", "must", "should", "deliverable", "format", "submission"]
            },
            "suggested_proposal_section": {"type": "string"}
        },
        "required": ["requirement_id", "requirement_text", "rfp_reference", "requirement_type", "suggested_proposal_section"]
    }
}

EVAL_CRITERIA_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "criterion": {"type": "string"},
            "description": {"type": "string"},
            # allow number, string (like "40%"), or null
            "weight": {
                "anyOf": [
                    {"type": "number"},
                    {"type": "string"},
                    {"type": "null"}
                ]
            },
            # make basis optional
            "basis": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "source_section": {"anyOf": [{"type": "string"}, {"type": "null"}]}
        },
        "required": ["criterion"]
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
        "required": ["item", "category", "details", "rfp_reference"]
    }
}
