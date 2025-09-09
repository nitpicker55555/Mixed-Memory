# """
# Agentic Search Engine for Knowledge Graph Question Answering

# This module implements a React-style agentic search system that:
# 1. Observes the question and current state
# 2. Thinks about the best approach 
# 3. Acts by generating and executing Cypher queries dynamically
# 4. Reflects on results and decides whether to continue or output answer

# No hardcoded queries - everything is generated dynamically based on analysis.
# """

# import json
# import uuid
# import os
# from datetime import datetime
# from typing import Dict, List, Optional, Tuple, Any
# from openai import OpenAI
# from neo4j import GraphDatabase

# # Constants for date conversion
# MONTH_CONVERSION_CASE = """CASE 
#     WHEN e.date CONTAINS 'January' THEN '01'
#     WHEN e.date CONTAINS 'February' THEN '02'
#     WHEN e.date CONTAINS 'March' THEN '03'
#     WHEN e.date CONTAINS 'April' THEN '04'
#     WHEN e.date CONTAINS 'May' THEN '05'
#     WHEN e.date CONTAINS 'June' THEN '06'
#     WHEN e.date CONTAINS 'July' THEN '07'
#     WHEN e.date CONTAINS 'August' THEN '08'
#     WHEN e.date CONTAINS 'September' THEN '09'
#     WHEN e.date CONTAINS 'October' THEN '10'
#     WHEN e.date CONTAINS 'November' THEN '11'
#     WHEN e.date CONTAINS 'December' THEN '12'
#     ELSE '00'
# END"""

# DATE_CONVERSION_TEMPLATE = """WITH e, 
#      {month_case} as month_num,
#      split(e.date, ' ')[1] as day,
#      split(e.date, ' ')[2] as year
# WITH e{additional_fields}, year + '-' + month_num + '-' + 
#      CASE WHEN size(day) = 3 THEN substring(day, 0, 2) ELSE day END as sort_date"""

# # Load environment variables from .env file if it exists
# try:
#     from dotenv import load_dotenv
#     load_dotenv()
#     print("✅ Loaded environment variables from .env file")
# except ImportError:
#     print("⚠️ python-dotenv not installed, trying to load .env manually...")
#     # Manual .env loading as fallback
#     env_file = os.path.join(os.path.dirname(__file__), '.env')
#     if os.path.exists(env_file):
#         with open(env_file, 'r') as f:
#             for line in f:
#                 line = line.strip()
#                 if line and not line.startswith('#') and '=' in line:
#                     key, value = line.split('=', 1)
#                     os.environ[key.strip()] = value.strip()
#         print("✅ Manually loaded environment variables from .env file")


# class SearchState:
#     """Maintains the current state of an agentic search session"""
    
#     def __init__(self, question: str, session_id: str = None):
#         self.session_id = session_id or str(uuid.uuid4())
#         self.question = question
#         self.iteration_count = 0
#         self.max_iterations = 5
#         self.attempted_strategies = []
#         self.query_history = []
#         self.result_history = []
#         self.confidence_score = 0.0
#         self.final_answer = None
#         self.reasoning_chain = []
#         self.current_hypothesis = None
#         self.search_context = {}
#         self.previous_attempts = []
        
#     def add_iteration(self, strategy: str, query: str, results: List[Dict], 
#                      confidence: float, reasoning: str):
#         """Add a new iteration to the search history"""
#         iteration = {
#             "iteration": self.iteration_count,
#             "timestamp": datetime.now().isoformat(),
#             "strategy": strategy,
#             "query": query,
#             "results": results,
#             "confidence": confidence,
#             "reasoning": reasoning
#         }
        
#         self.attempted_strategies.append(strategy)
#         self.query_history.append(query)
#         self.result_history.append(results)
#         self.reasoning_chain.append(reasoning)
#         self.confidence_score = confidence
#         self.iteration_count += 1
        
#         return iteration


# class CypherQueryGenerator:
#     """Dynamically generates Cypher queries based on analysis and context"""
    
#     def __init__(self, gpt_client: OpenAI, property_keys_data: Dict = None):
#         self.gpt_client = gpt_client
#         self.property_keys_data = property_keys_data
    
#     def _get_temporal_patterns(self) -> str:
#         """Generate temporal query patterns using templates"""
#         base_pattern = "MATCH (p:Person)-[:PARTICIPATED_IN]->(e:Event) WHERE p.name = 'Name' AND e.date <> ''"
#         date_conv = DATE_CONVERSION_TEMPLATE.format(
#             month_case=MONTH_CONVERSION_CASE, 
#             additional_fields=""
#         )
#         date_conv_with_original = DATE_CONVERSION_TEMPLATE.format(
#             month_case=MONTH_CONVERSION_CASE, 
#             additional_fields=".date as original_date"
#         )
        
#         return f"""
# 1. Most recent location: 
# {base_pattern}
# {date_conv}
# RETURN e.location ORDER BY sort_date DESC LIMIT 1

# 2. Chronological location list:
# {base_pattern}
# {date_conv}
# ORDER BY sort_date ASC
# WITH COLLECT(DISTINCT e.location) as locations
# UNWIND locations as location
# RETURN location

# 3. Chronological date list:
# {base_pattern}
# {date_conv_with_original}
# ORDER BY sort_date ASC
# WITH COLLECT(DISTINCT original_date) as unique_dates
# UNWIND unique_dates as date
# RETURN date"""
    
#     def get_available_properties(self, node_label: str) -> List[str]:
#         """Get available properties for a specific node label"""
#         if not self.property_keys_data:
#             return []
        
#         property_keys = self.property_keys_data.get('property_keys', {})
#         return property_keys.get(node_label, [])
    
#     def get_all_labels(self) -> List[str]:
#         """Get all available node labels"""
#         if not self.property_keys_data:
#             return ['Event', 'Person', 'Location']  # fallback
        
#         property_keys = self.property_keys_data.get('property_keys', {})
#         return [label for label in property_keys.keys() if label != '_relationships']
    
#     def get_relationship_types(self) -> List[str]:
#         """Get all available relationship types"""
#         if not self.property_keys_data:
#             return ['OCCURRED_AT', 'PARTICIPATED_IN']  # fallback
        
#         property_keys = self.property_keys_data.get('property_keys', {})
#         relationships = property_keys.get('_relationships', {})
#         return list(relationships.keys())
    
#     def _build_context_info(self, context: Dict) -> str:
#         """Build context information string"""
#         return f"Additional context: {json.dumps(context, indent=2)}" if context else ""
    
#     def _build_vector_info(self, vector_search_results: List[Dict]) -> str:
#         """Build vector search results string"""
#         if not vector_search_results:
#             return ""
        
#         vector_info = "Vector search found these relevant nodes:\n"
#         for i, result in enumerate(vector_search_results[:5]):
#             vector_info += f"- Node {result['node_id']} (similarity: {result['similarity']:.3f})\n"
#         return vector_info
    
#     def _build_previous_info(self, previous_attempts: List[str]) -> str:
#         """Build previous attempts learning string"""
#         if not previous_attempts:
#             return ""
        
#         available_relationships = self.get_relationship_types()
#         return f"""
# LEARNING FROM PREVIOUS FAILURES:
# {chr(10).join(previous_attempts)}

# IMPORTANT: Analyze why previous queries failed and avoid the same mistakes:
# - If a relationship type caused errors, use only verified relationships: {', '.join(available_relationships)}
# - If queries returned 0 results, the schema might be wrong - try simpler patterns first
# - If dates are duplicated, use DISTINCT properly in collection operations
# """
    
#     def _build_property_info(self) -> str:
#         """Build property information string"""
#         available_labels = self.get_all_labels()
#         property_info = "Available properties by node type:\n"
#         for label in available_labels:
#             props = self.get_available_properties(label)
#             property_info += f"- {label}: {', '.join(props)}\n"
#         return property_info
    
#     def _is_temporal_query(self, question: str) -> bool:
#         """Check if question is asking for chronological/temporal information"""
#         temporal_keywords = ['chronological', 'chronologically', 'timeline', 'earliest', 'latest', 'recent', 'dates', 'order', 'sequence', 'first', 'last']
#         return any(keyword in question.lower() for keyword in temporal_keywords)
    
#     def _build_temporal_guidance(self) -> str:
#         """Build temporal query guidance"""
#         return f"""

# SPECIAL GUIDANCE FOR CHRONOLOGICAL/TEMPORAL QUERIES:
# - Event nodes have 'date' property in format "Month DD, YYYY" 
# - Filter empty dates: WHERE e.date <> ''
# - Use e.location property (NO LOCATED_AT relationship exists!)
# - Manual date conversion required for proper sorting

# COMMON TEMPORAL QUERY PATTERNS:
# {self._get_temporal_patterns()}

# IMPORTANT: Use COLLECT(DISTINCT ...) for list queries to remove duplicates.
# """
    
#     def generate_query(self, question: str, strategy: str, context: Dict = None, 
#                       previous_attempts: List[str] = None, vector_search_results: List[Dict] = None) -> Tuple[str, str]:
#         """
#         Generate a Cypher query dynamically based on question analysis
        
#         Returns:
#             Tuple[str, str]: (cypher_query, reasoning)
#         """
        
#         # Build all context information
#         context_info = self._build_context_info(context)
#         vector_info = self._build_vector_info(vector_search_results)
#         previous_info = self._build_previous_info(previous_attempts)
#         property_info = self._build_property_info()
        
#         # Get schema information
#         available_labels = self.get_all_labels()
#         available_relationships = self.get_relationship_types()
        
#         # Add temporal guidance if needed
#         temporal_guidance = self._build_temporal_guidance() if self._is_temporal_query(question) else ""
        
#         prompt = f"""
# You are an expert in generating Cypher queries for Neo4j knowledge graphs. 
# Your task is to create a precise Cypher query to answer the given question.

# Question: {question}
# Strategy: {strategy}
# {context_info}
# {previous_info}
# {vector_info}

# ACTUAL Knowledge Graph Schema (from database analysis):
# - Available Node Labels: {', '.join(available_labels)}
# - Available Relationships: {', '.join(available_relationships)}

# {property_info}{temporal_guidance}

# IMPORTANT: You MUST only use the node labels, relationships, and properties listed above. 
# Do NOT use labels like 'Organization' or 'Topic' or relationships like 'RELATES_TO' if they are not in the available lists.

# Generate a Cypher query that will help answer this question. Consider:
# 1. What entities are mentioned in the question?
# 2. What relationships are implied?
# 3. What information needs to be retrieved?
# 4. How to structure the query for optimal results?
# 5. Use only the available schema elements listed above
# 6. If this is a temporal/chronological query, pay special attention to the date property and sorting

# Provide your response in this JSON format:
# {{
#     "cypher_query": "MATCH ... RETURN ...",
#     "reasoning": "Explanation of why this query should work",
#     "expected_results": "Description of what kind of results this should return"
# }}

# Make sure the query is syntactically correct and follows Neo4j Cypher syntax.
# Use only the available node labels, relationships and properties shown above.
# """

#         try:
#             response = self.gpt_client.chat.completions.create(
#                 model="gpt-4",
#                 messages=[{"role": "user", "content": prompt}],
#                 temperature=0.7
#             )
            
#             result = json.loads(response.choices[0].message.content)
#             return result["cypher_query"], result["reasoning"]
            
#         except Exception as e:
#             # Fallback to a basic query structure
#             basic_query = f"""
#             MATCH (n)
#             WHERE n.name CONTAINS '{question.split()[0] if question.split() else 'unknown'}'
#             RETURN n.name, labels(n), properties(n)
#             LIMIT 10
#             """
#             return basic_query, f"Fallback query due to error: {str(e)}"


# class ResultEvaluator:
#     """Evaluates query results and decides whether they answer the question"""
    
#     def __init__(self, gpt_client: OpenAI):
#         self.gpt_client = gpt_client
    
#     def evaluate_results(self, question: str, query: str, results: List[Dict], 
#                         iteration_context: Dict = None) -> Tuple[float, str, bool, Optional[str], Optional[str]]:
#         """
#         Evaluate whether the results adequately answer the question
        
#         Returns:
#             Tuple[float, str, bool, Optional[str], Optional[str]]: 
#             (confidence_score, reasoning, should_continue, suggested_answer, improvement_suggestions)
#         """
        
#         if not results:
#             return 0.0, "No results returned from query", True, None, "Check relationship types and schema - query might use non-existent relationships"
        
#         # Prepare results for analysis
#         results_summary = self._summarize_results(results)
        
#         context_info = ""
#         if iteration_context:
#             context_info = f"Search context: {json.dumps(iteration_context, indent=2)}"
        
#         prompt = f"""
# You are evaluating whether query results adequately answer a question.

# Question: {question}
# Cypher Query Used: {query}
# Results Summary: {results_summary}
# {context_info}

# Analyze the results and determine:
# 1. Do these results contain information that answers the question?
# 2. How confident are you that this is a complete/correct answer? (0-100%)
# 3. Should we continue searching or is this sufficient?
# 4. If sufficient, what is the final answer?

# CRITICAL ERROR DETECTION:
# - If query returned 0 results, analyze the query for common issues:
#   * Wrong relationship types (e.g., using LOCATED_AT which doesn't exist)
#   * Incorrect node labels or property names
#   * Overly restrictive WHERE clauses
# - If query had relationship warnings, suggest using actual relationship types
# - If results seem incomplete, suggest alternative query approaches

# Provide your evaluation in this JSON format:
# {{
#     "confidence_score": 85,
#     "reasoning": "Detailed explanation of your evaluation",
#     "should_continue": false,
#     "suggested_answer": "The final answer based on the results",
#     "improvement_suggestions": "If continuing, what should be tried next? Be specific about query fixes needed."
# }}

# Be thorough in your analysis. Consider completeness, relevance, and accuracy.
# """

#         try:
#             response = self.gpt_client.chat.completions.create(
#                 model="gpt-4",
#                 messages=[{"role": "user", "content": prompt}],
#                 temperature=0.3
#             )
            
#             evaluation = json.loads(response.choices[0].message.content)
            
#             confidence = evaluation.get("confidence_score", 0) / 100.0
#             reasoning = evaluation.get("reasoning", "No reasoning provided")
#             should_continue = evaluation.get("should_continue", True)
#             suggested_answer = evaluation.get("suggested_answer")
#             improvement_suggestions = evaluation.get("improvement_suggestions", "")
            
#             return confidence, reasoning, should_continue, suggested_answer, improvement_suggestions
            
#         except Exception as e:
#             # Fallback evaluation
#             if results and len(results) > 0:
#                 return 0.5, f"Basic evaluation - found {len(results)} results", True, None, ""
#             else:
#                 return 0.0, f"Evaluation error: {str(e)}", True, None, "Evaluation error - try simpler query patterns"
    
#     def _summarize_results(self, results: List[Dict]) -> str:
#         """Create a concise summary of results for analysis"""
#         if not results:
#             return "No results"
        
#         summary = f"Found {len(results)} results:\n"
#         for i, result in enumerate(results[:5]):  # Limit to first 5 for summary
#             summary += f"{i+1}. {json.dumps(result, indent=2)}\n"
        
#         if len(results) > 5:
#             summary += f"... and {len(results) - 5} more results"
        
#         return summary


# class StrategySelector:
#     """Selects the best search strategy based on question analysis"""
    
#     def __init__(self, gpt_client: OpenAI):
#         self.gpt_client = gpt_client
    
#     def select_strategy(self, question: str, previous_strategies: List[str] = None,
#                        search_context: Dict = None) -> Tuple[str, str, Dict]:
#         """
#         Analyze question and select the best search strategy
        
#         Returns:
#             Tuple[str, str, Dict]: (strategy_name, reasoning, context_updates)
#         """
        
#         previous_info = ""
#         if previous_strategies:
#             previous_info = f"Already tried strategies: {', '.join(previous_strategies)}"
        
#         context_info = ""
#         if search_context:
#             context_info = f"Current context: {json.dumps(search_context, indent=2)}"
        
#         prompt = f"""
# Analyze this question and determine the best search strategy for a knowledge graph.

# Question: {question}
# {previous_info}
# {context_info}

# Available strategy types:
# 1. entity_focused - Find specific entities mentioned in the question
# 2. relationship_focused - Explore relationships between entities
# 3. temporal_focused - Search based on time/sequence constraints  
# 4. location_focused - Search based on location/place constraints
# 5. broad_exploration - Cast a wide net to find relevant information
# 6. constraint_refinement - Add specific constraints to narrow results
# 7. pattern_matching - Look for specific patterns or structures

# Choose the most appropriate strategy and provide context updates.

# Respond in this JSON format:
# {{
#     "strategy": "entity_focused",
#     "reasoning": "Why this strategy is best for this question",
#     "context_updates": {{
#         "target_entities": ["entity1", "entity2"],
#         "key_constraints": ["constraint1"],
#         "search_focus": "what to focus on"
#     }}
# }}
# """

#         try:
#             response = self.gpt_client.chat.completions.create(
#                 model="gpt-4",
#                 messages=[{"role": "user", "content": prompt}],
#                 temperature=0.7
#             )
            
#             result = json.loads(response.choices[0].message.content)
            
#             strategy = result.get("strategy", "broad_exploration")
#             reasoning = result.get("reasoning", "Default strategy selection")
#             context_updates = result.get("context_updates", {})
            
#             return strategy, reasoning, context_updates
            
#         except Exception as e:
#             # Fallback strategy selection
#             if not previous_strategies:
#                 return "entity_focused", f"Fallback to entity_focused due to error: {str(e)}", {}
#             else:
#                 # Try a different strategy if previous ones failed
#                 all_strategies = ["entity_focused", "relationship_focused", "temporal_focused", 
#                                 "location_focused", "broad_exploration", "constraint_refinement"]
#                 remaining = [s for s in all_strategies if s not in previous_strategies]
#                 if remaining:
#                     return remaining[0], f"Trying alternative strategy due to error: {str(e)}", {}
#                 else:
#                     return "broad_exploration", "All strategies attempted, using broad exploration", {}


# class AgenticSearchEngine:
#     """
#     Main agentic search engine implementing React-style search loop:
#     Observe -> Think -> Act -> Reflect
#     """
    
#     def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str, 
#                  openai_api_key: str = None, neo4j_database: str = None):
#         # Store database connection info
#         self.neo4j_database = neo4j_database or os.getenv("NEO4J_DATABASE", "neo4j")
        
#         # Initialize connections
#         self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
#         if openai_api_key:
#             self.gpt_client = OpenAI(api_key=openai_api_key)
#         else:
#             self.gpt_client = OpenAI()  # Uses environment variable
        
#         # Initialize database preparator
#         import sys
#         # Add the graph_generation directory to the path
#         current_dir = os.path.dirname(os.path.abspath(__file__))
#         graph_generation_dir = os.path.join(os.path.dirname(current_dir), 'graph_generation')
#         if graph_generation_dir not in sys.path:
#             sys.path.insert(0, graph_generation_dir)
        
#         from database_preparation import DatabasePreparator
#         self.db_preparator = DatabasePreparator(
#             neo4j_uri=neo4j_uri,
#             neo4j_user=neo4j_user,
#             neo4j_password=neo4j_password,
#             neo4j_database=self.neo4j_database,
#             openai_api_key=openai_api_key
#         )
        
#         # Prepare database (load embeddings and property keys)
#         self.preparation_result = self.db_preparator.prepare_database()
#         self.property_keys_data = self.db_preparator.load_property_keys()
        
#         # Initialize components with property key data
#         self.query_generator = CypherQueryGenerator(self.gpt_client, self.property_keys_data)
#         self.result_evaluator = ResultEvaluator(self.gpt_client)
#         self.strategy_selector = StrategySelector(self.gpt_client)
        
#         # Session storage
#         self.session_storage = {}
    
#     def search(self, question: str, session_id: str = None) -> Dict[str, Any]:
#         """
#         Main search method implementing the agentic React loop
        
#         Returns:
#             Dict containing the final answer and search metadata
#         """
        
#         # Initialize search state
#         state = SearchState(question, session_id)
#         self.session_storage[state.session_id] = state
        
#         print(f"Starting agentic search for: {question}")
#         print(f"Session ID: {state.session_id}")
        
#         while state.iteration_count < state.max_iterations:
#             print(f"\n--- Iteration {state.iteration_count + 1} ---")
            
#             # OBSERVE: Analyze current situation
#             observation = self._observe(state)
#             print(f"Observation: {observation}")
            
#             # THINK: Select strategy based on analysis
#             strategy, strategy_reasoning, context_updates = self._think(state)
#             print(f"Strategy: {strategy}")
#             print(f"Reasoning: {strategy_reasoning}")
            
#             # Update search context
#             state.search_context.update(context_updates)
            
#             # ACT: Generate and execute query
#             query, query_reasoning = self._act(state, strategy)
#             print(f"Generated Query: {query}")
#             print(f"Query Reasoning: {query_reasoning}")
            
#             # Execute query
#             results = self._execute_query(query)
#             print(f"Results: Found {len(results)} items")
            
#             # REFLECT: Evaluate results and decide next action
#             confidence, eval_reasoning, should_continue, suggested_answer = self._reflect(
#                 state, query, results
#             )
#             print(f"Confidence: {confidence:.2f}")
#             print(f"Evaluation: {eval_reasoning}")
            
#             # Record iteration
#             iteration_data = state.add_iteration(
#                 strategy, query, results, confidence, eval_reasoning
#             )
            
#             # Save iteration to temporary storage
#             self._save_iteration(state.session_id, iteration_data)
            
#             # Decision point
#             if not should_continue or confidence >= 0.8:
#                 state.final_answer = suggested_answer
#                 print(f"Search completed with answer: {suggested_answer}")
#                 break
            
#             print("Continuing search with new strategy...")
        
#         # Prepare final result
#         final_result = {
#             "session_id": state.session_id,
#             "question": question,
#             "final_answer": state.final_answer,
#             "confidence_score": state.confidence_score,
#             "total_iterations": state.iteration_count,
#             "search_successful": state.final_answer is not None,
#             "reasoning_chain": state.reasoning_chain,
#             "query_history": state.query_history
#         }
        
#         print(f"\nFinal Result: {final_result}")
#         return final_result
    
#     def _observe(self, state: SearchState) -> str:
#         """Observe current state and question characteristics"""
#         observations = []
        
#         if state.iteration_count == 0:
#             observations.append("Starting fresh search")
#         else:
#             observations.append(f"Previous attempts: {len(state.attempted_strategies)}")
            
#         if state.result_history:
#             total_results = sum(len(results) for results in state.result_history)
#             observations.append(f"Previous results found: {total_results}")
        
#         observations.append(f"Current confidence: {state.confidence_score:.2f}")
        
#         return "; ".join(observations)
    
#     def _think(self, state: SearchState) -> Tuple[str, str, Dict]:
#         """Think about the best strategy for current iteration"""
#         return self.strategy_selector.select_strategy(
#             state.question, 
#             state.attempted_strategies,
#             state.search_context
#         )
    
#     def _act(self, state: SearchState, strategy: str) -> Tuple[str, str]:
#         """Generate and return a Cypher query based on strategy"""
#         # Perform vector search first
#         vector_results = self.db_preparator.vector_search(state.question, top_k=10)
        
#         if vector_results:
#             print(f"   Vector search found {len(vector_results)} similar nodes")
#             # Get details for top results
#             top_node_ids = [result['node_id'] for result in vector_results[:3]]
#             node_details = self.db_preparator.get_node_details(top_node_ids)
            
#             # Add vector search context to state
#             state.search_context['vector_results'] = vector_results[:5]
#             state.search_context['relevant_nodes'] = node_details
        
#         return self.query_generator.generate_query(
#             state.question,
#             strategy,
#             state.search_context,
#             state.previous_attempts,
#             vector_results
#         )
    
#     def _execute_query(self, query: str) -> List[Dict]:
#         """Execute Cypher query against Neo4j database"""
#         try:
#             # Use the database specified in environment variables
#             database = os.getenv("NEO4J_DATABASE", "neo4j")
#             with self.driver.session(database=database) as session:
#                 result = session.run(query)
#                 return [record.data() for record in result]
#         except Exception as e:
#             print(f"Query execution error: {str(e)}")
#             return []
    
#     def _reflect(self, state: SearchState, query: str, results: List[Dict]) -> Tuple[float, str, bool, Optional[str]]:
#         """Reflect on results and decide whether to continue"""
#         confidence, reasoning, should_continue, suggested_answer, improvement_suggestions = self.result_evaluator.evaluate_results(
#             state.question,
#             query, 
#             results,
#             state.search_context
#         )
        
#         # Store improvement suggestions for next iteration
#         if improvement_suggestions and should_continue:
#             state.previous_attempts.append(f"Failed query: {query}\nReason: {reasoning}\nImprovement needed: {improvement_suggestions}")
        
#         return confidence, reasoning, should_continue, suggested_answer
    
#     def _save_iteration(self, session_id: str, iteration_data: Dict):
#         """Save iteration data to temporary JSON storage"""
#         storage_dir = "/tmp/agentic_search_sessions"
#         os.makedirs(storage_dir, exist_ok=True)
        
#         session_file = f"{storage_dir}/{session_id}.json"
        
#         # Load existing data or create new
#         if os.path.exists(session_file):
#             with open(session_file, 'r') as f:
#                 session_data = json.load(f)
#         else:
#             session_data = {"session_id": session_id, "iterations": []}
        
#         # Add new iteration
#         session_data["iterations"].append(iteration_data)
        
#         # Save back to file
#         with open(session_file, 'w') as f:
#             json.dump(session_data, f, indent=2)
    
#     def get_session_history(self, session_id: str) -> Optional[Dict]:
#         """Retrieve session history from storage"""
#         storage_dir = "/tmp/agentic_search_sessions"
#         session_file = f"{storage_dir}/{session_id}.json"
        
#         if os.path.exists(session_file):
#             with open(session_file, 'r') as f:
#                 return json.load(f)
#         return None
    
#     def close(self):
#         """Clean up resources"""
#         if self.driver:
#             self.driver.close()
#         if hasattr(self, 'db_preparator') and self.db_preparator:
#             self.db_preparator.close()


# if __name__ == "__main__":
#     # Example usage
#     engine = AgenticSearchEngine(
#         neo4j_uri="bolt://localhost:7687",
#         neo4j_user="neo4j", 
#         neo4j_password="password"
#     )
    
#     try:
#         result = engine.search("What events did John participate in?")
#         print("Search completed:", result)
#     finally:
#         engine.close() 

#!/usr/bin/env python3
"""
Agentic Search Engine for Knowledge Graph Question Answering

This module implements a React-style agentic search system that:
1. Observes the question and current state
2. Thinks about the best approach 
3. Acts by generating and executing Cypher queries dynamically
4. Reflects on results and decides whether to continue or output answer

No hardcoded queries - everything is generated dynamically based on analysis.
"""

import json
import uuid
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from openai import OpenAI
from neo4j import GraphDatabase

# Constants for date conversion
MONTH_CONVERSION_CASE = """CASE 
    WHEN e.date CONTAINS 'January' THEN '01'
    WHEN e.date CONTAINS 'February' THEN '02'
    WHEN e.date CONTAINS 'March' THEN '03'
    WHEN e.date CONTAINS 'April' THEN '04'
    WHEN e.date CONTAINS 'May' THEN '05'
    WHEN e.date CONTAINS 'June' THEN '06'
    WHEN e.date CONTAINS 'July' THEN '07'
    WHEN e.date CONTAINS 'August' THEN '08'
    WHEN e.date CONTAINS 'September' THEN '09'
    WHEN e.date CONTAINS 'October' THEN '10'
    WHEN e.date CONTAINS 'November' THEN '11'
    WHEN e.date CONTAINS 'December' THEN '12'
    ELSE '00'
END"""

DATE_CONVERSION_TEMPLATE = """WITH e, 
     {month_case} as month_num,
     split(e.date, ' ')[1] as day,
     split(e.date, ' ')[2] as year
WITH e{additional_fields}, year + '-' + month_num + '-' + 
     CASE WHEN size(day) = 3 THEN substring(day, 0, 2) ELSE day END as sort_date"""

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded environment variables from .env file")
except ImportError:
    print("⚠️ python-dotenv not installed, trying to load .env manually...")
    # Manual .env loading as fallback
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print("✅ Manually loaded environment variables from .env file")


class SearchState:
    """Maintains the current state of an agentic search session"""
    
    def __init__(self, question: str, session_id: str = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.question = question
        self.iteration_count = 0
        self.max_iterations = 5
        self.attempted_strategies = []
        self.query_history = []
        self.result_history = []
        self.final_answer = None
        self.reasoning_chain = []
        self.current_hypothesis = None
        self.search_context = {}
        self.previous_attempts = []
        
    def add_iteration(self, strategy: str, query: str, results: List[Dict], reasoning: str):
        """Add a new iteration to the search history"""
        iteration = {
            "iteration": self.iteration_count,
            "timestamp": datetime.now().isoformat(),
            "strategy": strategy,
            "query": query,
            "results": results,
            "reasoning": reasoning
        }
        
        self.attempted_strategies.append(strategy)
        self.query_history.append(query)
        self.result_history.append(results)
        self.reasoning_chain.append(reasoning)
        self.iteration_count += 1
        
        return iteration


class CypherQueryGenerator:
    """Dynamically generates Cypher queries based on analysis and context"""
    
    def __init__(self, gpt_client: OpenAI, property_keys_data: Dict = None):
        self.gpt_client = gpt_client
        self.property_keys_data = property_keys_data
    
    def _get_temporal_patterns(self) -> str:
        """Generate temporal query patterns using templates"""
        base_pattern = "MATCH (p:Person)-[:PARTICIPATED_IN]->(e:Event) WHERE p.name = 'Name' AND e.date <> ''"
        date_conv = DATE_CONVERSION_TEMPLATE.format(
            month_case=MONTH_CONVERSION_CASE, 
            additional_fields=""
        )
        date_conv_with_original = DATE_CONVERSION_TEMPLATE.format(
            month_case=MONTH_CONVERSION_CASE, 
            additional_fields=".date as original_date"
        )
        
        return f"""
1. Most recent location: 
{base_pattern}
{date_conv}
RETURN e.location ORDER BY sort_date DESC LIMIT 1

2. Chronological location list:
{base_pattern}
{date_conv}
ORDER BY sort_date ASC
WITH COLLECT(DISTINCT e.location) as locations
UNWIND locations as location
RETURN location

3. Chronological date list:
{base_pattern}
{date_conv_with_original}
ORDER BY sort_date ASC
WITH COLLECT(DISTINCT original_date) as unique_dates
UNWIND unique_dates as date
RETURN date"""
    
    def get_available_properties(self, node_label: str) -> List[str]:
        """Get available properties for a specific node label"""
        if not self.property_keys_data:
            return []
        
        property_keys = self.property_keys_data.get('property_keys', {})
        return property_keys.get(node_label, [])
    
    def get_all_labels(self) -> List[str]:
        """Get all available node labels"""
        if not self.property_keys_data:
            return ['Event', 'Person', 'Location']  # fallback
        
        property_keys = self.property_keys_data.get('property_keys', {})
        return [label for label in property_keys.keys() if label != '_relationships']
    
    def get_relationship_types(self) -> List[str]:
        """Get all available relationship types"""
        if not self.property_keys_data:
            return ['OCCURRED_AT', 'PARTICIPATED_IN']  # fallback
        
        property_keys = self.property_keys_data.get('property_keys', {})
        relationships = property_keys.get('_relationships', {})
        return list(relationships.keys())
    
    def _build_context_info(self, context: Dict) -> str:
        """Build context information string"""
        return f"Additional context: {json.dumps(context, indent=2)}" if context else ""
    
    def _build_vector_info(self, vector_search_results: List[Dict]) -> str:
        """Build vector search results string"""
        if not vector_search_results:
            return ""
        
        vector_info = "Vector search found these relevant nodes:\n"
        for i, result in enumerate(vector_search_results[:5]):
            vector_info += f"- Node {result['node_id']} (similarity: {result['similarity']:.3f})\n"
        return vector_info
    
    def _build_previous_info(self, previous_attempts: List[str]) -> str:
        """Build previous attempts learning string"""
        if not previous_attempts:
            return ""
        
        available_relationships = self.get_relationship_types()
        return f"""
LEARNING FROM PREVIOUS FAILURES:
{chr(10).join(previous_attempts)}

IMPORTANT: Analyze why previous queries failed and avoid the same mistakes:
- If a relationship type caused errors, use only verified relationships: {', '.join(available_relationships)}
- If queries returned 0 results, the schema might be wrong - try simpler patterns first
- If dates are duplicated, use DISTINCT properly in collection operations
"""
    
    def _build_property_info(self) -> str:
        """Build property information string"""
        available_labels = self.get_all_labels()
        property_info = "Available properties by node type:\n"
        for label in available_labels:
            props = self.get_available_properties(label)
            property_info += f"- {label}: {', '.join(props)}\n"
        return property_info
    
    def _is_temporal_query(self, question: str) -> bool:
        """Check if question is asking for chronological/temporal information"""
        temporal_keywords = ['chronological', 'chronologically', 'timeline', 'earliest', 'latest', 'recent', 'dates', 'order', 'sequence', 'first', 'last']
        return any(keyword in question.lower() for keyword in temporal_keywords)
    
    def _build_temporal_guidance(self) -> str:
        """Build temporal query guidance"""
        return f"""

SPECIAL GUIDANCE FOR CHRONOLOGICAL/TEMPORAL QUERIES:
- Event nodes have 'date' property in format "Month DD, YYYY" 
- Filter empty dates: WHERE e.date <> ''
- Use e.location property (NO LOCATED_AT relationship exists!)
- Manual date conversion required for proper sorting

COMMON TEMPORAL QUERY PATTERNS:
{self._get_temporal_patterns()}

IMPORTANT: Use COLLECT(DISTINCT ...) for list queries to remove duplicates.
"""
    
    def generate_query(self, question: str, strategy: str, context: Dict = None, 
                      previous_attempts: List[str] = None, vector_search_results: List[Dict] = None) -> Tuple[str, str]:
        """
        Generate a Cypher query dynamically based on question analysis
        
        Returns:
            Tuple[str, str]: (cypher_query, reasoning)
        """
        
        # Build all context information
        context_info = self._build_context_info(context)
        vector_info = self._build_vector_info(vector_search_results)
        previous_info = self._build_previous_info(previous_attempts)
        property_info = self._build_property_info()
        
        # Get schema information
        available_labels = self.get_all_labels()
        available_relationships = self.get_relationship_types()
        
        # Add temporal guidance if needed
        temporal_guidance = self._build_temporal_guidance() if self._is_temporal_query(question) else ""
        
        prompt = f"""
You are an expert in generating Cypher queries for Neo4j knowledge graphs. 
Your task is to create a precise Cypher query to answer the given question.

Question: {question}
Strategy: {strategy}
{context_info}
{previous_info}
{vector_info}

ACTUAL Knowledge Graph Schema (from database analysis):
- Available Node Labels: {', '.join(available_labels)}
- Available Relationships: {', '.join(available_relationships)}

{property_info}{temporal_guidance}

IMPORTANT: You MUST only use the node labels, relationships, and properties listed above. 
Do NOT use labels like 'Organization' or 'Topic' or relationships like 'RELATES_TO' if they are not in the available lists.

Generate a Cypher query that will help answer this question. Consider:
1. What entities are mentioned in the question?
2. What relationships are implied?
3. What information needs to be retrieved?
4. How to structure the query for optimal results?
5. Use only the available schema elements listed above
6. If this is a temporal/chronological query, pay special attention to the date property and sorting

Provide your response in this JSON format:
{{
    "cypher_query": "MATCH ... RETURN ...",
    "reasoning": "Explanation of why this query should work",
    "expected_results": "Description of what kind of results this should return"
}}

Make sure the query is syntactically correct and follows Neo4j Cypher syntax.
Use only the available node labels, relationships and properties shown above.
"""

        try:
            response = self.gpt_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            result = json.loads(response.choices[0].message.content)
            return result["cypher_query"], result["reasoning"]
            
        except Exception as e:
            # Fallback to a basic query structure
            basic_query = f"""
            MATCH (n)
            WHERE n.name CONTAINS '{question.split()[0] if question.split() else 'unknown'}'
            RETURN n.name, labels(n), properties(n)
            LIMIT 10
            """
            return basic_query, f"Fallback query due to error: {str(e)}"


class ResultEvaluator:
    """Evaluates query results and decides whether they answer the question"""
    
    def __init__(self, gpt_client: OpenAI):
        self.gpt_client = gpt_client
    
    def evaluate_results(self, question: str, query: str, results: List[Dict], 
                        iteration_context: Dict = None) -> Tuple[float, str, bool, Optional[str], Optional[str]]:
        """
        Evaluate whether the results adequately answer the question
        
        Returns:
            Tuple[float, str, bool, Optional[str], Optional[str]]: 
            (confidence_score, reasoning, should_continue, suggested_answer, improvement_suggestions)
        """
        
        if not results:
            return 0.0, "No results returned from query", True, None, "Check relationship types and schema - query might use non-existent relationships"
        
        # Prepare results for analysis
        results_summary = self._summarize_results(results)
        
        context_info = ""
        if iteration_context:
            context_info = f"Search context: {json.dumps(iteration_context, indent=2)}"
        
        prompt = f"""
You are evaluating whether query results adequately answer a question.

Question: {question}
Cypher Query Used: {query}
Results Summary: {results_summary}
{context_info}

Analyze the results and determine:
1. Do these results contain information that answers the question?
2. How confident are you that this is a complete/correct answer? (0-100%)
3. Should we continue searching or is this sufficient?
4. If sufficient, what is the final answer?

CRITICAL ERROR DETECTION:
- If query returned 0 results, analyze the query for common issues:
  * Wrong relationship types (e.g., using LOCATED_AT which doesn't exist)
  * Incorrect node labels or property names
  * Overly restrictive WHERE clauses
- If query had relationship warnings, suggest using actual relationship types
- If results seem incomplete, suggest alternative query approaches

Provide your evaluation in this JSON format:
{{
    "confidence_score": 85,
    "reasoning": "Detailed explanation of your evaluation",
    "should_continue": false,
    "suggested_answer": "The final answer based on the results",
    "improvement_suggestions": "If continuing, what should be tried next? Be specific about query fixes needed."
}}

Be thorough in your analysis. Consider completeness, relevance, and accuracy.
"""

        try:
            response = self.gpt_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            evaluation = json.loads(response.choices[0].message.content)
            
            confidence = evaluation.get("confidence_score", 0) / 100.0
            reasoning = evaluation.get("reasoning", "No reasoning provided")
            should_continue = evaluation.get("should_continue", True)
            suggested_answer = evaluation.get("suggested_answer")
            improvement_suggestions = evaluation.get("improvement_suggestions", "")
            
            return confidence, reasoning, should_continue, suggested_answer, improvement_suggestions
            
        except Exception as e:
            # Fallback evaluation
            if results and len(results) > 0:
                return 0.5, f"Basic evaluation - found {len(results)} results", True, None, ""
            else:
                return 0.0, f"Evaluation error: {str(e)}", True, None, "Evaluation error - try simpler query patterns"
    
    def _summarize_results(self, results: List[Dict]) -> str:
        """Create a concise summary of results for analysis"""
        if not results:
            return "No results"
        
        summary = f"Found {len(results)} results:\n"
        for i, result in enumerate(results[:5]):  # Limit to first 5 for summary
            summary += f"{i+1}. {json.dumps(result, indent=2)}\n"
        
        if len(results) > 5:
            summary += f"... and {len(results) - 5} more results"
        
        return summary


class StrategySelector:
    """Selects the best search strategy based on question analysis"""
    
    def __init__(self, gpt_client: OpenAI):
        self.gpt_client = gpt_client
    
    def select_strategy(self, question: str, previous_strategies: List[str] = None,
                       search_context: Dict = None) -> Tuple[str, str, Dict]:
        """
        Analyze question and determine the best search strategy
        
        Returns:
            Tuple[str, str, Dict]: (strategy_name, reasoning, context_updates)
        """
        
        previous_info = ""
        if previous_strategies:
            previous_info = f"Already tried strategies: {', '.join(previous_strategies)}"
        
        context_info = ""
        if search_context:
            context_info = f"Current context: {json.dumps(search_context, indent=2)}"
        
        prompt = f"""
Analyze this question and determine the best search strategy for a knowledge graph.

Question: {question}
{previous_info}
{context_info}

Available strategy types:
1. entity_focused - Find specific entities mentioned in the question
2. relationship_focused - Explore relationships between entities
3. temporal_focused - Search based on time/sequence constraints  
4. location_focused - Search based on location/place constraints
5. broad_exploration - Cast a wide net to find relevant information
6. constraint_refinement - Add specific constraints to narrow results
7. pattern_matching - Look for specific patterns or structures

Choose the most appropriate strategy and provide context updates.

Respond in this JSON format:
{{
    "strategy": "entity_focused",
    "reasoning": "Why this strategy is best for this question",
    "context_updates": {{
        "target_entities": ["entity1", "entity2"],
        "key_constraints": ["constraint1"],
        "search_focus": "what to focus on"
    }}
}}
"""

        try:
            response = self.gpt_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            result = json.loads(response.choices[0].message.content)
            
            strategy = result.get("strategy", "broad_exploration")
            reasoning = result.get("reasoning", "Default strategy selection")
            context_updates = result.get("context_updates", {})
            
            return strategy, reasoning, context_updates
            
        except Exception as e:
            # Fallback strategy selection
            if not previous_strategies:
                return "entity_focused", f"Fallback to entity_focused due to error: {str(e)}", {}
            else:
                # Try a different strategy if previous ones failed
                all_strategies = ["entity_focused", "relationship_focused", "temporal_focused", 
                                "location_focused", "broad_exploration", "constraint_refinement"]
                remaining = [s for s in all_strategies if s not in previous_strategies]
                if remaining:
                    return remaining[0], f"Trying alternative strategy due to error: {str(e)}", {}
                else:
                    return "broad_exploration", "All strategies attempted, using broad exploration", {}


class AgenticSearchEngine:
    """
    Main agentic search engine implementing React-style search loop:
    Observe -> Think -> Act -> Reflect
    """
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str, 
                 openai_api_key: str = None, neo4j_database: str = None):
        # Store database connection info
        self.neo4j_database = neo4j_database or os.getenv("NEO4J_DATABASE", "neo4j")
        
        # Initialize connections
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
        # Initialize OpenAI client with explicit HTTP client to avoid proxies issue
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", None)
        
        if not api_key:
            raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY environment variable.")
        
        # Create HTTP client without proxy settings
        import httpx
        http_client = httpx.Client()
        
        # Initialize with explicit HTTP client
        client_kwargs = {
            "api_key": api_key,
            "http_client": http_client
        }
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self.gpt_client = OpenAI(**client_kwargs)
        
        # Initialize database preparator
        import sys
        # Add the graph_generation directory to the path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        graph_generation_dir = os.path.join(os.path.dirname(current_dir), 'graph_generation')
        if graph_generation_dir not in sys.path:
            sys.path.insert(0, graph_generation_dir)
        
        from database_preparation import DatabasePreparator
        self.db_preparator = DatabasePreparator(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            neo4j_database=self.neo4j_database,
            openai_api_key=openai_api_key
        )
        
        # Prepare database (load embeddings and property keys)
        self.preparation_result = self.db_preparator.prepare_database()
        self.property_keys_data = self.db_preparator.load_property_keys()
        
        # Initialize components with property key data
        self.query_generator = CypherQueryGenerator(self.gpt_client, self.property_keys_data)
        self.result_evaluator = ResultEvaluator(self.gpt_client)
        self.strategy_selector = StrategySelector(self.gpt_client)
        
        # Session storage
        self.session_storage = {}
    
    def search(self, question: str, session_id: str = None) -> Dict[str, Any]:
        """
        Main search method implementing the agentic React loop
        
        Returns:
            Dict containing the final answer and search metadata
        """
        
        # Initialize search state
        state = SearchState(question, session_id)
        self.session_storage[state.session_id] = state
        
        print(f"Starting agentic search for: {question}")
        print(f"Session ID: {state.session_id}")
        
        while state.iteration_count < state.max_iterations:
            print(f"\n--- Iteration {state.iteration_count + 1} ---")
            
            # OBSERVE: Analyze current situation
            observation = self._observe(state)
            print(f"Observation: {observation}")
            
            # THINK: Select strategy based on analysis
            strategy, strategy_reasoning, context_updates = self._think(state)
            print(f"Strategy: {strategy}")
            print(f"Reasoning: {strategy_reasoning}")
            
            # Update search context
            state.search_context.update(context_updates)
            
            # ACT: Generate and execute query
            query, query_reasoning = self._act(state, strategy)
            print(f"Generated Query: {query}")
            print(f"Query Reasoning: {query_reasoning}")
            
            # Execute query
            results = self._execute_query(query)
            print(f"Results: Found {len(results)} items")
            
            # REFLECT: Evaluate results (ignore confidence/should_continue; decide based on results emptiness)
            _, eval_reasoning, _, suggested_answer = self._reflect(
                state, query, results
            )
            print(f"Evaluation: {eval_reasoning}")
            
            # Record iteration (no confidence stored)
            iteration_data = state.add_iteration(
                strategy, query, results, eval_reasoning
            )
            
            # Save iteration to temporary storage
            self._save_iteration(state.session_id, iteration_data)
            
            # Decision point: continue only if results are empty
            should_continue = (len(results) == 0)
            if not should_continue:
                state.final_answer = suggested_answer
                print(f"Search completed with answer: {suggested_answer}")
                break
            
            print("Continuing search with new strategy...")
        
        # Format the answer for standardized output
        formatted_answer = self._format_standardized_answer(state.final_answer, question)
        
        # Prepare final result
        final_result = {
            "session_id": state.session_id,
            "question": question,
            "final_answer": state.final_answer,  # Keep original answer for debugging
            "standardized_answer": formatted_answer,  # New standardized format
            "total_iterations": state.iteration_count,
            "search_successful": state.final_answer is not None,
            "reasoning_chain": state.reasoning_chain,
            "query_history": state.query_history
        }
        
        print(f"\nFinal Result: {final_result}")
        return final_result
    
    def _observe(self, state: SearchState) -> str:
        """Observe current state and question characteristics"""
        observations = []
        
        if state.iteration_count == 0:
            observations.append("Starting fresh search")
        else:
            observations.append(f"Previous attempts: {len(state.attempted_strategies)}")
            
        if state.result_history:
            total_results = sum(len(results) for results in state.result_history)
            observations.append(f"Previous results found: {total_results}")
        
        return "; ".join(observations)
    
    def _think(self, state: SearchState) -> Tuple[str, str, Dict]:
        """Think about the best strategy for current iteration"""
        return self.strategy_selector.select_strategy(
            state.question, 
            state.attempted_strategies,
            state.search_context
        )
    
    def _act(self, state: SearchState, strategy: str) -> Tuple[str, str]:
        """Generate and return a Cypher query based on strategy"""
        # Perform vector search first
        vector_results = self.db_preparator.vector_search(state.question, top_k=10)
        
        if vector_results:
            print(f"   Vector search found {len(vector_results)} similar nodes")
            # Get details for top results
            top_node_ids = [result['node_id'] for result in vector_results[:3]]
            node_details = self.db_preparator.get_node_details(top_node_ids)
            
            # Add vector search context to state
            state.search_context['vector_results'] = vector_results[:5]
            state.search_context['relevant_nodes'] = node_details
        
        return self.query_generator.generate_query(
            state.question,
            strategy,
            state.search_context,
            state.previous_attempts,
            vector_results
        )
    
    def _execute_query(self, query: str) -> List[Dict]:
        """Execute Cypher query against Neo4j database"""
        try:
            # Use the database specified in environment variables
            database = os.getenv("NEO4J_DATABASE", "neo4j")
            with self.driver.session(database=database) as session:
                result = session.run(query)
                return [record.data() for record in result]
        except Exception as e:
            print(f"Query execution error: {str(e)}")
            return []
    
    def _reflect(self, state: SearchState, query: str, results: List[Dict]) -> Tuple[float, str, bool, Optional[str]]:
        """Reflect on results and decide whether to continue"""
        confidence, reasoning, should_continue, suggested_answer, improvement_suggestions = self.result_evaluator.evaluate_results(
            state.question,
            query, 
            results,
            state.search_context
        )
        
        # Store improvement suggestions for next iteration
        if improvement_suggestions and should_continue:
            state.previous_attempts.append(f"Failed query: {query}\nReason: {reasoning}\nImprovement needed: {improvement_suggestions}")
        
        return confidence, reasoning, should_continue, suggested_answer
    
    def _save_iteration(self, session_id: str, iteration_data: Dict):
        """Save iteration data to temporary JSON storage"""
        storage_dir = "/tmp/agentic_search_sessions"
        os.makedirs(storage_dir, exist_ok=True)
        
        session_file = f"{storage_dir}/{session_id}.json"
        
        # Load existing data or create new
        if os.path.exists(session_file):
            with open(session_file, 'r') as f:
                session_data = json.load(f)
        else:
            session_data = {"session_id": session_id, "iterations": []}
        
        # Add new iteration
        session_data["iterations"].append(iteration_data)
        
        # Save back to file
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
    
    def get_session_history(self, session_id: str) -> Optional[Dict]:
        """Retrieve session history from storage"""
        storage_dir = "/tmp/agentic_search_sessions"
        session_file = f"{storage_dir}/{session_id}.json"
        
        if os.path.exists(session_file):
            with open(session_file, 'r') as f:
                return json.load(f)
        return None
    
    def _format_standardized_answer(self, final_answer: Optional[str], question: str) -> List[str]:
        """
        Format the final answer into standardized list format for evaluation.
        
        Args:
            final_answer: The original answer from the search engine (may be str or list)
            question: The original question for context
            
        Returns:
            List[str]: Standardized answer format - list of answers or empty list if no answer
        """
        # --- robust typing: accept list or string, avoid .lower on list ---
        if final_answer is None:
            return []

        if isinstance(final_answer, list):
            cleaned_list = [str(x).strip() for x in final_answer if str(x).strip()]
            return cleaned_list

        if not isinstance(final_answer, str):
            final_answer = str(final_answer)

        text = final_answer.strip()
        if not text or text.lower() in ['none', 'no answer', 'no results found']:
            return []
        
        # Use GPT to extract the core answer from the descriptive text
        prompt = f"""
You are a precise answer extractor. Given a question and a detailed answer, extract ONLY the core factual answer(s) in the simplest possible format.

Question: {question}
Detailed Answer: {text}

Rules:
1. If the answer contains dates, extract them in the exact format they appear (e.g., "September 03, 2026")
2. If the answer contains locations, extract just the location names
3. If the answer contains names, extract just the names
4. If the answer contains a list of items, return each item separately
5. If there are multiple answers, return all of them
6. If there is genuinely no answer or the answer is "None", return an empty list
7. Return ONLY the factual content, no explanatory text
8. Preserve the exact formatting of dates, names, and locations as they appear

Examples:
- "The most recent date is September 03, 2026" → ["September 03, 2026"]
- "The locations are Grand Hall, Lincoln Center" → ["Grand Hall", "Lincoln Center"]
- "No events found" → []
- "The person is John Smith and the date is May 15, 2024" → ["John Smith", "May 15, 2024"]

Return your answer as a JSON list of strings:
"""

        try:
            response = self.gpt_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1  # Very low temperature for consistent extraction
            )
            
            content = response.choices[0].message.content.strip()
            
            # Try to parse as JSON
            import re
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                try:
                    extracted_answers = json.loads(json_match.group())
                    if isinstance(extracted_answers, list):
                        # Filter out empty strings and ensure all items are strings
                        return [str(item).strip() for item in extracted_answers if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            
            # Fallback: if JSON parsing fails, try simple extraction
            # Look for common patterns
            if "no" in text.lower() and any(word in text.lower() for word in ["found", "results", "answer", "events"]):
                return []
            
            # Simple fallback extraction for dates
            date_pattern = r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
            import re as _re
            dates = _re.findall(date_pattern, text)
            if dates:
                return dates
            
            # If all else fails, return the cleaned original answer
            cleaned = text
            if cleaned and not any(word in cleaned.lower() for word in ["no answer", "none", "not found"]):
                return [cleaned]
            
            return []
            
        except Exception as e:
            print(f"Warning: Answer formatting failed: {e}")
            # Fallback to simple cleanup
            if text and text.strip():
                return [text.strip()]
            return []
    
    def close(self):
        """Clean up resources"""
        if self.driver:
            self.driver.close()
        if hasattr(self, 'db_preparator') and self.db_preparator:
            self.db_preparator.close()


if __name__ == "__main__":
    # Example usage
    engine = AgenticSearchEngine(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j", 
        neo4j_password="password"
    )
    
    try:
        result = engine.search("What events did John participate in?")
        print("Search completed:", result)
    finally:
        engine.close()
