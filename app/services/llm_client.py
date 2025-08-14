# app/services/llm_client.py
from __future__ import annotations
import os
from typing import List, Dict, Any
from openai import OpenAI

def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    timeout = float(os.getenv("MDRAFT_TIMEOUT_SEC") or "60")
    return OpenAI(api_key=api_key, timeout=timeout)

def chat_json(messages: List[Dict[str, str]], response_json_hint: bool = True, model: str | None = None) -> str:
    client = _get_client()
    mdl = model or os.getenv("MDRAFT_MODEL") or "gpt-4o-mini"
    params: Dict[str, Any] = {
        "model": mdl,
        "messages": messages,
        "temperature": 0.2,
    }
    if response_json_hint:
        params["response_format"] = {"type": "json_object"}  # force JSON
    resp = client.chat.completions.create(**params)
    content = resp.choices[0].message.content or ""
    return content
