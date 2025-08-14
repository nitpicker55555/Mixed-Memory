#!/usr/bin/env python3
"""
Multi-Candidate Query Generation and Executable Scoring System

Implements self-consistency for queries by generating multiple candidate queries
and scoring them based on structural matching, result quality, and semantic consistency.
"""

from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass
import json
import statistics
from openai import OpenAI
from query_dsl import QueryDSL
from dsl_compiler import DSLCompiler, ValidationResult

@dataclass
class QueryCandidate:
    """A candidate query with its DSL and compiled Cypher"""
    dsl: QueryDSL
    cypher: str
    validation: ValidationResult
    generation_params: Dict[str, Any]  # temperature, seed, etc.

@dataclass
class ExecutionResult:
    """Result of executing a query candidate"""
    candidate: QueryCandidate
    results: List[Dict[str, Any]]
    execution_time: float
    error: Optional[str] = None

@dataclass
class CandidateScore:
    """Comprehensive score for a query candidate"""
    candidate: QueryCandidate
    execution_result: ExecutionResult
    
    # Individual scoring components
    structural_score: float = 0.0
    result_quality_score: float = 0.0
    semantic_consistency_score: float = 0.0
    
    # Combined score
    total_score: float = 0.0
    
    # Detailed breakdown
    score_breakdown: Dict[str, Any] = None

class QueryVariantGenerator:
    """Generates multiple query variants using different sampling parameters"""
    
    def __init__(self, gpt_client: OpenAI, schema_whitelist):
        self.gpt_client = gpt_client
        self.schema = schema_whitelist
    
    def generate_dsl_variants(self, question: str, entity_links: List, constraints: List,
                             num_variants: int = 5) -> List[QueryCandidate]:
        """Generate multiple DSL variants using different sampling parameters"""
        
        variants = []
        generation_configs = [
            {"temperature": 0.1, "seed": 42},
            {"temperature": 0.3, "seed": 123},
            {"temperature": 0.5, "seed": 456},
            {"temperature": 0.7, "seed": 789},
            {"temperature": 0.2, "seed": 999}
        ]
        
        for i, config in enumerate(generation_configs[:num_variants]):
            try:
                dsl = self._generate_single_dsl_variant(
                    question, entity_links, constraints, config
                )
                
                if dsl:
                    # Compile to Cypher for validation
                    compiler = DSLCompiler(self.schema)
                    cypher, validation = compiler.compile(dsl)
                    
                    variants.append(QueryCandidate(
                        dsl=dsl,
                        cypher=cypher,
                        validation=validation,
                        generation_params=config
                    ))
                    
            except Exception as e:
                print(f"Failed to generate variant {i}: {e}")
        
        return variants
    
    def _generate_single_dsl_variant(self, question: str, entity_links: List, 
                                   constraints: List, config: Dict) -> Optional[QueryDSL]:
        """Generate a single DSL variant with specific sampling parameters"""
        
        # Build context for DSL generation
        entity_context = [
            {"alias": link.alias, "label": link.label, "properties": link.properties}
            for link in entity_links
        ]
        
        constraint_context = [
            {"field": c.field, "operator": c.operator, "value": c.value}
            for c in constraints
        ]
        
        prompt = f"""
Generate a QueryDSL JSON for this question using the provided entities and constraints.

Question: {question}
Entities: {json.dumps(entity_context, indent=2)}
Constraints: {json.dumps(constraint_context, indent=2)}

Available schema:
- Labels: {list(self.schema.labels)}
- Relationships: {list(self.schema.relationships)}
- Properties: {dict(self.schema.properties)}

Generate a complete QueryDSL JSON that captures the query intent. Include:
- entities (with alias, label, link properties)
- relations (with from, type, to, direction)
- filters (with on, op, value)
- temporal specification if needed
- aggregations if needed
- select fields
- limit if appropriate

Focus on accuracy and completeness. Return only the JSON object.
"""
        
        try:
            response = self.gpt_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=config["temperature"],
                seed=config.get("seed")
            )
            
            dsl_dict = json.loads(response.choices[0].message.content)
            return QueryDSL.from_dict(dsl_dict)
            
        except Exception as e:
            print(f"DSL generation failed: {e}")
            return None

class QueryExecutor:
    """Executes query candidates and collects results"""
    
    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver
    
    def execute_candidates(self, candidates: List[QueryCandidate], 
                          database: str = "neo4j") -> List[ExecutionResult]:
        """Execute all valid query candidates"""
        
        execution_results = []
        
        for candidate in candidates:
            if not candidate.validation.is_valid:
                # Skip invalid candidates
                execution_results.append(ExecutionResult(
                    candidate=candidate,
                    results=[],
                    execution_time=0.0,
                    error=f"Invalid query: {candidate.validation.errors}"
                ))
                continue
            
            # Execute the query
            result = self._execute_single_query(candidate.cypher, database)
            execution_results.append(ExecutionResult(
                candidate=candidate,
                results=result["results"],
                execution_time=result["execution_time"],
                error=result.get("error")
            ))
        
        return execution_results
    
    def _execute_single_query(self, cypher: str, database: str) -> Dict[str, Any]:
        """Execute a single Cypher query and measure performance"""
        import time
        
        start_time = time.time()
        
        try:
            with self.driver.session(database=database) as session:
                result = session.run(cypher)
                records = [record.data() for record in result]
                
                execution_time = time.time() - start_time
                return {
                    "results": records,
                    "execution_time": execution_time
                }
                
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "results": [],
                "execution_time": execution_time,
                "error": str(e)
            }

class ComprehensiveScorer:
    """Scores query candidates based on multiple criteria"""
    
    def __init__(self, gpt_client: OpenAI, schema_whitelist):
        self.gpt_client = gpt_client
        self.schema = schema_whitelist
        
        # Scoring weights
        self.structural_weight = 0.3
        self.result_quality_weight = 0.4
        self.semantic_consistency_weight = 0.3
    
    def score_candidates(self, question: str, execution_results: List[ExecutionResult]) -> List[CandidateScore]:
        """Score all candidates comprehensively"""
        
        scored_candidates = []
        
        for exec_result in execution_results:
            # Calculate individual scores
            structural_score = self._calculate_structural_score(exec_result)
            result_quality_score = self._calculate_result_quality_score(exec_result)
            semantic_score = self._calculate_semantic_consistency_score(question, exec_result)
            
            # Calculate weighted total score
            total_score = (
                structural_score * self.structural_weight +
                result_quality_score * self.result_quality_weight +
                semantic_score * self.semantic_consistency_weight
            )
            
            # Create detailed breakdown
            breakdown = {
                "structural_details": self._get_structural_details(exec_result),
                "quality_details": self._get_quality_details(exec_result),
                "semantic_details": self._get_semantic_details(question, exec_result),
                "weights": {
                    "structural": self.structural_weight,
                    "quality": self.result_quality_weight,
                    "semantic": self.semantic_consistency_weight
                }
            }
            
            scored_candidates.append(CandidateScore(
                candidate=exec_result.candidate,
                execution_result=exec_result,
                structural_score=structural_score,
                result_quality_score=result_quality_score,
                semantic_consistency_score=semantic_score,
                total_score=total_score,
                score_breakdown=breakdown
            ))
        
        # Sort by total score (descending)
        return sorted(scored_candidates, key=lambda x: x.total_score, reverse=True)
    
    def _calculate_structural_score(self, exec_result: ExecutionResult) -> float:
        """Score based on structural matching of query components"""
        
        if exec_result.error:
            return 0.0
        
        score = 0.0
        max_score = 0.0
        
        candidate = exec_result.candidate
        dsl = candidate.dsl
        
        # Check entity matching (25% of structural score)
        if dsl.entities:
            entity_score = 0.0
            for entity in dsl.entities:
                if entity.label in self.schema.labels:
                    entity_score += 1.0
                if entity.link:
                    # Check if linked properties exist in schema
                    label_props = self.schema.properties.get(entity.label, set())
                    for prop in entity.link.keys():
                        if prop in label_props:
                            entity_score += 0.5
            
            entity_score = min(entity_score / len(dsl.entities), 1.0)
            score += entity_score * 0.25
        max_score += 0.25
        
        # Check relationship matching (25% of structural score)
        if dsl.relations:
            rel_score = sum(1.0 for rel in dsl.relations if rel.type in self.schema.relationships)
            rel_score = min(rel_score / len(dsl.relations), 1.0)
            score += rel_score * 0.25
        max_score += 0.25
        
        # Check query validity (25% of structural score)
        if candidate.validation.is_valid:
            score += 0.25
        max_score += 0.25
        
        # Check execution success (25% of structural score)
        if not exec_result.error:
            score += 0.25
        max_score += 0.25
        
        return score / max_score if max_score > 0 else 0.0
    
    def _calculate_result_quality_score(self, exec_result: ExecutionResult) -> float:
        """Score based on result quality metrics"""
        
        if exec_result.error or not exec_result.results:
            return 0.0
        
        results = exec_result.results
        score = 0.0
        max_score = 0.0
        
        # Result count reasonableness (20% of quality score)
        result_count = len(results)
        if 1 <= result_count <= 100:  # Reasonable range
            count_score = 1.0
        elif result_count == 0:
            count_score = 0.0
        else:
            count_score = max(0.0, 1.0 - (result_count - 100) / 1000)  # Penalty for too many results
        
        score += count_score * 0.2
        max_score += 0.2
        
        # Non-empty key coverage (20% of quality score)
        if results:
            total_keys = sum(len(record.keys()) for record in results)
            non_empty_values = sum(
                1 for record in results 
                for value in record.values() 
                if value is not None and value != ""
            )
            
            coverage_score = non_empty_values / total_keys if total_keys > 0 else 0.0
            score += coverage_score * 0.2
        max_score += 0.2
        
        # Duplicate handling (20% of quality score)
        unique_results = len(set(json.dumps(record, sort_keys=True) for record in results))
        duplicate_score = unique_results / len(results) if results else 0.0
        score += duplicate_score * 0.2
        max_score += 0.2
        
        # Temporal consistency (20% of quality score - if temporal query)
        dsl = exec_result.candidate.dsl
        if dsl.temporal and results:
            temporal_score = self._check_temporal_consistency(results, dsl.temporal)
            score += temporal_score * 0.2
        else:
            score += 0.2  # No temporal requirements
        max_score += 0.2
        
        # Performance score (20% of quality score)
        exec_time = exec_result.execution_time
        if exec_time < 1.0:  # Under 1 second is good
            perf_score = 1.0
        elif exec_time < 5.0:  # Under 5 seconds is acceptable
            perf_score = 0.7
        else:
            perf_score = 0.3  # Slow queries get low score
        
        score += perf_score * 0.2
        max_score += 0.2
        
        return score / max_score if max_score > 0 else 0.0
    
    def _calculate_semantic_consistency_score(self, question: str, exec_result: ExecutionResult) -> float:
        """Score based on semantic consistency using LLM judge"""
        
        if exec_result.error:
            return 0.0
        
        # Prepare results for LLM evaluation
        results_summary = json.dumps(exec_result.results[:10], indent=2)  # Limit for token efficiency
        
        prompt = f"""
You are evaluating whether query results semantically answer the given question.

Question: {question}
Query Results: {results_summary}
Result Count: {len(exec_result.results)}

Evaluate on a scale of 0-100:
1. Do these results directly answer the question?
2. Are the results relevant to what was asked?
3. Is the result format appropriate for the question type?
4. Are the results complete (not missing obvious information)?

Consider:
- Factual accuracy and relevance
- Completeness of the answer
- Appropriate granularity/detail level
- Logical consistency

Return only a JSON object:
{{
    "semantic_score": 85,
    "reasoning": "The results directly answer the question about...",
    "relevance": 0.9,
    "completeness": 0.8,
    "appropriateness": 0.9
}}
"""
        
        try:
            response = self.gpt_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            evaluation = json.loads(response.choices[0].message.content)
            return evaluation.get("semantic_score", 0) / 100.0
            
        except Exception as e:
            print(f"Semantic scoring failed: {e}")
            return 0.5  # Neutral score on failure
    
    def _check_temporal_consistency(self, results: List[Dict], temporal_spec) -> float:
        """Check if results are properly ordered temporally"""
        
        if not results or not temporal_spec:
            return 1.0
        
        # Extract date field values
        field_name = temporal_spec.field.split('.')[-1]  # e.g., "e.date" -> "date"
        dates = []
        
        for record in results:
            if field_name in record and record[field_name]:
                dates.append(record[field_name])
        
        if len(dates) < 2:
            return 1.0  # Can't check ordering with < 2 dates
        
        # Check if dates are in expected order
        # This is a simplified check - in practice you'd parse dates properly
        if temporal_spec.order.value in ["desc", "reverse_chronological"]:
            # Should be descending
            is_ordered = all(dates[i] >= dates[i+1] for i in range(len(dates)-1))
        else:
            # Should be ascending
            is_ordered = all(dates[i] <= dates[i+1] for i in range(len(dates)-1))
        
        return 1.0 if is_ordered else 0.3
    
    def _get_structural_details(self, exec_result: ExecutionResult) -> Dict[str, Any]:
        """Get detailed structural scoring breakdown"""
        return {
            "valid_entities": len([e for e in exec_result.candidate.dsl.entities if e.label in self.schema.labels]),
            "total_entities": len(exec_result.candidate.dsl.entities),
            "valid_relationships": len([r for r in exec_result.candidate.dsl.relations if r.type in self.schema.relationships]),
            "total_relationships": len(exec_result.candidate.dsl.relations),
            "validation_errors": exec_result.candidate.validation.errors,
            "execution_error": exec_result.error
        }
    
    def _get_quality_details(self, exec_result: ExecutionResult) -> Dict[str, Any]:
        """Get detailed quality scoring breakdown"""
        return {
            "result_count": len(exec_result.results),
            "execution_time": exec_result.execution_time,
            "has_error": bool(exec_result.error),
            "non_empty_ratio": self._calculate_non_empty_ratio(exec_result.results)
        }
    
    def _get_semantic_details(self, question: str, exec_result: ExecutionResult) -> Dict[str, Any]:
        """Get detailed semantic scoring breakdown"""
        return {
            "question_length": len(question.split()),
            "result_count": len(exec_result.results),
            "avg_result_fields": statistics.mean([len(r.keys()) for r in exec_result.results]) if exec_result.results else 0
        }
    
    def _calculate_non_empty_ratio(self, results: List[Dict]) -> float:
        """Calculate ratio of non-empty values in results"""
        if not results:
            return 0.0
        
        total_values = sum(len(record.values()) for record in results)
        non_empty_values = sum(
            1 for record in results 
            for value in record.values() 
            if value is not None and value != ""
        )
        
        return non_empty_values / total_values if total_values > 0 else 0.0

class MultiCandidateQuerySystem:
    """Main system orchestrating multi-candidate query generation and scoring"""
    
    def __init__(self, gpt_client: OpenAI, neo4j_driver, schema_whitelist):
        self.variant_generator = QueryVariantGenerator(gpt_client, schema_whitelist)
        self.executor = QueryExecutor(neo4j_driver)
        self.scorer = ComprehensiveScorer(gpt_client, schema_whitelist)
    
    def generate_and_score_candidates(self, question: str, entity_links: List, 
                                    constraints: List, num_variants: int = 5) -> List[CandidateScore]:
        """
        Full pipeline: generate variants, execute, and score
        
        Returns list of scored candidates sorted by total score (best first)
        """
        
        print(f"🔄 Generating {num_variants} query variants...")
        
        # Step 1: Generate DSL variants
        candidates = self.variant_generator.generate_dsl_variants(
            question, entity_links, constraints, num_variants
        )
        
        print(f"✅ Generated {len(candidates)} valid candidates")
        
        # Step 2: Execute all candidates
        print("⚡ Executing candidates...")
        execution_results = self.executor.execute_candidates(candidates)
        
        successful_executions = [r for r in execution_results if not r.error]
        print(f"✅ {len(successful_executions)}/{len(execution_results)} executed successfully")
        
        # Step 3: Score all candidates
        print("🎯 Scoring candidates...")
        scored_candidates = self.scorer.score_candidates(question, execution_results)
        
        print(f"🏆 Best candidate score: {scored_candidates[0].total_score:.3f}")
        
        return scored_candidates

if __name__ == "__main__":
    print("Multi-Candidate Query System implementation completed!")
    print("This module requires integration with OpenAI, Neo4j, and schema components.") 