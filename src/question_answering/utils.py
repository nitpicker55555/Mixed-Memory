"""
Utility Functions for Agentic Search Engine

This module provides common utility functions for date parsing,
text processing, and list operations.
"""

import re
from datetime import datetime
from typing import Any, List, Optional


# Regular expression for ordinal numbers
_ORDINAL_RE = re.compile(r'(\d+)(st|nd|rd|th)$', re.IGNORECASE)


def strip_ordinal(day_str: str) -> str:
    """
    Remove ordinal suffix from day number.
    
    Args:
        day_str: Day string with possible ordinal suffix (e.g., '23rd')
        
    Returns:
        Day string without suffix (e.g., '23')
        
    Example:
        >>> strip_ordinal('23rd')
        '23'
    """
    match = _ORDINAL_RE.match(day_str.strip())
    return match.group(1) if match else day_str.strip()


def parse_date_safe(date_string: str) -> Optional[datetime]:
    """
    Parse date string to datetime object with multiple format support.
    
    Supports formats like:
    - 'March 23, 2024'
    - 'Mar 23, 2024'
    - 'March 23rd, 2024'
    
    Args:
        date_string: Date string to parse
        
    Returns:
        Parsed datetime object or None if parsing fails
    """
    if not date_string:
        return None
    
    # Normalize string: remove commas and extra spaces
    text = date_string.strip().replace(",", " ")
    parts = [p for p in text.split() if p]
    
    if len(parts) >= 3:
        # Remove ordinal suffix from day
        parts[1] = strip_ordinal(parts[1])
        text = " ".join(parts[:3])
    
    # Try multiple date formats
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    
    return None


def unique_in_order(sequence: List[Any]) -> List[Any]:
    """
    Remove duplicates from list while preserving order.
    
    Args:
        sequence: Input list with possible duplicates
        
    Returns:
        List with duplicates removed, original order preserved
        
    Example:
        >>> unique_in_order([1, 2, 2, 3, 1, 4])
        [1, 2, 3, 4]
    """
    seen = set()
    result = []
    for item in sequence:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def clean_json_response(text: str) -> str:
    """
    Clean LLM JSON response by removing markdown and formatting issues.
    
    Args:
        text: Raw LLM response text
        
    Returns:
        Cleaned JSON string
    """
    # Remove markdown code block markers
    if text.startswith('```json'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    # Ensure starts with { and ends with }
    if not text.startswith('{'):
        start_idx = text.find('{')
        if start_idx != -1:
            text = text[start_idx:]
    
    if not text.endswith('}'):
        end_idx = text.rfind('}')
        if end_idx != -1:
            text = text[:end_idx + 1]
    
    # Remove explanatory text, keep only JSON
    lines = text.split('\n')
    json_lines = []
    in_json = False
    
    for line in lines:
        line = line.strip()
        if line.startswith('{') or in_json:
            in_json = True
            json_lines.append(line)
            if line.endswith('}') and line.count('{') <= line.count('}'):
                break
    
    if json_lines:
        cleaned = '\n'.join(json_lines)
        if cleaned.startswith('{') and cleaned.endswith('}'):
            return cleaned
    
    # If cleaning failed, return original text
    return text


def to_list(answer: Any) -> List[str]:
    """
    Convert answer to standardized list format.
    
    Args:
        answer: Answer in any format (None, string, or list)
        
    Returns:
        Standardized list of strings
        
    Example:
        >>> to_list(None)
        []
        >>> to_list("answer")
        ['answer']
        >>> to_list([1, 2, 3])
        ['1', '2', '3']
    """
    if answer is None:
        return []
    if isinstance(answer, list):
        return [str(x).strip() for x in answer if str(x).strip()]
    return [str(answer).strip()]

