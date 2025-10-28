"""
Search State Management

This module manages the state of an agentic search session,
tracking iterations, queries, and token usage.
"""

import uuid
from typing import Any, Dict, List, Optional


class SearchState:
    """
    Maintains the state of an agentic search session.
    
    This class tracks all information about a search session including
    the question, iteration count, query history, errors, and token usage.
    """
    
    def __init__(self, question: str):
        """
        Initialize a new search state.
        
        Args:
            question: The user's question to answer
        """
        self.session_id = str(uuid.uuid4())
        self.question = question
        self.iteration = 0
        self.max_iterations = 5

        # Query execution history
        self.query_history: List[str] = []
        self.reasoning: List[str] = []

        # Results and errors
        self.final_answer: Optional[Any] = None
        self.last_error: Optional[str] = None
        self.last_result_rows: int = 0

        # Column tracking for query refinement
        self.last_missing_cols: List[str] = []
        self.last_row_keys: List[str] = []
        
        # Search optimization hints
        self.search_field_hint: Optional[str] = None
        
        # Token usage tracking
        self.token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "calls_count": 0
        }
    
    def add_query(self, query: str) -> None:
        """Add a query to the history."""
        self.query_history.append(query)
    
    def add_reasoning(self, reason: str) -> None:
        """Add a reasoning step to the chain."""
        self.reasoning.append(reason)
    
    def update_token_usage(self, response) -> None:
        """
        Update token usage statistics from API response.
        
        Args:
            response: OpenAI API response object with usage information
        """
        if hasattr(response, 'usage') and response.usage:
            usage = response.usage
            self.token_usage["prompt_tokens"] += usage.prompt_tokens or 0
            self.token_usage["completion_tokens"] += usage.completion_tokens or 0
            self.token_usage["total_tokens"] += usage.total_tokens or 0
            self.token_usage["calls_count"] += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert search state to dictionary for reporting.
        
        Returns:
            Dictionary representation of the search state
        """
        return {
            "session_id": self.session_id,
            "question": self.question,
            "final_answer": self.final_answer,
            "total_iterations": self.iteration,
            "search_successful": self.final_answer is not None,
            "reasoning_chain": self.reasoning,
            "query_history": self.query_history,
            "token_usage": self.token_usage,
        }

