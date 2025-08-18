"""
Centralized serialization utilities for consistent JSON handling.
This module provides utilities to ensure all enums and complex objects
are properly serialized for JSON responses.
"""

from typing import Any, Dict, List, Union
from enum import Enum


def serialize_enum(obj: Any) -> Any:
    """
    Convert enum objects to their string values for JSON serialization.
    
    Args:
        obj: Any object, potentially an enum
        
    Returns:
        The string value if obj is an enum, otherwise the original object
    """
    if isinstance(obj, Enum):
        return obj.value
    return obj


def serialize_conversion_status(status: Any) -> str:
    """
    Specifically handle ConversionStatus enum serialization.
    
    Args:
        status: ConversionStatus enum or string
        
    Returns:
        String representation of the status
    """
    if hasattr(status, 'value'):
        return status.value
    return str(status)


def serialize_conversion_for_json(conversion: Any) -> Dict[str, Any]:
    """
    Serialize a conversion object for JSON response.
    
    Args:
        conversion: Conversion model instance
        
    Returns:
        Dictionary ready for JSON serialization
    """
    if not conversion:
        return {}
    
    # Handle status serialization
    status_value = serialize_conversion_status(conversion.status)
    
    # Build the response dictionary
    result = {
        "id": conversion.id,
        "conversion_id": conversion.id,
        "filename": conversion.filename,
        "status": status_value,  # Use serialized status
        "created_at": conversion.created_at.isoformat() if conversion.created_at else None,
    }
    
    # Add optional fields if they exist
    if hasattr(conversion, 'progress') and conversion.progress is not None:
        result["progress"] = conversion.progress
    
    if hasattr(conversion, 'error') and conversion.error:
        result["error"] = conversion.error
    
    if hasattr(conversion, 'markdown') and conversion.markdown:
        result["markdown"] = conversion.markdown
    
    # Add links
    result["links"] = {
        "self": f"/api/conversions/{conversion.id}",
        "markdown": f"/api/conversions/{conversion.id}/markdown",
        "view": f"/v/{conversion.id}",
    }
    
    return result


def serialize_conversion_list(conversions: List[Any]) -> List[Dict[str, Any]]:
    """
    Serialize a list of conversion objects for JSON response.
    
    Args:
        conversions: List of Conversion model instances
        
    Returns:
        List of dictionaries ready for JSON serialization
    """
    return [serialize_conversion_for_json(conv) for conv in conversions]


def safe_json_serialize(obj: Any) -> Any:
    """
    Safely serialize any object for JSON, handling enums and other special types.
    
    Args:
        obj: Any object to serialize
        
    Returns:
        JSON-serializable version of the object
    """
    if isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, dict):
        return {k: safe_json_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [safe_json_serialize(item) for item in obj]
    elif hasattr(obj, 'isoformat'):  # datetime objects
        return obj.isoformat()
    else:
        return obj
