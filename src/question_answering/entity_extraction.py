"""
Entity Extraction Module

This module provides functionality for extracting entities (persons, events)
from natural language questions using pattern matching and LLM-based extraction.
"""

import re
import json
from typing import Optional, Tuple, List
from openai import OpenAI


def extract_person_and_event_regex(question: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract person names and event keywords using regex patterns.
    
    This is a fallback method for basic entity extraction.
    
    Args:
        question: Natural language question
        
    Returns:
        Tuple of (person_name, event_keyword) or (None, None)
    """
    person = None
    event = None
    
    # Person name: two or three capitalized words
    match = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", question)
    if match:
        candidate = match.group(1).strip()
        # Exclude common event-related terms
        event_terms = [
            'night', 'day', 'festival', 'exhibition', 'contest', 'competition',
            'workshop', 'conference', 'meeting', 'party', 'celebration', 'show', 'event'
        ]
        if not any(term in candidate.lower() for term in event_terms):
            person = candidate
    
    # Event keyword: text in quotes or after specific patterns
    patterns = [
        r'involving ([A-Z][A-Za-z\s]+?)(?:\.|$)',  # involving X
        r'"([^"]+)"',  # in quotes
        r'"([^"]+)"',  # in smart quotes
        r'related to ([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)',
        r'involving both .* and ([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, question, flags=re.IGNORECASE)
        if match:
            event = match.group(1).strip()
            break
    
    return person, event


def extract_entities_llm(client: OpenAI, question: str, state=None) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract entities using LLM for more accurate identification.
    
    Args:
        client: OpenAI client instance
        question: Natural language question
        state: Optional search state for token tracking
        
    Returns:
        Tuple of (person_name, event_keyword) or (None, None)
    """
    prompt = f"""
Analyze this question and extract person names and event keywords. Be very careful to distinguish between people and events.

Question: {question}

Return ONLY a JSON object:
{{
  "person": "<actual person name if mentioned, else null>",
  "event": "<event name/type if mentioned, else null>"
}}

Rules:
- A PERSON is a human being's name (e.g., "John Smith", "Mary Johnson")
- An EVENT is an activity, gathering, or occurrence (e.g., "Photography Exhibition", "Astronomy Night", "Film Festival")
- If something could be either, analyze the context carefully
- "Astronomy Night" is an EVENT, not a person
- Return null if you're not confident
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        
        # Track token usage if state provided
        if state:
            state.update_token_usage(response)
        
        content = response.choices[0].message.content.strip()
        
        # Clean markdown formatting
        if content.startswith('```'):
            lines = content.split('\n')
            content = '\n'.join(lines[1:-1])
        
        data = json.loads(content)
        person = data.get("person")
        event = data.get("event")
        
        return (
            person if isinstance(person, str) and person.strip() else None,
            event if isinstance(event, str) and event.strip() else None
        )
        
    except Exception as e:
        print(f"Warning: LLM entity extraction failed: {e}")
        return (None, None)


def extract_keywords_for_search(client: OpenAI, question: str, state=None) -> List[str]:
    """
    Extract search keywords from question using LLM.
    
    Args:
        client: OpenAI client instance
        question: Natural language question
        state: Optional search state for token tracking
        
    Returns:
        List of extracted keywords
    """
    prompt = f"""
Extract key search terms from this question for semantic search.
Return 2-4 important keywords/phrases that would help find relevant events.

Question: {question}

Return ONLY a JSON array like this: ["keyword1", "keyword2", "keyword3"]
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        
        # Track token usage
        if state:
            state.update_token_usage(response)
        
        content = response.choices[0].message.content.strip()
        
        # Clean markdown formatting
        if content.startswith('```'):
            content = content.split('\n')[1:-1]
            content = '\n'.join(content)
        
        keywords = json.loads(content)
        return keywords if isinstance(keywords, list) else []
        
    except Exception as e:
        print(f"Warning: Keyword extraction failed: {e}")
        # Fallback: simple word extraction
        words = question.lower().split()
        stop_words = {
            'consider', 'events', 'involving', 'list', 'locations',
            'where', 'these', 'took', 'place', 'without', 'mentioning', 'themselves'
        }
        return [w for w in words if len(w) > 3 and w not in stop_words][:4]

