"""
LLM Query Generator Module

This module handles all LLM interactions for generating Cypher queries,
classifying questions, and providing dynamic query refinement.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from openai import OpenAI
from utils import clean_json_response


class QueryClassifier:
    """
    Classifies questions and determines required output columns.
    """
    
    def __init__(self, client: OpenAI, available_fields: List[str]):
        """
        Initialize query classifier.
        
        Args:
            client: OpenAI client instance
            available_fields: List of available Event node fields
        """
        self.client = client
        self.available_fields = available_fields
    
    def classify_question(self, question: str) -> Dict[str, Any]:
        """
        Classify question and determine required output columns using LLM.
        
        Args:
            question: Natural language question
            
        Returns:
            Dictionary with question type and required columns
        """
        prompt = f"""
Analyze this question and determine what information needs to be returned from a graph database.

Question: {question}

Available Event node fields in the database: {self.available_fields}

Return ONLY a JSON object:
{{
  "analysis": "Brief analysis of what the question is asking for",
  "need_columns": ["list of field names that should be returned to answer this question"],
  "priority_order": ["order fields by importance for answering the question"]
}}

Rules:
- Focus on what the question is actually asking for
- Use only field names that exist in the database
- Be specific about what data is needed to answer the question
- If asking for locations, return ["location"]
- If asking for dates, return ["date", "timestamp"] 
- If asking for events, return ["name", "event_type"]
- If asking for people, return ["participants"]
- For complex questions, include multiple relevant fields
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            content = response.choices[0].message.content.strip()
            
            # Clean markdown formatting
            if content.startswith('```'):
                lines = content.split('\n')
                content = '\n'.join(lines[1:-1])
            
            data = json.loads(content)
            need_columns = data.get("need_columns", [])
            
            # Ensure valid field list
            if not need_columns:
                need_columns = ["location", "date", "name", "event_type"]
                
            return {
                "type": "intelligent_analysis", 
                "need": need_columns,
                "analysis": data.get("analysis", ""),
                "priority": data.get("priority_order", need_columns)
            }
            
        except Exception as e:
            print(f"Warning: LLM classification failed: {e}")
            # Fallback classification
            return self._fallback_classification(question)
    
    def _fallback_classification(self, question: str) -> Dict[str, Any]:
        """
        Simple keyword-based classification as fallback.
        
        Args:
            question: Natural language question
            
        Returns:
            Basic classification dictionary
        """
        question_lower = question.lower()
        
        if "location" in question_lower or "where" in question_lower:
            need_columns = ["location"]
        elif "date" in question_lower or "when" in question_lower:
            need_columns = ["date", "timestamp"]
        elif "event" in question_lower:
            need_columns = ["name", "event_type", "location", "date"]
        else:
            need_columns = ["location", "date", "name", "event_type"]
            
        return {"type": "fallback", "need": need_columns}


class CypherQueryGenerator:
    """
    Generates Cypher queries using LLM with dynamic refinement.
    """
    
    def __init__(self, client: OpenAI, schema_hint: str):
        """
        Initialize Cypher query generator.
        
        Args:
            client: OpenAI client instance
            schema_hint: Database schema description
        """
        self.client = client
        self.schema_hint = schema_hint
    
    def generate_query(
        self,
        question: str,
        need_columns: List[str],
        person: Optional[str],
        keyword: Optional[str],
        prev_query: Optional[str] = None,
        last_error: Optional[str] = None,
        last_rows: Optional[int] = None,
        missing_cols: Optional[List[str]] = None,
        last_keys: Optional[List[str]] = None,
        query_history: Optional[List[str]] = None,
        search_field_hint: Optional[str] = None,
        available_fields: Optional[List[str]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate Cypher query with LLM guidance and refinement.
        
        Args:
            question: Natural language question
            need_columns: Required output columns
            person: Person parameter for filtering
            keyword: Keyword parameter for filtering
            prev_query: Previous query attempt
            last_error: Error from previous attempt
            last_rows: Number of rows returned previously
            missing_cols: Columns missing from previous result
            last_keys: Columns present in previous result
            query_history: Full query history
            search_field_hint: Hint for which field to search
            available_fields: Available database fields
            
        Returns:
            Tuple of (query_string, parameters_dict)
        """
        # Generate constraints dynamically
        constraints = self._generate_constraints(
            question, available_fields or [], need_columns,
            person, keyword, search_field_hint, prev_query, last_error
        )
        
        # Build diagnostic information
        diagnosis = self._build_diagnosis(
            prev_query, query_history, last_rows, last_error,
            missing_cols, last_keys, keyword, question
        )
        
        # Construct prompt
        prompt = self._build_query_prompt(
            question, need_columns, constraints, person, keyword, diagnosis
        )
        
        # Try up to 2 times to generate valid JSON
        for attempt in range(2):
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            text = response.choices[0].message.content.strip()
            
            # Clean response
            text = clean_json_response(text)
            
            try:
                data = json.loads(text)
                query = data.get("query", "")
                params = data.get("params", {}) or {}
                
                if not isinstance(query, str):
                    raise ValueError("`query` must be a string")
                if not isinstance(params, dict):
                    raise ValueError("`params` must be an object")
                
                # Fill in default parameters
                if person and "person" not in params:
                    params["person"] = person
                if keyword and "kw" not in params:
                    params["kw"] = keyword
                
                return query, params
                
            except Exception as e:
                # Add error feedback for retry
                print(f"Warning: JSON parse error: {e}")
                print(f"Warning: Raw response: {repr(text)}")
                prompt += f"""

CRITICAL ERROR: Your previous response was invalid JSON!
Error: {e}
Your response was: {text}

You MUST respond with ONLY this exact format:
{{"query": "YOUR_CYPHER_QUERY_HERE", "params": {{"key": "value"}}}}

No explanation, no comments, no markdown - ONLY the JSON object!
"""
                continue
        
        raise RuntimeError("LLM failed to return a valid JSON query/params.")
    
    def _generate_constraints(
        self, question: str, available_fields: List[str],
        need_columns: List[str], person: Optional[str],
        keyword: Optional[str], search_field_hint: Optional[str],
        prev_query: Optional[str], last_error: Optional[str]
    ) -> List[str]:
        """Generate dynamic query constraints."""
        prompt = f"""
Generate specific Cypher query constraints for this database query task.

Question: {question}
Available Event fields: {available_fields}
Required output columns: {need_columns}
Person parameter: {person}
Keyword parameter: {keyword}
Search field hint: {search_field_hint}
Previous query: {prev_query}
Previous error: {last_error}

Return ONLY a JSON array of constraint strings that will help generate a correct Cypher query:

Example format:
[
  "Use MATCH (e:Event) pattern",
  "Filter by person using participants field if needed",
  "Return only the specified columns with exact aliases",
  "Handle case-insensitive searches appropriately"
]

Focus on:
1. Database schema constraints (available fields)
2. Query syntax requirements  
3. Parameter handling for person/keyword filters
4. Error prevention based on previous failures
5. Field-specific search strategies
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            content = response.choices[0].message.content.strip()
            
            # Clean markdown
            if content.startswith('```'):
                lines = content.split('\n')
                content = '\n'.join(lines[1:-1])
            
            constraints = json.loads(content)
            
            if isinstance(constraints, list) and all(isinstance(c, str) for c in constraints):
                return constraints
            else:
                return self._get_fallback_constraints()
                
        except Exception as e:
            print(f"Warning: Dynamic constraint generation failed: {e}")
            return self._get_fallback_constraints()
    
    def _get_fallback_constraints(self) -> List[str]:
        """Basic fallback constraints."""
        return [
            "Use MATCH (e:Event) to query Event nodes",
            "Return only the required columns with exact aliases",
            "Use case-insensitive filtering where appropriate",
            "Handle parameters correctly in WHERE clauses"
        ]
    
    def _build_diagnosis(
        self, prev_query: Optional[str], query_history: Optional[List[str]],
        last_rows: int, last_error: Optional[str], missing_cols: Optional[List[str]],
        last_keys: Optional[List[str]], keyword: Optional[str], question: str
    ) -> str:
        """Build diagnostic information for query refinement."""
        if prev_query is None:
            return ""
        
        diagnosis = f"\nIteration {len(query_history) if query_history else 1}: "
        diagnosis += f"Previous query returned {last_rows} rows. "
        diagnosis += f"Last error: {last_error or 'none'}.\n"
        
        # Detect common Cypher syntax errors
        if last_error and "Variable" in last_error and "not defined" in last_error:
            if "ANY(" in prev_query and "RETURN" in prev_query:
                diagnosis += "ERROR DETECTED: You're trying to use a variable from ANY() clause in RETURN. "
                diagnosis += "This is invalid Cypher syntax.\n"
                diagnosis += "FIX: Use 'e.participants' instead of the ANY() variable in RETURN clause.\n"
        
        # Add strategy reflection for repeated failures
        if last_rows == 0 and query_history:
            diagnosis += self._generate_strategy_reflection(
                len(query_history), question, keyword, query_history
            )
        
        # Add dynamic diagnosis
        if missing_cols:
            diagnosis += f"Missing columns: {missing_cols}. Include them with exact aliases.\n"
        
        if last_rows == 0 and keyword:
            diagnosis += "Zero rows returned. Try broader keyword matching.\n"
        
        return diagnosis
    
    def _generate_strategy_reflection(
        self, iteration_num: int, question: str,
        keyword: Optional[str], query_history: List[str]
    ) -> str:
        """Generate strategic reflection for repeated failures."""
        if iteration_num <= 1:
            return ""
        
        repeated_query = (len(query_history) >= 2 and 
                         query_history[-1] == query_history[-2])
        
        if repeated_query:
            return "\nCRITICAL: You repeated the same query! Try a different approach.\n"
        else:
            return f"\nSTRATEGY REFLECTION: Iteration {iteration_num} - " \
                   f"previous approach failed. Try broadening your search strategy.\n"
    
    def _build_query_prompt(
        self, question: str, need_columns: List[str],
        constraints: List[str], person: Optional[str],
        keyword: Optional[str], diagnosis: str
    ) -> str:
        """Build the final query generation prompt."""
        return f"""
You are a Cypher generator. Do not use any templates or examples.
Database schema hint: {self.schema_hint}

Question: {question}

Required output columns (exact aliases): {need_columns}
Rules:
- {chr(10) + '- '.join(constraints)}

{('Parameters to expect: ' + json.dumps({'person': person, 'kw': keyword})) if (person or keyword) else 'No external parameters are required.'}
{diagnosis}

CRITICAL: Your response must be EXACTLY this format:
{{"query": "YOUR_CYPHER_QUERY_HERE", "params": {{"param_name": "param_value"}}}}

Requirements:
1. Start with {{ and end with }}
2. Use double quotes for all strings
3. No comments, no explanations, no markdown
4. No text before or after the JSON
5. The "query" field must contain a valid Cypher query string
6. The "params" field must be a JSON object (use {{}} if empty)

Example format (DO NOT copy this query, create your own):
{{"query": "MATCH (e:Event) WHERE e.name = $kw RETURN e.location AS location", "params": {{"kw": "some_value"}}}}
"""


class AnswerGenerator:
    """
    Generates final answers from query results using LLM.
    """
    
    def __init__(self, client: OpenAI):
        """
        Initialize answer generator.
        
        Args:
            client: OpenAI client instance
        """
        self.client = client
    
    def generate_answer(self, question: str, rows: List[Dict]) -> Any:
        """
        Generate final answer from query results.
        
        Args:
            question: Original question
            rows: Query result rows
            
        Returns:
            Final answer (string, list, or None)
        """
        if not rows:
            return None
        
        # Determine if this is a list question
        question_lower = question.lower()
        is_list_question = any(keyword in question_lower for keyword in [
            "all dates", "all events", "all locations", "list of", "provide a list", 
            "chronological list", "describe all", "reflect on all"
        ])
        
        # Prepare data summary
        if is_list_question and len(rows) > 10:
            sample_rows = rows[:25]
            data_info = f"Total {len(rows)} rows, showing first 25 for analysis"
            
            # Provide complete unique values for list questions
            if len(rows) > 25:
                all_values = {}
                for key in rows[0].keys():
                    values = [str(row.get(key, "")) for row in rows if row.get(key)]
                    all_values[key] = list(set(values))
                
                data_info += f"\nComplete unique values across all {len(rows)} rows:"
                for key, values in all_values.items():
                    data_info += f"\n{key}: {len(values)} unique values: {values[:10]}"
                    if len(values) > 10:
                        data_info += "..."
        else:
            if len(rows) > 10:
                sample_rows = rows[:10]
                data_info = f"Total {len(rows)} rows, showing first 10 as sample"
            else:
                sample_rows = rows
                data_info = f"All {len(rows)} rows"
        
        # Build data summary
        data_summary = []
        for i, row in enumerate(sample_rows):
            data_summary.append(f"Row {i+1}: {dict(row)}")
        
        prompt = f"""
You are analyzing query results to answer a specific question. Based on the question and the data returned from the database, provide the most appropriate answer.

Question: {question}

Data returned ({data_info}):
{chr(10).join(data_summary)}

Instructions:
1. Read the question carefully to understand what is being asked
2. Analyze the data to extract the relevant information
3. Return the answer in the most appropriate format:
   - For single item questions: return the item directly (string/number)
   - For list questions: return a JSON array ["item1", "item2", ...]
   - For chronological questions: sort by date and return appropriately
   - For "most recent" questions: find the latest date and return the requested field
4. If the question asks for dates, return ALL dates from the data
5. If the question asks for locations, return ALL locations from the data
6. If the question asks for activities/events, return ALL activity/event names from the data
7. If the question asks for descriptions, return ALL descriptions from the data
8. Remove duplicates appropriately
9. Sort chronologically if requested
10. IMPORTANT: If the question asks for "all" or "list of" something, make sure to include ALL items from the data, not just one

Return ONLY the final answer (no explanation, no extra text):
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            answer_text = response.choices[0].message.content.strip()
            
            # Try to parse JSON array
            if answer_text.startswith('[') and answer_text.endswith(']'):
                try:
                    return json.loads(answer_text)
                except:
                    # If JSON parsing fails, split by comma
                    items = answer_text[1:-1].split(',')
                    return [item.strip().strip('"') for item in items if item.strip()]
            
            # Clean quotes
            answer_text = answer_text.strip('"').strip("'")
            
            return answer_text
            
        except Exception as e:
            print(f"ERROR in answer generation: {e}")
            # Fallback logic
            if len(rows) == 1:
                for value in rows[0].values():
                    if value:
                        return str(value)
            else:
                first_key = list(rows[0].keys())[0]
                return [str(row.get(first_key, "")) for row in rows if row.get(first_key)]
            
            return "No answer found"

