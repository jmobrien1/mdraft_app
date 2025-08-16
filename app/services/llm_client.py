# app/services/llm_client.py
from __future__ import annotations
import os, logging
from typing import List, Dict, Any
from openai import OpenAI
from app.services.prompt_sanitization import sanitize_for_prompt
# Exception classes vary by SDK version; import broadly and fall back to Exception.
try:
    from openai import (
        APIError, APIConnectionError, RateLimitError, BadRequestError,
        AuthenticationError, PermissionDeniedError, NotFoundError, UnprocessableEntityError
    )
except Exception:  # pragma: no cover
    APIError = APIConnectionError = RateLimitError = BadRequestError = Exception
    AuthenticationError = PermissionDeniedError = NotFoundError = UnprocessableEntityError = Exception

from .reliability import (
    create_retry_decorator, with_timeout, resilient_call,
    ReliabilityError, ExternalServiceError
)
from ..config import get_config

LOG = logging.getLogger(__name__)

def _mask(s: str) -> str:
    return (s[:3] + "..." + s[-4:]) if s and len(s) > 10 else "set"

def _get_request_id() -> str:
    """Get current request ID from context or generate new one."""
    try:
        from app.utils.logging import get_correlation_ids
        correlation_ids = get_correlation_ids()
        return correlation_ids.get("request_id") or "unknown"
    except ImportError:
        # Fallback to Flask request context
        try:
            from flask import request
            return request.environ.get('X-Request-ID', 'unknown')
        except RuntimeError:
            return "unknown"

def _get_client() -> OpenAI:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise AuthenticationError(message="missing OPENAI_API_KEY", response=None, body=None)  # type: ignore
    
    config = get_config().reliability
    timeout = config.HTTP_TIMEOUT_SEC
    
    # Get request ID for logging and headers
    request_id = _get_request_id()
    
    LOG.info("llm_client: model=%s key=%s timeout=%ss request_id=%s",
             os.getenv("MDRAFT_MODEL") or "gpt-4o-mini", _mask(api_key), timeout, request_id)
    
    # Create client with default headers including X-Request-ID
    default_headers = {
        "X-Request-ID": request_id,
        "User-Agent": "mdraft-llm-client/1.0"
    }
    
    return OpenAI(
        api_key=api_key, 
        timeout=timeout, 
        max_retries=0,  # We handle retries with our reliability layer
        default_headers=default_headers
    )

def _create_chat_completion(client: OpenAI, params: Dict[str, Any], response_json_hint: bool = True) -> str:
    """Create chat completion with reliability features."""
    def _call_openai():
        if response_json_hint:
            try:
                params_rf = dict(params, response_format={"type": "json_object"})
                resp = client.chat.completions.create(**params_rf)
            except TypeError as e:
                LOG.warning("response_format unsupported; retrying without it: %s", e)
                resp = client.chat.completions.create(**params)
        else:
            resp = client.chat.completions.create(**params)
        
        return resp.choices[0].message.content or ""
    
    # Use resilient_call for automatic retries, timeouts, and circuit breaker
    return resilient_call(
        service_name="openai",
        endpoint="chat.completions",
        func=_call_openai
    )

def chat_json(messages, response_json_hint=True, model=None, max_tokens=700):
    client = _get_client()
    mdl = (model or os.getenv("MDRAFT_MODEL") or "gpt-4o-mini").strip()
    
    # Sanitize all message content before sending to the model
    sanitized_messages = []
    for message in messages:
        if isinstance(message, dict) and "content" in message:
            # Sanitize the content
            sanitization_result = sanitize_for_prompt(
                message["content"], 
                context=f"message_{message.get('role', 'unknown')}"
            )
            if sanitization_result.warnings:
                LOG.warning("Message sanitization warnings: %s", "; ".join(sanitization_result.warnings))
            
            # Create sanitized message
            sanitized_message = dict(message)
            sanitized_message["content"] = sanitization_result.sanitized_text
            sanitized_messages.append(sanitized_message)
        else:
            # Keep non-dict messages or messages without content as-is
            sanitized_messages.append(message)
    
    params = dict(model=mdl, messages=sanitized_messages, temperature=0.2, max_tokens=max_tokens)
    
    # Get request ID for logging
    request_id = _get_request_id()
    
    try:
        result = _create_chat_completion(client, params, response_json_hint)
        LOG.info("openai_success: request_id=%s model=%s", request_id, mdl)
        return result
        
    except ReliabilityError as e:
        # Log the standardized error
        LOG.error("openai_reliability_error: %s request_id=%s", e, request_id)
        raise RuntimeError(f"openai|{e.error_type.value}")
        
    except Exception as e:
        # Fallback for unexpected errors
        LOG.exception("openai_unexpected: %s request_id=%s", e, request_id)
        msg = (str(e) or "unknown").replace("\n"," ")[:200]
        raise RuntimeError(f"openai_other|{msg}")
