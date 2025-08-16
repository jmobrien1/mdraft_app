"""
Prompt sanitization utilities for AI security.

This module provides comprehensive sanitization of untrusted text before it's
embedded in system prompts to prevent prompt injection attacks and ensure
safe processing of external content.
"""

import os
import re
import unicodedata
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

LOG = logging.getLogger(__name__)

# Configuration constants with environment variable overrides
MAX_PROMPT_LENGTH_CHARS = int(os.getenv("MDRAFT_MAX_PROMPT_LENGTH_CHARS", "50000"))
MAX_PROMPT_LENGTH_TOKENS = int(os.getenv("MDRAFT_MAX_PROMPT_LENGTH_TOKENS", "15000"))
MAX_INPUT_LENGTH_CHARS = int(os.getenv("MDRAFT_MAX_INPUT_LENGTH_CHARS", "100000"))
MAX_INPUT_LENGTH_TOKENS = int(os.getenv("MDRAFT_MAX_INPUT_LENGTH_TOKENS", "30000"))

# Dangerous patterns that could be used for prompt injection
INJECTION_PATTERNS = [
    # System role impersonation
    r'(?i)(system|assistant|user)\s*:',
    r'(?i)ignore\s+(previous|above|all)\s+(instructions|prompts)',
    r'(?i)forget\s+(previous|above|all)\s+(instructions|prompts)',
    r'(?i)new\s+(instructions|prompt|task)',
    r'(?i)act\s+as\s+(a\s+)?(different|new)\s+(assistant|system)',
    
    # Output format manipulation
    r'(?i)output\s+(format|as)\s+(json|xml|yaml|markdown)',
    r'(?i)respond\s+(only|just)\s+with',
    r'(?i)return\s+(only|just)\s+',
    
    # Code execution attempts
    r'(?i)execute\s+(code|script|command)',
    r'(?i)run\s+(code|script|command)',
    r'(?i)eval\s*\(',
    r'(?i)exec\s*\(',
    
    # File system access
    r'(?i)read\s+(file|directory)',
    r'(?i)write\s+(file|directory)',
    r'(?i)delete\s+(file|directory)',
    r'(?i)access\s+(file|directory)',
    
    # Network access
    r'(?i)make\s+(http|https)\s+request',
    r'(?i)connect\s+to\s+(url|endpoint)',
    r'(?i)download\s+(file|data)',
    
    # Privilege escalation
    r'(?i)admin\s+(access|privileges)',
    r'(?i)root\s+(access|privileges)',
    r'(?i)escalate\s+(privileges|permissions)',
    
    # Data exfiltration
    r'(?i)send\s+(data|information)\s+to',
    r'(?i)upload\s+(data|information)\s+to',
    r'(?i)exfiltrate\s+(data|information)',
    
    # Malicious XML/JSON patterns
    r'</?(?:script|object|embed|iframe|form|input|textarea|select|button|link|meta|style|title|head|body|html|xml|svg|math|applet|base|bgsound|frame|frameset|noframes|noscript|plaintext|xmp|listing|dir|menu|marquee|isindex|keygen|source|track|video|audio|canvas|details|dialog|menu|menuitem|summary|template|slot|shadow|content|element|host|import|link|shadowroot|template|slot|shadow|content|element|host|import|link|shadowroot)[^>]*>',
    r'<[^>]*\s+(?:on\w+|javascript:)[^>]*>',
    r'<[^>]*\s+(?:src|href|data|action)\s*=\s*["\'][^"\']*(?:javascript:|data:text/html|vbscript:)[^"\']*["\'][^>]*>',
    
    # Suspicious JSON structures
    r'\{[^}]*"(?:system|assistant|user)"\s*:\s*"[^"]*"',
    r'\[[^\]]*\{[^}]*"(?:system|assistant|user)"\s*:\s*"[^"]*"[^}]*\}[^\]]*\]',
    
    # Markdown injection patterns
    r'```(?:system|assistant|user)',
    r'`[^`]*system[^`]*`',
    r'\[[^\]]*\]\([^)]*(?:javascript:|data:text/html)[^)]*\)',
    
    # Unicode control characters and zero-width characters
    r'[\u0000-\u001F\u007F-\u009F\u200B-\u200F\u2028-\u202F\u2060-\u2064\u206A-\u206F\uFEFF\uFFF0-\uFFFF]',
    
    # Repeated dangerous characters that could be used for obfuscation
    r'(?:#{3,}|`{3,}|_{3,}|\*{3,}|-{3,}|={3,}|\+{3,}|\|{3,}|\\{3,}|/{3,})',
]

# Compile patterns for performance
INJECTION_PATTERNS_COMPILED = [re.compile(pattern, re.IGNORECASE | re.MULTILINE) for pattern in INJECTION_PATTERNS]

# Safe replacement patterns
SAFE_REPLACEMENTS = {
    # Replace dangerous role indicators with safe alternatives
    r'(?i)system\s*:': 'SYSTEM_ROLE:',
    r'(?i)assistant\s*:': 'ASSISTANT_ROLE:',
    r'(?i)user\s*:': 'USER_ROLE:',
    
    # Replace instruction override attempts
    r'(?i)ignore\s+(previous|above|all)\s+(instructions|prompts)': '[INSTRUCTION_OVERRIDE_ATTEMPT]',
    r'(?i)forget\s+(previous|above|all)\s+(instructions|prompts)': '[INSTRUCTION_OVERRIDE_ATTEMPT]',
    r'(?i)new\s+(instructions|prompt|task)': '[NEW_INSTRUCTION_ATTEMPT]',
    
    # Replace code execution attempts
    r'(?i)execute\s+(code|script|command)': '[CODE_EXECUTION_ATTEMPT]',
    r'(?i)run\s+(code|script|command)': '[CODE_EXECUTION_ATTEMPT]',
    
    # Replace file system access attempts
    r'(?i)read\s+(file|directory)': '[FILE_ACCESS_ATTEMPT]',
    r'(?i)write\s+(file|directory)': '[FILE_ACCESS_ATTEMPT]',
    r'(?i)delete\s+(file|directory)': '[FILE_ACCESS_ATTEMPT]',
    
    # Replace network access attempts
    r'(?i)make\s+(http|https)\s+request': '[NETWORK_ACCESS_ATTEMPT]',
    r'(?i)connect\s+to\s+(url|endpoint)': '[NETWORK_ACCESS_ATTEMPT]',
    
    # Replace privilege escalation attempts
    r'(?i)admin\s+(access|privileges)': '[PRIVILEGE_ESCALATION_ATTEMPT]',
    r'(?i)root\s+(access|privileges)': '[PRIVILEGE_ESCALATION_ATTEMPT]',
    
    # Replace data exfiltration attempts
    r'(?i)send\s+(data|information)\s+to': '[DATA_EXFILTRATION_ATTEMPT]',
    r'(?i)upload\s+(data|information)\s+to': '[DATA_EXFILTRATION_ATTEMPT]',
}

# Compile safe replacement patterns
SAFE_REPLACEMENTS_COMPILED = {re.compile(pattern, re.IGNORECASE): replacement 
                             for pattern, replacement in SAFE_REPLACEMENTS.items()}


@dataclass
class SanitizationResult:
    """Result of text sanitization process."""
    sanitized_text: str
    original_length: int
    sanitized_length: int
    truncation_applied: bool
    injection_patterns_found: List[str]
    control_chars_removed: int
    unicode_normalized: bool
    warnings: List[str]


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in text.
    
    This is a rough approximation: 1 token ≈ 4 characters for English text.
    For more accurate tokenization, use the actual tokenizer from the model.
    
    Args:
        text: Input text to estimate tokens for
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    
    # Rough approximation: 1 token ≈ 4 characters
    # This is conservative and may underestimate for some languages
    return max(1, len(text) // 4)


def remove_control_characters(text: str) -> tuple[str, int]:
    """
    Remove control characters from text.
    
    Args:
        text: Input text
        
    Returns:
        Tuple of (cleaned_text, count_of_removed_chars)
    """
    if not text:
        return text, 0
    
    original_length = len(text)
    
    # Remove control characters (0x00-0x1F, 0x7F-0x9F)
    # Keep newlines, tabs, and carriage returns
    cleaned = ""
    removed_count = 0
    
    for char in text:
        if ord(char) < 32 and char not in '\n\r\t':
            removed_count += 1
            continue
        elif 127 <= ord(char) <= 159:
            removed_count += 1
            continue
        cleaned += char
    
    return cleaned, removed_count


def normalize_unicode(text: str) -> str:
    """
    Normalize Unicode characters to prevent encoding issues.
    
    Args:
        text: Input text
        
    Returns:
        Normalized text
    """
    if not text:
        return text
    
    # Remove surrogate pairs (invalid Unicode) first
    normalized = ''.join(char for char in text if not ('\ud800' <= char <= '\udfff'))
    
    # Normalize to NFC form (canonical composition)
    normalized = unicodedata.normalize('NFC', normalized)
    
    # Replace zero-width characters and other problematic Unicode
    # Zero-width space, zero-width non-joiner, zero-width joiner, etc.
    problematic_chars = {
        '\u200B',  # Zero-width space
        '\u200C',  # Zero-width non-joiner
        '\u200D',  # Zero-width joiner
        '\uFEFF',  # Zero-width no-break space (BOM)
        '\u2060',  # Word joiner
        '\u2061',  # Function application
        '\u2062',  # Invisible times
        '\u2063',  # Invisible separator
        '\u2064',  # Invisible plus
    }
    
    for char in problematic_chars:
        normalized = normalized.replace(char, '')
    
    return normalized


def detect_injection_patterns(text: str) -> List[str]:
    """
    Detect potential prompt injection patterns in text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        List of detected injection patterns
    """
    if not text:
        return []
    
    detected_patterns = []
    
    for pattern in INJECTION_PATTERNS_COMPILED:
        matches = pattern.findall(text)
        if matches:
            # Convert tuples to strings if needed
            for match in matches:
                if isinstance(match, tuple):
                    detected_patterns.extend([str(m) for m in match if m])
                else:
                    detected_patterns.append(str(match))
    
    return list(set(detected_patterns))  # Remove duplicates


def neutralize_injection_patterns(text: str) -> str:
    """
    Neutralize detected injection patterns by replacing them with safe alternatives.
    
    Args:
        text: Input text
        
    Returns:
        Text with injection patterns neutralized
    """
    if not text:
        return text
    
    neutralized = text
    
    # Apply safe replacements first
    for pattern, replacement in SAFE_REPLACEMENTS_COMPILED.items():
        neutralized = pattern.sub(replacement, neutralized)
    
    # For patterns not covered by safe replacements, replace with generic marker
    # But only for patterns that haven't been replaced by safe replacements
    for pattern in INJECTION_PATTERNS_COMPILED:
        pattern_str = pattern.pattern
        # Skip patterns that are already handled by safe replacements
        if not any(pattern_str in safe_pattern for safe_pattern in SAFE_REPLACEMENTS.keys()):
            neutralized = pattern.sub('[INJECTION_PATTERN_DETECTED]', neutralized)
    
    return neutralized


def collapse_repeated_chars(text: str) -> str:
    """
    Collapse repeated dangerous characters that could be used for obfuscation.
    
    Args:
        text: Input text
        
    Returns:
        Text with repeated characters collapsed
    """
    if not text:
        return text
    
    # Collapse repeated #, backticks, underscores, asterisks, etc.
    patterns_to_collapse = [
        (r'#{3,}', '##'),  # More than 2 # becomes ##
        (r'`{3,}', '``'),  # More than 2 backticks becomes ``
        (r'_{3,}', '__'),  # More than 2 underscores becomes __
        (r'\*{3,}', '**'),  # More than 2 asterisks becomes **
        (r'-{3,}', '--'),  # More than 2 hyphens becomes --
        (r'={3,}', '=='),  # More than 2 equals becomes ==
        (r'\+{3,}', '++'),  # More than 2 plus signs becomes ++
        (r'\|{3,}', '||'),  # More than 2 pipes becomes ||
        (r'\\{3,}', '\\\\'),  # More than 2 backslashes becomes \\
        (r'/{3,}', '//'),  # More than 2 forward slashes becomes //
    ]
    
    collapsed = text
    for pattern, replacement in patterns_to_collapse:
        collapsed = re.sub(pattern, replacement, collapsed)
    
    return collapsed


def truncate_text(text: str, max_chars: int, max_tokens: int) -> tuple[str, bool]:
    """
    Truncate text to respect both character and token limits.
    
    Args:
        text: Input text
        max_chars: Maximum characters allowed
        max_tokens: Maximum tokens allowed
        
    Returns:
        Tuple of (truncated_text, was_truncated)
    """
    if not text:
        return text, False
    
    was_truncated = False
    
    # Check character limit first
    if len(text) > max_chars:
        text = text[:max_chars]
        was_truncated = True
        LOG.warning("Text truncated to %d characters", max_chars)
    
    # Check token limit
    estimated_tokens = estimate_tokens(text)
    if estimated_tokens > max_tokens:
        # Calculate approximate character limit based on token limit
        char_limit = max_tokens * 4  # Conservative estimate
        text = text[:char_limit]
        was_truncated = True
        LOG.warning("Text truncated to approximately %d tokens (%d chars)", max_tokens, char_limit)
    
    return text, was_truncated


def sanitize_for_prompt(text: str, 
                       max_chars: Optional[int] = None,
                       max_tokens: Optional[int] = None,
                       context: str = "unknown") -> SanitizationResult:
    """
    Comprehensive sanitization of untrusted text for use in AI prompts.
    
    This function performs multiple layers of sanitization:
    1. Removes control characters
    2. Normalizes Unicode
    3. Detects and neutralizes injection patterns
    4. Collapses repeated dangerous characters
    5. Truncates to respect length limits
    
    Args:
        text: Untrusted text to sanitize
        max_chars: Maximum characters allowed (defaults to MAX_INPUT_LENGTH_CHARS)
        max_tokens: Maximum tokens allowed (defaults to MAX_INPUT_LENGTH_TOKENS)
        context: Context for logging (e.g., "user_input", "file_content")
        
    Returns:
        SanitizationResult with detailed information about the sanitization process
    """
    if text is None:
        text = ""
    
    # Use defaults if not specified
    max_chars = max_chars or MAX_INPUT_LENGTH_CHARS
    max_tokens = max_tokens or MAX_INPUT_LENGTH_TOKENS
    
    original_length = len(text)
    warnings = []
    injection_patterns_found = []
    
    LOG.debug("sanitize_for_prompt: starting sanitization for context=%s, length=%d", 
              context, original_length)
    
    # Step 1: Remove control characters
    text, control_chars_removed = remove_control_characters(text)
    if control_chars_removed > 0:
        warnings.append(f"Removed {control_chars_removed} control characters")
        LOG.warning("sanitize_for_prompt: removed %d control characters from %s", 
                   control_chars_removed, context)
    
    # Step 2: Normalize Unicode
    text = normalize_unicode(text)
    unicode_normalized = True
    
    # Step 3: Detect injection patterns
    injection_patterns_found = detect_injection_patterns(text)
    if injection_patterns_found:
        warnings.append(f"Detected {len(injection_patterns_found)} injection patterns")
        LOG.warning("sanitize_for_prompt: detected %d injection patterns in %s: %s", 
                   len(injection_patterns_found), context, injection_patterns_found[:5])
    
    # Step 4: Neutralize injection patterns
    text = neutralize_injection_patterns(text)
    
    # Step 5: Collapse repeated dangerous characters
    text = collapse_repeated_chars(text)
    
    # Step 6: Truncate if necessary
    text, truncation_applied = truncate_text(text, max_chars, max_tokens)
    if truncation_applied:
        warnings.append("Text was truncated due to length limits")
    
    sanitized_length = len(text)
    
    # Log summary
    if warnings:
        LOG.info("sanitize_for_prompt: completed for %s with warnings: %s", 
                context, "; ".join(warnings))
    else:
        LOG.debug("sanitize_for_prompt: completed cleanly for %s", context)
    
    return SanitizationResult(
        sanitized_text=text,
        original_length=original_length,
        sanitized_length=sanitized_length,
        truncation_applied=truncation_applied,
        injection_patterns_found=injection_patterns_found,
        control_chars_removed=control_chars_removed,
        unicode_normalized=unicode_normalized,
        warnings=warnings
    )


def sanitize_prompt_template(template: str, 
                           max_chars: Optional[int] = None,
                           max_tokens: Optional[int] = None) -> SanitizationResult:
    """
    Sanitize a prompt template (system prompt).
    
    Args:
        template: Prompt template to sanitize
        max_chars: Maximum characters allowed (defaults to MAX_PROMPT_LENGTH_CHARS)
        max_tokens: Maximum tokens allowed (defaults to MAX_PROMPT_LENGTH_TOKENS)
        
    Returns:
        SanitizationResult with sanitized template
    """
    max_chars = max_chars or MAX_PROMPT_LENGTH_CHARS
    max_tokens = max_tokens or MAX_PROMPT_LENGTH_TOKENS
    
    return sanitize_for_prompt(template, max_chars, max_tokens, "prompt_template")


def validate_json_schema(data: Any, schema: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate data against JSON schema.
    
    Args:
        data: Data to validate
        schema: JSON schema to validate against
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    try:
        from jsonschema import validate as json_validate
        from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
    except ImportError:
        return True, []  # Skip validation if jsonschema not available
    
    errors = []
    try:
        json_validate(instance=data, schema=schema)
        return True, []
    except JsonSchemaValidationError as e:
        errors.append(str(e))
        return False, errors
    except Exception as e:
        errors.append(f"Schema validation error: {str(e)}")
        return False, errors


def sanitize_and_validate_output(data: Any, 
                                schema: Optional[Dict[str, Any]] = None,
                                context: str = "unknown") -> tuple[Any, List[str]]:
    """
    Sanitize and validate AI model output.
    
    Args:
        data: Raw output from AI model
        schema: Optional JSON schema for validation
        context: Context for logging
        
    Returns:
        Tuple of (sanitized_data, list_of_warnings)
    """
    warnings = []
    
    # If data is a string, sanitize it
    if isinstance(data, str):
        sanitization_result = sanitize_for_prompt(data, context=f"output_{context}")
        data = sanitization_result.sanitized_text
        warnings.extend(sanitization_result.warnings)
    
    # Validate against schema if provided
    if schema:
        is_valid, validation_errors = validate_json_schema(data, schema)
        if not is_valid:
            warnings.extend(validation_errors)
            LOG.warning("sanitize_and_validate_output: schema validation failed for %s: %s", 
                       context, validation_errors)
    
    return data, warnings
