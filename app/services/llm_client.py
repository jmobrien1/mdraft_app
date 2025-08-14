# app/services/llm_client.py
from __future__ import annotations
import os
import logging
from typing import List, Dict, Any
from openai import OpenAI
from openai import AuthenticationError, RateLimitError, APITimeoutError, APIError

LOG = logging.getLogger(__name__)

def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    timeout = float(os.getenv("MDRAFT_TIMEOUT_SEC") or "60")
    return OpenAI(api_key=api_key, timeout=timeout)

def chat_json(messages: List[Dict[str, str]], response_json_hint: bool = True, model: str | None = None) -> str:
    """
    Send a chat request to OpenAI and return the response.
    
    Args:
        messages: List of message dictionaries
        response_json_hint: Whether to force JSON response format
        model: Model to use (defaults to MDRAFT_MODEL env var)
        
    Returns:
        Response content as string
        
    Raises:
        RuntimeError: With specific error codes for different failure types
    """
    client = _get_client()
    mdl = model or os.getenv("MDRAFT_MODEL") or "gpt-4o-mini"
    
    params: Dict[str, Any] = {
        "model": mdl,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 2000,
    }
    
    if response_json_hint:
        params["response_format"] = {"type": "json_object"}  # force JSON
    
    try:
        LOG.info("chat_json: calling OpenAI model=%s", mdl)
        resp = client.chat.completions.create(**params)
        content = resp.choices[0].message.content or ""
        LOG.info("chat_json: success model=%s len=%d", mdl, len(content))
        return content
        
    except AuthenticationError as e:
        LOG.error("chat_json: authentication failed model=%s: %s", mdl, e)
        raise RuntimeError("openai_auth")
        
    except RateLimitError as e:
        LOG.error("chat_json: rate limit exceeded model=%s: %s", mdl, e)
        raise RuntimeError("openai_rate_limit")
        
    except APITimeoutError as e:
        LOG.error("chat_json: timeout model=%s: %s", mdl, e)
        raise RuntimeError("openai_timeout")
        
    except APIError as e:
        LOG.error("chat_json: API error model=%s: %s", mdl, e)
        raise RuntimeError("openai_other")
        
    except Exception as e:
        LOG.error("chat_json: unexpected error model=%s: %s", mdl, e)
        raise RuntimeError("openai_other")
