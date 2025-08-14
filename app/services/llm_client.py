# app/services/llm_client.py
from __future__ import annotations
import os, re, logging
from typing import List, Dict, Any
from openai import OpenAI, APIError, APIConnectionError, RateLimitError, BadRequestError, AuthenticationError

LOG = logging.getLogger(__name__)

def _mask(s: str) -> str:
    if not s: return ""
    return s[:3] + "..." + s[-4:]

def _get_client() -> OpenAI:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        LOG.error("OPENAI_API_KEY missing")
        raise AuthenticationError(message="missing OPENAI_API_KEY", response=None, body=None)
    timeout = float(os.getenv("MDRAFT_TIMEOUT_SEC") or "60")
    # brief init log once
    LOG.info("llm_client init: model=%s key=%s timeout=%ss",
             os.getenv("MDRAFT_MODEL") or "gpt-4o-mini", _mask(api_key), timeout)
    return OpenAI(api_key=api_key, timeout=timeout, max_retries=2)

def chat_json(messages: List[Dict[str, str]], response_json_hint: bool = True, model: str | None = None) -> str:
    client = _get_client()
    mdl = (model or os.getenv("MDRAFT_MODEL") or "gpt-4o-mini").strip()
    params: Dict[str, Any] = {
        "model": mdl,
        "messages": messages,
        "temperature": 0.2,
    }
    if response_json_hint:
        # Only supported on modern JSON-capable models like gpt-4o/4o-mini
        params["response_format"] = {"type": "json_object"}
    try:
        resp = client.chat.completions.create(**params)
        content = resp.choices[0].message.content or ""
        return content
    except AuthenticationError as e:
        LOG.exception("openai auth error: %s", e)
        raise RuntimeError("openai_auth")
    except RateLimitError as e:
        LOG.warning("openai rate limit: %s", e)
        raise RuntimeError("openai_rate_limit")
    except BadRequestError as e:
        # e.g., invalid model, unsupported response_format, too long input
        LOG.exception("openai bad request (model=%s): %s", mdl, e)
        raise RuntimeError("openai_bad_request")
    except APIConnectionError as e:
        LOG.exception("openai connection error: %s", e)
        raise RuntimeError("openai_connection")
    except APIError as e:
        LOG.exception("openai api error: %s", e)
        raise RuntimeError("openai_api")
    except Exception as e:
        LOG.exception("openai other error: %s", e)
        raise RuntimeError("openai_other")
