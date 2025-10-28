"""
Agentic Search Engine Core

This module implements the main search engine logic that orchestrates
LLM-based query generation, execution, and iterative refinement.
"""

import os
import json
from typing import Any, Dict, List, Optional, Tuple
from neo4j import GraphDatabase
from openai import OpenAI

# Import local modules
from search_state import SearchState
from entity_extraction import extract_entities_llm, extract_keywords_for_search
from semantic_search import SemanticSearchEngine, KeywordSemanticSearcher, enhance_keyword_with_semantics
from llm_query_generator import QueryClassifier, CypherQueryGenerator, AnswerGenerator
from utils import to_list


class AgenticSearchEngine:
    """
    Main agentic search engine that uses LLM to generate and refine Cypher queries.
    
    This engine provides a template-free approach where all queries are dynamically
    generated based on the question, with iterative refinement based on results.
    """
    
    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        neo4j_database: Optional[str] = None,
    ):
        """
        Initialize the agentic search engine.
        
        Args:
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            openai_api_key: OpenAI API key
            neo4j_database: Neo4j database name
        """
        self.database = neo4j_database or os.getenv("NEO4J_DATABASE", "neo4j")
        
        # Initialize Neo4j driver
        self.driver = GraphDatabase.driver(
            neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(
                neo4j_user or os.getenv("NEO4J_USER", "neo4j"),
                neo4j_password or os.getenv("NEO4J_PASSWORD", "password")
            )
        )
        
        # Initialize OpenAI client
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=api_key)

        # Schema description (no templates, just structure)
        self.schema_hint = (
            "There is a single label `Event` you must use. "
            "`Event` has properties: `name` (string), `date` (string like 'March 23, 2024'), "
            "`location` (string), `event_type` (string), `description` (string), "
            "`participants` (array of strings). "
            "Do NOT use any relationships. Only query `Event` nodes and their properties. "
            "Participants are stored as an array of names on the `Event` node."
        )
        
        # Initialize semantic search
        self.semantic_searcher = SemanticSearchEngine(self.database, self.client)
        
        # Initialize keyword searcher
        self.keyword_searcher = None
        try:
            self.keyword_searcher = KeywordSemanticSearcher(self.database)
        except Exception as e:
            print(f"Warning: Failed to load keyword searcher: {e}")
        
        # Initialize LLM components
        self.available_fields = self._get_available_event_fields()
        self.classifier = QueryClassifier(self.client, self.available_fields)
        self.query_generator = CypherQueryGenerator(self.client, self.schema_hint)
        self.answer_generator = AnswerGenerator(self.client)
    
    def _get_available_event_fields(self) -> List[str]:
        """
        Dynamically retrieve available Event node fields from database.
        
        Returns:
            List of field names
        """
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (e:Event)
                WITH e LIMIT 1
                RETURN keys(e) AS field_names
                """)
                
                for record in result:
                    return record["field_names"]
                    
                # Fallback if no data
                return ["name", "event_type", "location", "date", "timestamp", 
                       "participants", "description"]
                
        except Exception as e:
            print(f"Warning: Failed to get database fields: {e}")
            return ["name", "event_type", "location", "date", "timestamp", 
                   "participants", "description"]
    
    def _get_sample_database_content(self) -> str:
        """
        Get sample database content for reflection and diagnosis.
        
        Returns:
            Formatted string with sample events
        """
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (e:Event) 
                RETURN e.name, e.event_type, e.location, e.participants[0..2] as sample_participants
                LIMIT 5
                """)
                
                samples = []
                for record in result:
                    samples.append({
                        'name': record['name'],
                        'event_type': record['event_type'], 
                        'location': record['location'],
                        'participants': record['sample_participants']
                    })
                
                return "Sample events in database:\n" + "\n".join([
                    f"- Name: '{s['name']}', Type: '{s['event_type']}', Location: '{s['location']}'"
                    for s in samples
                ])
                
        except Exception as e:
            return f"Could not retrieve sample data: {e}"
    
    def _reflect_and_adapt_search(
        self, question: str, failed_query: str, 
        failed_params: dict, state: SearchState
    ) -> Optional[Dict]:
        """
        Reflect on search failure and propose new search strategy.
        
        Args:
            question: Original question
            failed_query: Query that failed
            failed_params: Parameters that were used
            state: Current search state
            
        Returns:
            Dictionary with reflection and new strategy, or None
        """
        try:
            sample_data = self._get_sample_database_content()
            
            reflection_prompt = f"""
You are a search engine that just failed to find results. Reflect on why the search failed and suggest a new approach.

ORIGINAL QUESTION: {question}

FAILED QUERY: {failed_query}
FAILED PARAMETERS: {failed_params}

SAMPLE DATABASE CONTENT:
{sample_data}

SEARCH HISTORY: {state.query_history}

Think step by step:
1. Why might the original search have failed?
2. What alternative keywords or search approaches could work?
3. Based on the sample data, what similar events might exist?

Return ONLY a JSON object with your reflection and new search strategy:
{{
  "analysis": "Why the search likely failed",
  "new_strategy": "What to try instead",
  "new_keyword": "Alternative keyword to search for (if any)",
  "new_person": "Alternative person name (if any)", 
  "search_field_hint": "Which field to focus on (name, event_type, description, etc.)",
  "reasoning": "Brief explanation of the new approach"
}}

If you cannot suggest improvements, return {{"no_suggestions": true}}
"""
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": reflection_prompt}],
                temperature=0.1
            )
            
            state.update_token_usage(response)
            
            content = response.choices[0].message.content.strip()
            
            # Clean markdown
            if content.startswith('```'):
                lines = content.split('\n')
                content = '\n'.join(lines[1:-1])
            
            reflection = json.loads(content)
            
            if reflection.get('no_suggestions'):
                return None
            
            # Enhance keyword with semantic search if available
            new_keyword = reflection.get('new_keyword')
            if new_keyword and self.keyword_searcher:
                enhanced = enhance_keyword_with_semantics(
                    self.keyword_searcher, new_keyword
                )
                if enhanced and enhanced.get('keyword') != new_keyword:
                    reflection['new_keyword'] = enhanced['keyword']
                    reflection['search_field_hint'] = enhanced['field']
                    reflection['reasoning'] += (
                        f" (Enhanced with semantic search: {enhanced['keyword']} "
                        f"in field {enhanced['field']})"
                    )
            
            return reflection
            
        except Exception as e:
            print(f"Warning: Reflection failed: {e}")
            return None
    
    def _execute_query(self, query: str, params: Dict[str, Any]) -> Tuple[List[Dict], Optional[str]]:
        """
        Execute Cypher query on Neo4j database.
        
        Args:
            query: Cypher query string
            params: Query parameters
            
        Returns:
            Tuple of (result_rows, error_message)
        """
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, **params)
                rows = [dict(r) for r in result]
                return rows, None
        except Exception as e:
            return [], str(e)
    
    def search(self, question: str, max_iterations: int = 5) -> Dict[str, Any]:
        """
        Execute agentic search with iterative refinement.
        
        Args:
            question: Natural language question to answer
            max_iterations: Maximum number of refinement iterations
            
        Returns:
            Dictionary with search results and metadata
        """
        state = SearchState(question)
        state.max_iterations = max_iterations

        print(f"Starting agentic search for: {question}")
        print(f"Session: {state.session_id}")

        # Extract entities using LLM
        person, event_keyword = extract_entities_llm(self.client, question, state)

        # Classify question to determine required columns
        classification = self.classifier.classify_question(question)
        need_columns: List[str] = classification["need"]

        # Main iteration loop
        while state.iteration < state.max_iterations and state.final_answer is None:
            state.iteration += 1
            print(f"\n-- Iteration {state.iteration} --")

            # Generate query
            try:
                query, params = self.query_generator.generate_query(
                    question=question,
                    need_columns=need_columns,
                    person=person,
                    keyword=event_keyword,
                    prev_query=state.query_history[-1] if state.query_history else None,
                    last_error=state.last_error,
                    last_rows=state.last_result_rows,
                    missing_cols=state.last_missing_cols,
                    last_keys=state.last_row_keys,
                    query_history=state.query_history,
                    search_field_hint=state.search_field_hint,
                    available_fields=self.available_fields,
                )
            except Exception as e:
                state.add_reasoning(f"Query generation error: {e}")
                break

            state.add_query(query)
            print("Generated query:", query)
            print("Params:", params)

            # Execute query
            rows, error = self._execute_query(query, params)
            state.last_error = error
            state.last_result_rows = len(rows)
            state.last_row_keys = list(rows[0].keys()) if rows else []
            
            if error:
                print("Execution error:", error)
                state.add_reasoning(f"Execution error: {error}")
                continue

            print(f"Rows: {len(rows)}")
            if rows:
                print("First row keys:", list(rows[0].keys()))

            # Check for missing columns
            missing = [c for c in need_columns if rows and c not in rows[0]]
            state.last_missing_cols = missing

            # Special handling for latest_activity questions
            if classification["type"] == "latest_activity_of_person" and rows:
                has_date = any(f in rows[0] for f in ["date", "timestamp"])
                has_event = any(f in rows[0] for f in ["event_type", "name", "event", "activity"])
                if has_date or has_event:
                    missing = []

            if rows and missing:
                msg = f"Missing columns {missing}, will request them in next iteration"
                print(msg)
                state.add_reasoning(msg)
                continue

            if rows:
                # Generate final answer
                state.final_answer = self.answer_generator.generate_answer(question, rows)
                break

            # Try reflection-based search adaptation
            if not rows:
                reflection = self._reflect_and_adapt_search(question, query, params, state)
                if reflection:
                    if reflection.get('new_person'):
                        person = reflection['new_person']
                    if reflection.get('new_keyword'):
                        event_keyword = reflection['new_keyword']
                    if reflection.get('new_need_cols'):
                        need_columns = reflection['new_need_cols']
                    if reflection.get('search_field_hint'):
                        state.search_field_hint = reflection['search_field_hint']
                    
                    state.add_reasoning(reflection.get('reasoning', 'Reflection suggested new approach'))
                    print(f"Reflection: {reflection.get('reasoning')}")
                    continue

            state.add_reasoning("Zero rows returned; will attempt refinement")

        # Prepare result
        result = state.to_dict()
        result["standardized_answer"] = to_list(state.final_answer)
        
        print("Final:", result)
        return result
    
    def close(self):
        """Close database connection."""
        if hasattr(self, 'driver') and self.driver:
            self.driver.close()

