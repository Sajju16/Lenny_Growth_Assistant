import re
import html
import logging
from typing import Tuple, List, Dict, Any

logger = logging.getLogger("lenny-growth-backend.artifacts.sanitizer")

# Patterns for dangerous HTML elements and attributes
SCRIPT_TAG_PATTERN = re.compile(r"<\s*script[^>]*>[\s\S]*?<\s*/\s*script\s*>", re.IGNORECASE)
GENERIC_SCRIPT_PATTERN = re.compile(r"<\s*script[^>]*>", re.IGNORECASE)
EVENT_HANDLER_PATTERN = re.compile(r"\bon[a-zA-Z]+\s*=\s*['\"][^'\"]*['\"]|\bon[a-zA-Z]+\s*=\s*[^>\s]+", re.IGNORECASE)
JAVASCRIPT_URI_PATTERN = re.compile(r"(href|src|action|data)\s*=\s*['\"]\s*javascript:[^'\"]*['\"]", re.IGNORECASE)
VBSCRIPT_URI_PATTERN = re.compile(r"(href|src|action|data)\s*=\s*['\"]\s*vbscript:[^'\"]*['\"]", re.IGNORECASE)
DANGEROUS_TAGS_PATTERN = re.compile(r"<\s*(iframe|object|embed|applet|meta\s+http-equiv)[^>]*>", re.IGNORECASE)


def validate_and_sanitize_html(raw_html: str) -> Tuple[bool, str, List[str]]:
    """
    Validates and sanitizes model-generated HTML content before storage or preview.
    
    Returns:
        (is_safe, sanitized_html, warnings)
        
    Rules:
    - Zero tolerance for executable script elements.
    - Inline event handlers (onload, onerror, onclick, etc.) stripped.
    - Pseudo-protocols (javascript:, vbscript:) neutralized.
    - Dangerous embedded frame/object tags stripped.
    - If active threats are detected, is_safe is marked False so the UI
      can fallback to source code inspection and display security warnings.
    """
    if not raw_html or not raw_html.strip():
        return True, "", []

    warnings: List[str] = []
    sanitized = raw_html

    # 1. Detect and strip <script> tags
    if SCRIPT_TAG_PATTERN.search(sanitized) or GENERIC_SCRIPT_PATTERN.search(sanitized):
        warnings.append("Disallowed <script> executable tag detected and removed.")
        sanitized = SCRIPT_TAG_PATTERN.sub("", sanitized)
        sanitized = GENERIC_SCRIPT_PATTERN.sub("", sanitized)

    # 2. Detect and strip inline event handlers (e.g. onerror=, onload=, onclick=)
    event_matches = EVENT_HANDLER_PATTERN.findall(sanitized)
    if event_matches:
        for handler in event_matches:
            attr_name = handler.split("=")[0].strip()
            warnings.append(f"Disallowed inline event handler '{attr_name}' detected and removed.")
        sanitized = EVENT_HANDLER_PATTERN.sub("", sanitized)

    # 3. Detect and neutralize javascript: and vbscript: URIs
    if JAVASCRIPT_URI_PATTERN.search(sanitized):
        warnings.append("Disallowed 'javascript:' protocol detected in URL attribute and neutralized.")
        sanitized = JAVASCRIPT_URI_PATTERN.sub(r'\1="#"', sanitized)

    if VBSCRIPT_URI_PATTERN.search(sanitized):
        warnings.append("Disallowed 'vbscript:' protocol detected in URL attribute and neutralized.")
        sanitized = VBSCRIPT_URI_PATTERN.sub(r'\1="#"', sanitized)

    # 4. Detect and strip dangerous embedding tags (<iframe, <object, <embed)
    if DANGEROUS_TAGS_PATTERN.search(sanitized):
        warnings.append("Disallowed embedded frame/object tag detected and removed.")
        sanitized = DANGEROUS_TAGS_PATTERN.sub("", sanitized)

    # If any threats were detected, the original input was unsafe
    is_safe = (len(warnings) == 0)

    # Wrap self-contained HTML snippets with minimal, clean styling if missing html/body tags
    cleaned_html = sanitized.strip()
    if not cleaned_html.lower().startswith("<!doctype") and "<html" not in cleaned_html.lower():
        cleaned_html = (
            "<!DOCTYPE html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "  <style>\n"
            "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; "
            "           padding: 24px; color: #1e293b; background: #ffffff; line-height: 1.6; margin: 0; }\n"
            "    * { box-sizing: border-box; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            f"{cleaned_html}\n"
            "</body>\n"
            "</html>"
        )

    return is_safe, cleaned_html, warnings
