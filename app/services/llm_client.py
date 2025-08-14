# app/services/llm_client.py
from __future__ import annotations
import os, logging
from typing import List, Dict, Any
from openai import OpenAI
# Exception classes vary by SDK version; import broadly and fall back to Exception.
try:
    from openai import (
        APIError, APIConnectionError, RateLimitError, BadRequestError,
        AuthenticationError, PermissionDeniedError, NotFoundError, UnprocessableEntityError
    )
except Exception:  # pragma: no cover
    APIError = APIConnectionError = RateLimitError = BadRequestError = Exception
    AuthenticationError = PermissionDeniedError = NotFoundError = UnprocessableEntityError = Exception

LOG = logging.getLogger(__name__)

def _mask(s: str) -> str:
    return (s[:3] + "..." + s[-4:]) if s and len(s) > 10 else "set"

def _get_client() -> OpenAI:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise AuthenticationError(message="missing OPENAI_API_KEY", response=None, body=None)  # type: ignore
    timeout = float(os.getenv("MDRAFT_TIMEOUT_SEC") or "60")
    LOG.info("llm_client: model=%s key=%s timeout=%ss",
             os.getenv("MDRAFT_MODEL") or "gpt-4o-mini", _mask(api_key), timeout)
    return OpenAI(api_key=api_key, timeout=timeout, max_retries=2)

def _raise(code: str, err: BaseException):
    # bubble a compact, safe message to callers
    msg = str(err)
    msg = (msg or "").replace("\n", " ")[:200]
    raise RuntimeError(f"{code}|{msg}")

def chat_json(messages: List[Dict[str, str]], response_json_hint: bool = True, model: str | None = None) -> str:
    client = _get_client()
    mdl = (model or os.getenv("MDRAFT_MODEL") or "gpt-4o-mini").strip()
    params: Dict[str, Any] = {
        "model": mdl,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 2000,
    }
    if response_json_hint:
        params["response_format"] = {"type": "json_object"}

    try:
        resp = client.chat.completions.create(**params)
        return resp.choices[0].message.content or ""
    except AuthenticationError as e:
        LOG.exception("openai_auth: %s", e); _raise("openai_auth", e)
    except PermissionDeniedError as e:
        LOG.exception("openai_permission: %s", e); _raise("openai_permission", e)
    except RateLimitError as e:
        LOG.warning("openai_rate_limit: %s", e); _raise("openai_rate_limit", e)
    except BadRequestError as e:
        LOG.exception("openai_bad_request: %s", e); _raise("openai_bad_request", e)
    except UnprocessableEntityError as e:
        LOG.exception("openai_unprocessable: %s", e); _raise("openai_unprocessable", e)
    except NotFoundError as e:
        LOG.exception("openai_not_found: %s", e); _raise("openai_not_found", e)
    except APIConnectionError as e:
        LOG.exception("openai_connection: %s", e); _raise("openai_connection", e)
    except APIError as e:
        LOG.exception("openai_api: %s", e); _raise("openai_api", e)
    except Exception as e:
        LOG.exception("openai_other: %s", e); _raise("openai_other", e)
