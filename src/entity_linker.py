#!/usr/bin/env python3
"""
Enhanced Entity Linking and Constraint Extraction

Provides robust entity linking with vector search + cross-verification
and structured constraint extraction from natural language questions.
"""

from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass
import re
from openai import OpenAI
import json

@dataclass
class EntityCandidate:
    """A candidate entity from linking process"""
    node_id: str
    label: str
    properties: Dict[str, Any]
    confidence: float
    match_reason: str

@dataclass
class EntityLink:
    """Final entity link result"""
    alias: str
    label: str
    properties: Dict[str, Any]
    confidence: float
    candidates_considered: int

@dataclass 
class ConstraintExtraction:
    """Extracted constraint from question"""
    field: str  # e.g., "e.date", "p.name"
    operator: str  # e.g., "not_empty", "equals", "contains"
    value: Optional[Any] = None
    context: Optional[str] = None
    confidence: float = 1.0

@dataclass
class QueryIntent:
    """Structured representation of query intent"""
    entities: List[EntityLink]
    constraints: List[ConstraintExtraction]
    temporal_intent: Optional[Dict[str, Any]] = None
    aggregation_intent: Optional[Dict[str, Any]] = None
    output_intent: Optional[Dict[str, Any]] = None
    confidence: float = 1.0

class EntityLinker:
    """Enhanced entity linking with vector search and cross-verification"""
    
    def __init__(self, gpt_client: OpenAI, vector_searcher, schema_whitelist):
        self.gpt_client = gpt_client
        self.vector_searcher = vector_searcher
        self.schema = schema_whitelist
        self.confidence_threshold = 0.7
    
    def link_entities(self, question: str, top_k: int = 10) -> List[EntityLink]:
        """
        Link entities in question using two-step process:
        1. Vector search for candidates
        2. LLM cross-verification with schema
        """
        
        # Step 1: Extract potential entity mentions
        entity_mentions = self._extract_entity_mentions(question)
        
        entity_links = []
        for mention in entity_mentions:
            # Step 2: Vector search for candidates
            candidates = self._vector_search_candidates(mention, top_k)
            
            # Step 3: Cross-verify candidates with LLM
            verified_candidates = self._cross_verify_candidates(
                mention, candidates, question
            )
            
            # Step 4: Select best candidate above threshold
            best_candidate = self._select_best_candidate(verified_candidates)
            
            if best_candidate and best_candidate.confidence >= self.confidence_threshold:
                entity_links.append(EntityLink(
                    alias=self._generate_alias(best_candidate.label),
                    label=best_candidate.label,
                    properties=best_candidate.properties,
                    confidence=best_candidate.confidence,
                    candidates_considered=len(verified_candidates)
                ))
        
        return entity_links
    
    def _extract_entity_mentions(self, question: str) -> List[str]:
        """Extract potential entity mentions from question"""
        
        prompt = f"""
Extract potential entity mentions from this question that might refer to people, places, events, or other graph entities.

Question: {question}

Focus on:
- Proper nouns (names of people, places, events)
- Specific identifiers 
- Quoted strings
- Time/date references

Return a JSON list of entity mentions:
{{"mentions": ["mention1", "mention2", ...]}}

Be conservative - only extract clear entity references.
"""
        
        try:
            response = self.gpt_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get("mentions", [])
            
        except Exception as e:
            print(f"Entity mention extraction failed: {e}")
            # Fallback: simple regex for quoted strings and capitalized words
            mentions = []
            
            # Find quoted strings
            quoted = re.findall(r'"([^"]*)"', question)
            mentioned = re.findall(r"'([^']*)'", question)
            mentions.extend(quoted + mentioned)
            
            # Find capitalized word sequences (likely proper nouns)
            capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', question)
            mentions.extend(capitalized)
            
            return list(set(mentions))
    
    def _vector_search_candidates(self, mention: str, top_k: int) -> List[EntityCandidate]:
        """Search for entity candidates using vector similarity"""
        
        try:
            # Use vector searcher to find similar nodes
            vector_results = self.vector_searcher.vector_search(mention, top_k=top_k)
            
            candidates = []
            for result in vector_results:
                # Get node details
                node_details = self.vector_searcher.get_node_details([result['node_id']])
                if node_details:
                    detail = node_details[0]
                    candidates.append(EntityCandidate(
                        node_id=result['node_id'],
                        label=detail.get('label', 'Unknown'),
                        properties=detail.get('properties', {}),
                        confidence=result['similarity'],
                        match_reason=f"Vector similarity: {result['similarity']:.3f}"
                    ))
            
            return candidates
            
        except Exception as e:
            print(f"Vector search failed for '{mention}': {e}")
            return []
    
    def _cross_verify_candidates(self, mention: str, candidates: List[EntityCandidate], 
                               question: str) -> List[EntityCandidate]:
        """Cross-verify candidates using LLM with schema knowledge"""
        
        if not candidates:
            return []
        
        # Prepare candidate info for LLM
        candidate_info = []
        for i, candidate in enumerate(candidates):
            info = {
                "id": i,
                "label": candidate.label,
                "properties": candidate.properties,
                "vector_confidence": candidate.confidence
            }
            candidate_info.append(info)
        
        prompt = f"""
You are verifying entity candidates for the mention "{mention}" in this question: "{question}"

Available candidates:
{json.dumps(candidate_info, indent=2)}

Schema constraints:
- Valid labels: {list(self.schema.labels)}
- Valid properties per label: {dict(self.schema.properties)}

For each candidate, evaluate:
1. Does this entity likely match the mention "{mention}"?
2. Are the properties consistent with what's expected?
3. Does the label make sense in the question context?
4. Overall confidence (0-1)

Return JSON with verification results:
{{
    "verified_candidates": [
        {{
            "id": 0,
            "matches_mention": true,
            "property_consistency": 0.9,
            "context_relevance": 0.8,
            "overall_confidence": 0.85,
            "reasoning": "explanation"
        }},
        ...
    ]
}}

Be strict - only give high confidence to clear matches.
"""
        
        try:
            response = self.gpt_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            verification = json.loads(response.choices[0].message.content)
            verified_results = verification.get("verified_candidates", [])
            
            # Update candidate confidences
            verified_candidates = []
            for result in verified_results:
                candidate_id = result["id"]
                if candidate_id < len(candidates):
                    candidate = candidates[candidate_id]
                    # Combine vector and LLM confidences
                    combined_confidence = (
                        candidate.confidence * 0.3 +  # Vector similarity weight
                        result["overall_confidence"] * 0.7  # LLM verification weight
                    )
                    
                    candidate.confidence = combined_confidence
                    candidate.match_reason += f" | LLM verification: {result['reasoning']}"
                    verified_candidates.append(candidate)
            
            return verified_candidates
            
        except Exception as e:
            print(f"Cross-verification failed: {e}")
            return candidates  # Return original candidates as fallback
    
    def _select_best_candidate(self, candidates: List[EntityCandidate]) -> Optional[EntityCandidate]:
        """Select the best candidate based on confidence"""
        if not candidates:
            return None
        
        # Sort by confidence and return best
        sorted_candidates = sorted(candidates, key=lambda c: c.confidence, reverse=True)
        return sorted_candidates[0]
    
    def _generate_alias(self, label: str) -> str:
        """Generate a short alias for the entity label"""
        return label.lower()[0]  # Simple: first letter of label

class ConstraintExtractor:
    """Extract structured constraints from natural language questions"""
    
    def __init__(self, gpt_client: OpenAI, schema_whitelist):
        self.gpt_client = gpt_client
        self.schema = schema_whitelist
    
    def extract_constraints(self, question: str, entity_links: List[EntityLink]) -> List[ConstraintExtraction]:
        """Extract structured constraints from question"""
        
        # Build entity context
        entity_context = []
        for link in entity_links:
            entity_context.append({
                "alias": link.alias,
                "label": link.label,
                "properties": link.properties
            })
        
        prompt = f"""
Analyze this question and extract structured constraints/filters that should be applied.

Question: {question}
Entities identified: {json.dumps(entity_context, indent=2)}
Available properties: {dict(self.schema.properties)}

Extract constraints like:
- Temporal filters (date not empty, date ranges)
- Property existence checks  
- Value filters (equals, contains, etc.)
- Relationship constraints

Common patterns:
- "most recent" → temporal ordering + not empty date
- "chronological" → temporal ordering
- "location" → location property exists
- specific names → equals constraints

Return JSON:
{{
    "constraints": [
        {{
            "field": "e.date",
            "operator": "not_empty",
            "value": null,
            "context": "temporal query requires valid dates",
            "confidence": 0.9
        }},
        ...
    ],
    "temporal_intent": {{
        "requires_ordering": true,
        "direction": "desc",
        "field": "e.date"
    }},
    "aggregation_intent": {{
        "type": "collect",
        "field": "e.location",
        "distinct": true
    }},
    "output_intent": {{
        "limit": 1,
        "fields": ["e.location"]
    }}
}}
"""
        
        try:
            response = self.gpt_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Parse constraints
            constraints = []
            for constraint_data in result.get("constraints", []):
                constraints.append(ConstraintExtraction(
                    field=constraint_data["field"],
                    operator=constraint_data["operator"],
                    value=constraint_data.get("value"),
                    context=constraint_data.get("context"),
                    confidence=constraint_data.get("confidence", 1.0)
                ))
            
            return constraints, result.get("temporal_intent"), result.get("aggregation_intent"), result.get("output_intent")
            
        except Exception as e:
            print(f"Constraint extraction failed: {e}")
            return [], None, None, None

class QueryIntentAnalyzer:
    """Main analyzer combining entity linking and constraint extraction"""
    
    def __init__(self, gpt_client: OpenAI, vector_searcher, schema_whitelist):
        self.entity_linker = EntityLinker(gpt_client, vector_searcher, schema_whitelist)
        self.constraint_extractor = ConstraintExtractor(gpt_client, schema_whitelist)
        self.schema = schema_whitelist
    
    def analyze_query_intent(self, question: str) -> QueryIntent:
        """Analyze question and return structured query intent"""
        
        # Step 1: Link entities
        entity_links = self.entity_linker.link_entities(question)
        
        # Step 2: Extract constraints
        constraints, temporal_intent, aggregation_intent, output_intent = \
            self.constraint_extractor.extract_constraints(question, entity_links)
        
        # Step 3: Calculate overall confidence
        entity_confidences = [link.confidence for link in entity_links]
        constraint_confidences = [c.confidence for c in constraints]
        
        overall_confidence = 1.0
        if entity_confidences:
            overall_confidence *= sum(entity_confidences) / len(entity_confidences)
        if constraint_confidences:
            overall_confidence *= sum(constraint_confidences) / len(constraint_confidences)
        
        return QueryIntent(
            entities=entity_links,
            constraints=constraints,
            temporal_intent=temporal_intent,
            aggregation_intent=aggregation_intent,
            output_intent=output_intent,
            confidence=overall_confidence
        )

if __name__ == "__main__":
    # Test with mock components
    print("Entity Linker and Constraint Extractor implementation completed!")
    print("This module requires integration with vector search and schema components.") 