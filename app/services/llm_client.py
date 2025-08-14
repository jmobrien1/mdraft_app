"""
LLM client module for AI model integration.

This module provides a unified interface for calling AI models from different providers.
Currently supports OpenAI and Google Cloud Vertex AI.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

LOG = logging.getLogger(__name__)


def chat_json(messages: List[Dict[str, str]], response_json_hint: bool = True) -> str:
    """
    Send messages to an AI model and return the response.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        response_json_hint: Whether to hint that JSON response is expected
        
    Returns:
        The model's response text
        
    Raises:
        Exception: If no AI service is configured or call fails
    """
    # Check for OpenAI API key first
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        return _call_openai(messages, response_json_hint)
    
    # Check for Google Cloud Vertex AI
    google_cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if google_cloud_project:
        try:
            return _call_vertex_ai(messages, response_json_hint)
        except Exception as e:
            LOG.warning(f"Vertex AI call failed: {e}")
    
    # No AI service configured
    raise Exception("No AI service configured. Set OPENAI_API_KEY or GOOGLE_CLOUD_PROJECT")


def _call_openai(messages: List[Dict[str, str]], response_json_hint: bool) -> str:
    """
    Call OpenAI API with the given messages.
    
    Args:
        messages: List of message dictionaries
        response_json_hint: Whether to hint that JSON response is expected
        
    Returns:
        Model response text
    """
    try:
        import openai
        
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Add JSON hint to system message if needed
        if response_json_hint and messages and messages[0].get("role") == "system":
            messages[0]["content"] += "\n\nIMPORTANT: Respond with valid JSON only."
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use cost-effective model
            messages=messages,
            temperature=0.1,  # Low temperature for consistent structured output
            max_tokens=4000
        )
        
        return response.choices[0].message.content
        
    except ImportError:
        LOG.error("OpenAI client not available")
        raise Exception("OpenAI client not installed. Run: pip install openai")
    except Exception as e:
        LOG.error(f"OpenAI API call failed: {e}")
        raise


def _call_vertex_ai(messages: List[Dict[str, str]], response_json_hint: bool) -> str:
    """
    Call Google Cloud Vertex AI with the given messages.
    
    Args:
        messages: List of message dictionaries
        response_json_hint: Whether to hint that JSON response is expected
        
    Returns:
        Model response text
    """
    try:
        import google.generativeai as genai
        
        # Configure the API key
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise Exception("GOOGLE_API_KEY environment variable not set")
        
        genai.configure(api_key=api_key)
        
        # Use Gemini Pro model
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Combine messages for Gemini (it doesn't support separate system/user messages)
        combined_content = ""
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                combined_content += f"SYSTEM: {content}\n\n"
            elif role == "user":
                combined_content += f"USER: {content}\n\n"
            else:
                combined_content += f"{content}\n\n"
        
        # Add JSON hint if needed
        if response_json_hint:
            combined_content += "IMPORTANT: Respond with valid JSON only.\n\n"
        
        response = model.generate_content(combined_content.strip())
        
        return response.text
        
    except ImportError:
        LOG.error("Google Generative AI client not available")
        raise Exception("Google Generative AI client not installed. Run: pip install google-generativeai")
    except Exception as e:
        LOG.error(f"Vertex AI API call failed: {e}")
        raise
