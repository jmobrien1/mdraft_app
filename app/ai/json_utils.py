"""
Robust JSON parsing utilities with repair capabilities.

This module provides a pipeline for parsing JSON from AI responses:
1. Strict parsing
2. Repair attempts
3. Graceful error handling with developer-friendly diagnostics
"""
import json
import re
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

LOG = logging.getLogger(__name__)


def parse_strict(raw_text: str) -> Tuple[bool, Any, Optional[str]]:
    """
    Attempt strict JSON parsing.
    
    Args:
        raw_text: Raw text from AI response
        
    Returns:
        Tuple of (success, parsed_data, error_message)
    """
    try:
        # Try direct parsing first
        parsed = json.loads(raw_text.strip())
        return True, parsed, None
    except json.JSONDecodeError as e:
        return False, None, f"JSON decode error: {str(e)}"
    except Exception as e:
        return False, None, f"Unexpected error: {str(e)}"


def attempt_repair(raw_text: str) -> Tuple[bool, str, Optional[str]]:
    """
    Attempt to repair common JSON issues.
    
    Args:
        raw_text: Raw text that failed strict parsing
        
    Returns:
        Tuple of (success, repaired_text, error_message)
    """
    try:
        text = raw_text.strip()
        
        # Try to extract JSON array first (for compliance matrix)
        array_match = re.search(r'\[[\s\S]*\]', text)
        if array_match:
            text = array_match.group(0)
        else:
            # Try to extract JSON object if no array found
            object_match = re.search(r'\{[\s\S]*\}', text)
            if object_match:
                text = object_match.group(0)
        
        # Apply repairs in order
        # 1. Fix trailing commas in arrays and objects
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        
        # 2. Fix single quotes to double quotes
        text = re.sub(r"'([^']*)'", r'"\1"', text)
        
        # 3. Fix missing quotes around object keys
        text = re.sub(r'(\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*):', r'\1"\2"\3:', text)
        
        # 4. Fix missing closing brackets/braces
        if text.endswith(','):
            text = text[:-1]
        
        # Debug logging
        LOG.debug(f"Repair attempt: original='{raw_text}', repaired='{text}'")
        
        # Validate the repaired JSON
        json.loads(text)
        return True, text, None
        
    except Exception as e:
        return False, raw_text, f"Repair failed: {str(e)}"


def parse_with_repair(raw_text: str) -> Tuple[bool, Any, Optional[str], Dict[str, Any]]:
    """
    Parse JSON with repair attempts and detailed diagnostics.
    
    Args:
        raw_text: Raw text from AI response
        
    Returns:
        Tuple of (success, parsed_data, error_message, diagnostics)
    """
    diagnostics = {
        "original_length": len(raw_text),
        "repair_attempted": False,
        "repair_successful": False,
        "sample_text": raw_text[:200] + "..." if len(raw_text) > 200 else raw_text
    }
    
    # Step 1: Try strict parsing
    success, parsed, error = parse_strict(raw_text)
    if success:
        return True, parsed, None, diagnostics
    
    # Step 2: Attempt repair
    diagnostics["repair_attempted"] = True
    repair_success, repaired_text, repair_error = attempt_repair(raw_text)
    diagnostics["repair_successful"] = repair_success
    
    if repair_success:
        # Try parsing the repaired text
        success, parsed, error = parse_strict(repaired_text)
        if success:
            diagnostics["repaired_text"] = repaired_text[:200] + "..." if len(repaired_text) > 200 else repaired_text
            return True, parsed, None, diagnostics
    
    # Step 3: Return detailed error information
    error_details = {
        "strict_error": error,
        "repair_error": repair_error if not repair_success else None,
        "sample_original": raw_text[:500] + "..." if len(raw_text) > 500 else raw_text,
        "sample_repaired": repaired_text[:500] + "..." if len(repaired_text) > 500 else repaired_text if repair_success else None
    }
    
    return False, None, "JSON parsing failed after repair attempts", diagnostics


def validate_compliance_matrix(data: Any) -> Tuple[bool, List[str]]:
    """
    Validate compliance matrix data structure.
    
    Args:
        data: Parsed JSON data
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    if not isinstance(data, list):
        errors.append("Data must be an array")
        return False, errors
    
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(f"Item {i} must be an object")
            continue
        
        # Check required fields
        required_fields = ["requirement_id", "requirement_text", "rfp_reference", "requirement_type", "suggested_proposal_section"]
        for field in required_fields:
            if field not in item:
                errors.append(f"Item {i} missing required field: {field}")
        
        # Check requirement_type enum
        if "requirement_type" in item:
            valid_types = ["shall", "must", "should", "will", "deliverable", "format", "submission"]
            if item["requirement_type"] not in valid_types:
                errors.append(f"Item {i} invalid requirement_type: {item['requirement_type']}")
    
    return len(errors) == 0, errors


def safe_json_parse(raw_text: str, schema_name: str = "unknown") -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Safe JSON parsing with comprehensive error handling.
    
    This is the main entry point for parsing AI responses.
    
    Args:
        raw_text: Raw text from AI response
        schema_name: Name of the schema for error reporting
        
    Returns:
        Parsed data or raises ValueError with detailed diagnostics
        
    Raises:
        ValueError: If parsing fails, with detailed error information
    """
    success, parsed, error, diagnostics = parse_with_repair(raw_text)
    
    if not success:
        # Create a detailed error message for developers
        error_msg = f"JSON parsing failed for {schema_name}: {error}"
        if diagnostics.get("repair_attempted"):
            error_msg += f" (repair attempted: {diagnostics['repair_successful']})"
        
        # Include sample text for debugging
        sample = diagnostics.get("sample_text", "No sample available")
        error_msg += f"\nSample: {sample}"
        
        raise ValueError(error_msg)
    
    # Additional validation for compliance matrix
    if schema_name == "compliance_matrix":
        is_valid, validation_errors = validate_compliance_matrix(parsed)
        if not is_valid:
            error_msg = f"Compliance matrix validation failed: {', '.join(validation_errors)}"
            raise ValueError(error_msg)
    
    return parsed
