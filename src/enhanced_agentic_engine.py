#!/usr/bin/env python3
"""
Enhanced Agentic Search Engine

Integrates all improvements:
1. Structured DSL → Cypher compilation with schema validation
2. Enhanced entity linking with vector search + cross-verification  
3. Multi-candidate query generation with comprehensive scoring
4. Constraint extraction and structured query planning

This prevents schema hallucination and improves query reliability through
systematic validation and multi-candidate consensus.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from openai import OpenAI
from neo4j import GraphDatabase
from dataclasses import dataclass, field

# Import our new components
from query_dsl import QueryDSL, EntitySpec, RelationSpec, FilterSpec, TemporalSpec, AggregationSpec
from dsl_compiler import DSLCompiler, SchemaWhitelist, ValidationResult
from entity_linker import QueryIntentAnalyzer, EntityLink, ConstraintExtraction
from multi_candidate_scorer import MultiCandidateQuerySystem, CandidateScore

# Import existing components
from database_preparation import DatabasePreparator

@dataclass
class EnhancedSearchState:
    """Enhanced search state with DSL and multi-candidate support"""
    session_id: str
    question: str
    
    # Query planning state
    query_intent: Optional[Any] = None  # QueryIntent from entity linking
    candidate_scores: List[CandidateScore] = None
    best_candidate: Optional[CandidateScore] = None
    
    # Traditional state
    iteration_count: int = 0
    max_iterations: int = 3
    final_answer: Optional[str] = None
    confidence_score: float = 0.0
    
    # Tracking
    reasoning_chain: List[str] = field(default_factory=list)
    query_history: List[str] = field(default_factory=list)
    search_context: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.candidate_scores is None:
            self.candidate_scores = []

class EnhancedDSLQueryGenerator:
    """Enhanced query generator that produces structured DSL instead of raw Cypher"""
    
    def __init__(self, gpt_client: OpenAI, schema_whitelist: SchemaWhitelist, 
                 intent_analyzer: QueryIntentAnalyzer):
        self.gpt_client = gpt_client
        self.schema = schema_whitelist
        self.intent_analyzer = intent_analyzer
    
    def generate_dsl_from_intent(self, question: str, query_intent) -> QueryDSL:
        """Generate QueryDSL from structured query intent"""
        
        # Convert entity links to EntitySpec
        entities = []
        for link in query_intent.entities:
            entities.append(EntitySpec(
                alias=link.alias,
                label=link.label,
                link=link.properties,
                confidence=link.confidence
            ))
        
        # Convert constraints to FilterSpec
        filters = []
        for constraint in query_intent.constraints:
            from query_dsl import FilterOperator
            filters.append(FilterSpec(
                on=constraint.field,
                operator=FilterOperator(constraint.operator),
                value=constraint.value
            ))
        
        # Add default relationship if entities exist
        relations = []
        if len(entities) >= 2:
            # Default to PARTICIPATED_IN for Person -> Event
            person_entity = next((e for e in entities if e.label == "Person"), None)
            event_entity = next((e for e in entities if e.label == "Event"), None)
            
            if person_entity and event_entity:
                relations.append(RelationSpec(
                    from_alias=person_entity.alias,
                    type="PARTICIPATED_IN",
                    to_alias=event_entity.alias
                ))
        
        # Handle temporal intent
        temporal = None
        if query_intent.temporal_intent:
            temporal_data = query_intent.temporal_intent
            if temporal_data.get("requires_ordering"):
                from query_dsl import TemporalOrder
                temporal = TemporalSpec(
                    order=TemporalOrder(temporal_data.get("direction", "desc")),
                    field=temporal_data.get("field", "e.date"),
                    normalize="Month DD, YYYY"
                )
        
        # Handle aggregation intent
        aggregations = []
        if query_intent.aggregation_intent:
            agg_data = query_intent.aggregation_intent
            aggregations.append(AggregationSpec(
                function=agg_data.get("type", "collect"),
                field=agg_data.get("field"),
                distinct=agg_data.get("distinct", False)
            ))
        
        # Handle output intent
        select_fields = []
        limit = None
        if query_intent.output_intent:
            output_data = query_intent.output_intent
            select_fields = output_data.get("fields", [])
            limit = output_data.get("limit")
        
        # Create DSL
        dsl = QueryDSL(
            entities=entities,
            relations=relations,
            filters=filters,
            temporal=temporal,
            aggregations=aggregations,
            select=select_fields,
            limit=limit,
            intent=f"Generated from query intent for: {question}",
            confidence=query_intent.confidence
        )
        
        return dsl

class EnhancedAgenticSearchEngine:
    """
    Enhanced Agentic Search Engine with DSL compilation and multi-candidate scoring
    
    Key improvements:
    1. Natural language → structured DSL → validated Cypher
    2. Entity linking with vector search + LLM cross-verification
    3. Multi-candidate generation with comprehensive scoring
    4. Schema validation prevents hallucination
    """
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str, 
                 openai_api_key: str = None, openai_base_url: str = None):
        
        # Database connection
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
        # OpenAI client
        if not openai_api_key:
            openai_api_key = os.getenv("OPENAI_API_KEY")
        
        client_kwargs = {"api_key": openai_api_key}
        if openai_base_url:
            client_kwargs["base_url"] = openai_base_url
        
        self.gpt_client = OpenAI(**client_kwargs)
        
        # Initialize components
        self.db_preparator = DatabasePreparator(self.driver)
        
        # Load schema whitelist
        property_keys_data = self.db_preparator.get_property_keys()
        self.schema_whitelist = SchemaWhitelist.from_property_keys_data(property_keys_data)
        
        # Initialize enhanced components
        self.intent_analyzer = QueryIntentAnalyzer(
            self.gpt_client, self.db_preparator, self.schema_whitelist
        )
        
        self.dsl_compiler = DSLCompiler(self.schema_whitelist)
        
        self.multi_candidate_system = MultiCandidateQuerySystem(
            self.gpt_client, self.driver, self.schema_whitelist
        )
        
        self.enhanced_dsl_generator = EnhancedDSLQueryGenerator(
            self.gpt_client, self.schema_whitelist, self.intent_analyzer
        )
        
        print("🚀 Enhanced Agentic Search Engine initialized")
        print(f"📊 Schema loaded: {len(self.schema_whitelist.labels)} labels, {len(self.schema_whitelist.relationships)} relationships")
    
    def search(self, question: str, use_multi_candidate: bool = True, 
               num_candidates: int = 3) -> Dict[str, Any]:
        """
        Enhanced search with structured DSL compilation and multi-candidate scoring
        
        Args:
            question: Natural language question
            use_multi_candidate: Whether to use multi-candidate approach
            num_candidates: Number of candidate queries to generate
        """
        
        state = EnhancedSearchState(
            session_id=str(uuid.uuid4()),
            question=question
        )
        
        print(f"🔍 Enhanced Agentic Search: {question}")
        print(f"📋 Session ID: {state.session_id}")
        
        try:
            # Step 1: Analyze query intent (entity linking + constraint extraction)
            print("\n🧠 Phase 1: Query Intent Analysis")
            state.query_intent = self.intent_analyzer.analyze_query_intent(question)
            
            print(f"   ✓ Entities found: {len(state.query_intent.entities)}")
            print(f"   ✓ Constraints extracted: {len(state.query_intent.constraints)}")
            print(f"   ✓ Intent confidence: {state.query_intent.confidence:.3f}")
            
            if use_multi_candidate and state.query_intent.confidence > 0.5:
                # Step 2: Multi-candidate approach
                print(f"\n🎯 Phase 2: Multi-Candidate Query Generation ({num_candidates} variants)")
                
                state.candidate_scores = self.multi_candidate_system.generate_and_score_candidates(
                    question,
                    state.query_intent.entities,
                    state.query_intent.constraints,
                    num_candidates
                )
                
                if state.candidate_scores:
                    state.best_candidate = state.candidate_scores[0]
                    print(f"   🏆 Best candidate score: {state.best_candidate.total_score:.3f}")
                    
                    # Extract answer from best candidate
                    if state.best_candidate.execution_result.results:
                        state.final_answer = self._extract_answer_from_results(
                            state.best_candidate.execution_result.results,
                            question
                        )
                        state.confidence_score = state.best_candidate.total_score
                        
                        print(f"   ✅ Answer: {state.final_answer}")
            
            if not state.final_answer:
                # Step 3: Fallback to traditional single-query approach
                print("\n🔄 Phase 3: Fallback to Single Query Generation")
                
                # Generate DSL from intent
                dsl = self.enhanced_dsl_generator.generate_dsl_from_intent(
                    question, state.query_intent
                )
                
                # Compile to Cypher
                cypher, validation = self.dsl_compiler.compile(dsl)
                
                if validation.is_valid:
                    print(f"   ✓ Generated valid Cypher query")
                    print(f"   Query: {cypher[:100]}...")
                    
                    # Execute query
                    results = self._execute_query(cypher)
                    
                    if results:
                        state.final_answer = self._extract_answer_from_results(results, question)
                        state.confidence_score = 0.7  # Medium confidence for single query
                        print(f"   ✅ Answer: {state.final_answer}")
                    
                else:
                    print(f"   ❌ Query validation failed: {validation.errors}")
            
        except Exception as e:
            print(f"❌ Search failed: {str(e)}")
            state.final_answer = None
            state.confidence_score = 0.0
        
        # Prepare final result
        final_result = {
            "session_id": state.session_id,
            "question": question,
            "final_answer": state.final_answer,
            "confidence_score": state.confidence_score,
            "search_successful": state.final_answer is not None,
            
            # Enhanced fields
            "query_intent": {
                "entities_found": len(state.query_intent.entities) if state.query_intent else 0,
                "constraints_extracted": len(state.query_intent.constraints) if state.query_intent else 0,
                "intent_confidence": state.query_intent.confidence if state.query_intent else 0.0
            },
            
            "multi_candidate_results": {
                "candidates_generated": len(state.candidate_scores),
                "best_score": state.best_candidate.total_score if state.best_candidate else 0.0,
                "scoring_breakdown": state.best_candidate.score_breakdown if state.best_candidate else None
            } if use_multi_candidate else None,
            
            "schema_validation": {
                "labels_available": list(self.schema_whitelist.labels),
                "relationships_available": list(self.schema_whitelist.relationships)
            }
        }
        
        print(f"\n📊 Final Result:")
        print(f"   Answer: {final_result['final_answer']}")
        print(f"   Confidence: {final_result['confidence_score']:.3f}")
        print(f"   Success: {final_result['search_successful']}")
        
        return final_result
    
    def _execute_query(self, query: str) -> List[Dict]:
        """Execute Cypher query against Neo4j database"""
        try:
            database = os.getenv("NEO4J_DATABASE", "neo4j")
            with self.driver.session(database=database) as session:
                result = session.run(query)
                return [record.data() for record in result]
        except Exception as e:
            print(f"Query execution error: {str(e)}")
            return []
    
    def _extract_answer_from_results(self, results: List[Dict], question: str) -> Optional[str]:
        """Extract natural language answer from query results"""
        
        if not results:
            return None
        
        # For single result queries (like "most recent location")
        if len(results) == 1:
            result = results[0]
            
            # Try to find the most relevant field
            for key, value in result.items():
                if value is not None and value != "":
                    return str(value)
        
        # For multiple results
        elif len(results) > 1:
            # If asking for a list, return formatted list
            if any(word in question.lower() for word in ["list", "all", "what", "which"]):
                values = []
                for result in results:
                    for key, value in result.items():
                        if value is not None and value != "":
                            values.append(str(value))
                
                if values:
                    return ", ".join(values[:10])  # Limit to first 10
        
        # Fallback: return first non-empty value
        for result in results:
            for key, value in result.items():
                if value is not None and value != "":
                    return str(value)
        
        return None
    
    def get_detailed_analysis(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed analysis for a completed search session"""
        # This would retrieve detailed analysis from session storage
        # Implementation depends on how you want to store session data
        pass
    
    def close(self):
        """Close database connections"""
        if self.driver:
            self.driver.close()

# Convenience function for quick testing
def quick_enhanced_search(question: str) -> Dict[str, Any]:
    """Quick search function for testing"""
    
    # Load configuration from environment
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    
    engine = EnhancedAgenticSearchEngine(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        result = engine.search(question)
        return result
    finally:
        engine.close()

if __name__ == "__main__":
    # Test the enhanced engine
    test_questions = [
        "What was Lucy Carter's most recent location?",
        "List all locations where John Smith has been chronologically",
        "When did the last event occur?"
    ]
    
    print("🧪 Testing Enhanced Agentic Search Engine")
    print("=" * 60)
    
    for question in test_questions:
        print(f"\n📝 Question: {question}")
        try:
            result = quick_enhanced_search(question)
            print(f"✅ Answer: {result.get('final_answer', 'No answer')}")
            print(f"📊 Confidence: {result.get('confidence_score', 0):.3f}")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        print("-" * 40) 