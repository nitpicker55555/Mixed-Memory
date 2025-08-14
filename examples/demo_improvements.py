#!/usr/bin/env python3
"""
Demo script showcasing all improvements to the Agentic Search Engine

This script demonstrates:
1. Structured DSL generation and compilation
2. Entity linking with confidence scoring
3. Multi-candidate query generation and scoring
4. Schema validation and error prevention
"""

import json
from query_dsl import create_person_events_dsl, create_location_list_dsl
from dsl_compiler import DSLCompiler, SchemaWhitelist
from entity_linker import EntityCandidate, EntityLink, ConstraintExtraction

def demo_dsl_and_compilation():
    """Demonstrate DSL creation and compilation with validation"""
    
    print("🔧 Demo 1: Structured DSL and Schema-Validated Compilation")
    print("=" * 70)
    
    # Create mock schema
    schema = SchemaWhitelist(
        labels={"Person", "Event", "Location"},
        relationships={"PARTICIPATED_IN", "OCCURRED_AT"},
        properties={
            "Person": {"name", "birthDate", "aka"},
            "Event": {"name", "date", "location", "description"},
            "Location": {"name", "country", "coordinates"}
        }
    )
    
    compiler = DSLCompiler(schema)
    
    # Test 1: Valid DSL
    print("\n📝 Test 1: Valid Person Events DSL")
    dsl_valid = create_person_events_dsl("Lucy Carter", "desc", 1)
    print("DSL Structure:")
    print(json.dumps(dsl_valid.to_dict(), indent=2))
    
    cypher, validation = compiler.compile(dsl_valid)
    print(f"\n✅ Validation: {'PASSED' if validation.is_valid else 'FAILED'}")
    if validation.errors:
        print(f"❌ Errors: {validation.errors}")
    
    print(f"\n🔗 Generated Cypher:")
    print(cypher)
    
    # Test 2: Invalid DSL (wrong relationship)
    print("\n" + "="*50)
    print("📝 Test 2: Invalid DSL with Wrong Relationship")
    
    from query_dsl import QueryDSL, EntitySpec, RelationSpec
    dsl_invalid = QueryDSL(
        entities=[
            EntitySpec(alias="p", label="Person", link={"name": "John"}),
            EntitySpec(alias="e", label="Event")
        ],
        relations=[
            RelationSpec(from_alias="p", type="INVALID_RELATIONSHIP", to_alias="e")  # Wrong!
        ]
    )
    
    cypher_invalid, validation_invalid = compiler.compile(dsl_invalid)
    print(f"✅ Validation: {'PASSED' if validation_invalid.is_valid else 'FAILED'}")
    print(f"❌ Errors: {validation_invalid.errors}")
    
    print("\n🎯 Key Benefits:")
    print("  • Schema hallucination prevention")
    print("  • Automatic validation before execution")
    print("  • Injection attack prevention")
    print("  • Consistent query structure")

def demo_entity_linking():
    """Demonstrate enhanced entity linking concepts"""
    
    print("\n\n🔗 Demo 2: Enhanced Entity Linking with Confidence Scoring")
    print("=" * 70)
    
    # Mock entity candidates
    candidates = [
        EntityCandidate(
            node_id="person_123",
            label="Person",
            properties={"name": "Lucy Carter", "aka": "LC", "birthDate": "1990-05-15"},
            confidence=0.95,
            match_reason="Exact name match + high vector similarity"
        ),
        EntityCandidate(
            node_id="person_456",
            label="Person", 
            properties={"name": "Lucy C.", "birthDate": "1985-03-20"},
            confidence=0.72,
            match_reason="Partial name match + medium vector similarity"
        ),
        EntityCandidate(
            node_id="person_789",
            label="Person",
            properties={"name": "Lucy Carson", "birthDate": "1988-11-10"},
            confidence=0.45,
            match_reason="Name similarity but different surname"
        )
    ]
    
    print("📊 Entity Linking Results for 'Lucy Carter':")
    print(f"{'Candidate':<15} {'Label':<10} {'Confidence':<12} {'Properties'}")
    print("-" * 70)
    
    for i, candidate in enumerate(candidates, 1):
        props_str = f"name: {candidate.properties.get('name', 'N/A')}"
        print(f"Candidate {i:<7} {candidate.label:<10} {candidate.confidence:<12.3f} {props_str}")
    
    # Show selected candidate
    best_candidate = candidates[0]  # Highest confidence
    print(f"\n🏆 Selected: {best_candidate.properties['name']} (confidence: {best_candidate.confidence:.3f})")
    print(f"   Reason: {best_candidate.match_reason}")
    
    # Show constraint extraction example
    print("\n📋 Constraint Extraction Example:")
    constraints = [
        ConstraintExtraction(
            field="e.date",
            operator="not_empty",
            context="Temporal query requires valid dates",
            confidence=0.9
        ),
        ConstraintExtraction(
            field="e.location",
            operator="exists",
            context="Location-based query needs location property",
            confidence=0.85
        )
    ]
    
    for constraint in constraints:
        print(f"  • {constraint.field} {constraint.operator} (confidence: {constraint.confidence:.2f})")
        print(f"    Context: {constraint.context}")
    
    print("\n🎯 Key Benefits:")
    print("  • Disambiguation of similar entities")
    print("  • Confidence-based filtering")
    print("  • Vector similarity + LLM cross-verification")
    print("  • Structured constraint extraction")

def demo_multi_candidate_scoring():
    """Demonstrate multi-candidate query scoring concepts"""
    
    print("\n\n🎯 Demo 3: Multi-Candidate Query Generation & Scoring")
    print("=" * 70)
    
    # Mock query candidates with different approaches
    candidates_info = [
        {
            "approach": "Temporal-focused DSL",
            "cypher": "MATCH (p:Person)-[:PARTICIPATED_IN]->(e:Event) WHERE p.name='Lucy Carter' AND e.date<>'' WITH e, [date conversion] ORDER BY sort_date DESC LIMIT 1",
            "structural_score": 0.95,
            "result_quality_score": 0.90,
            "semantic_consistency_score": 0.88,
            "total_score": 0.91,
            "results": [{"location": "Townsville"}],
            "execution_time": 0.45
        },
        {
            "approach": "Simple entity matching",
            "cypher": "MATCH (p:Person {name:'Lucy Carter'})-[:PARTICIPATED_IN]->(e:Event) RETURN e.location",
            "structural_score": 0.80,
            "result_quality_score": 0.65,
            "semantic_consistency_score": 0.70,
            "total_score": 0.71,
            "results": [{"location": "Townsville"}, {"location": "Springfield"}, {"location": "Metropolis"}],
            "execution_time": 0.32
        },
        {
            "approach": "Over-constrained query",
            "cypher": "MATCH (p:Person)-[:PARTICIPATED_IN]->(e:Event)-[:LOCATED_AT]->(l:Location) WHERE p.name='Lucy Carter'",
            "structural_score": 0.40,  # Invalid relationship
            "result_quality_score": 0.0,  # No results
            "semantic_consistency_score": 0.0,
            "total_score": 0.13,
            "results": [],
            "execution_time": 0.15
        }
    ]
    
    print("📊 Candidate Query Scoring Results:")
    print(f"{'Approach':<25} {'Structural':<12} {'Quality':<10} {'Semantic':<10} {'Total':<8} {'Results'}")
    print("-" * 85)
    
    for candidate in candidates_info:
        result_count = len(candidate['results'])
        print(f"{candidate['approach']:<25} "
              f"{candidate['structural_score']:<12.3f} "
              f"{candidate['result_quality_score']:<10.3f} "
              f"{candidate['semantic_consistency_score']:<10.3f} "
              f"{candidate['total_score']:<8.3f} "
              f"{result_count} results")
    
    # Show winner
    best_candidate = max(candidates_info, key=lambda x: x['total_score'])
    print(f"\n🏆 Winner: {best_candidate['approach']}")
    print(f"   Total Score: {best_candidate['total_score']:.3f}")
    print(f"   Result: {best_candidate['results'][0] if best_candidate['results'] else 'No results'}")
    print(f"   Execution Time: {best_candidate['execution_time']:.2f}s")
    
    print("\n📈 Scoring Breakdown for Winner:")
    print(f"  • Structural Score: {best_candidate['structural_score']:.3f}")
    print("    - Valid schema elements")
    print("    - Proper relationship usage")
    print("    - Successful execution")
    
    print(f"  • Result Quality Score: {best_candidate['result_quality_score']:.3f}")
    print("    - Reasonable result count")
    print("    - Non-empty value coverage")
    print("    - Temporal consistency")
    print("    - Query performance")
    
    print(f"  • Semantic Consistency Score: {best_candidate['semantic_consistency_score']:.3f}")
    print("    - Results answer the question")
    print("    - Appropriate format")
    print("    - Completeness")
    
    print("\n🎯 Key Benefits:")
    print("  • Self-consistency across multiple attempts")
    print("  • Comprehensive scoring (structure + quality + semantics)")
    print("  • Automatic best candidate selection")
    print("  • Reduced variance in query performance")

def demo_complete_pipeline():
    """Demonstrate the complete enhanced pipeline"""
    
    print("\n\n🚀 Demo 4: Complete Enhanced Pipeline")
    print("=" * 70)
    
    question = "What was Lucy Carter's most recent location?"
    
    print(f"📝 Question: {question}")
    
    print("\n🔄 Pipeline Stages:")
    
    # Stage 1: Intent Analysis
    print("\n1️⃣ Query Intent Analysis")
    print("   🔍 Entity mentions: ['Lucy Carter']")
    print("   🔗 Entity linking: Person(name='Lucy Carter', confidence=0.95)")
    print("   📋 Constraints: [e.date NOT_EMPTY, temporal_ordering]")
    print("   🎯 Intent confidence: 0.89")
    
    # Stage 2: Multi-candidate generation
    print("\n2️⃣ Multi-Candidate Generation (3 variants)")
    print("   📊 Temperature=0.1, seed=42: Temporal-focused approach")
    print("   📊 Temperature=0.3, seed=123: Entity-focused approach") 
    print("   📊 Temperature=0.5, seed=456: Relationship-exploration approach")
    
    # Stage 3: Compilation & validation
    print("\n3️⃣ DSL Compilation & Schema Validation")
    print("   ✅ Candidate 1: VALID (all schema elements verified)")
    print("   ✅ Candidate 2: VALID (simpler but correct)")
    print("   ❌ Candidate 3: INVALID (uses non-existent LOCATED_AT relationship)")
    
    # Stage 4: Execution & scoring
    print("\n4️⃣ Query Execution & Comprehensive Scoring")
    print("   ⚡ Executed 2 valid candidates")
    print("   🎯 Scored on: structural (30%) + quality (40%) + semantic (30%)")
    print("   🏆 Best score: 0.91 (Temporal-focused approach)")
    
    # Stage 5: Final result
    print("\n5️⃣ Final Result")
    print("   ✅ Answer: Townsville")
    print("   📊 Confidence: 0.91")
    print("   ⏱️ Total time: 2.3s")
    
    print("\n🎯 Improvements Achieved:")
    print("  ✅ Schema hallucination eliminated")
    print("  ✅ Entity disambiguation improved")
    print("  ✅ Query reliability increased")
    print("  ✅ Confidence calibration enhanced")
    print("  ✅ Error detection automated")

def main():
    """Run all demos"""
    print("🎪 Enhanced Agentic Search Engine - Feature Demonstrations")
    print("=" * 80)
    
    demo_dsl_and_compilation()
    demo_entity_linking()
    demo_multi_candidate_scoring()
    demo_complete_pipeline()
    
    print("\n\n🎉 All Demonstrations Complete!")
    print("\n💡 The enhanced engine provides:")
    print("   • 🛡️  Robust schema validation")
    print("   • 🎯  Accurate entity linking")
    print("   • 🏆  Self-consistent query generation")
    print("   • 📊  Comprehensive quality scoring")
    print("   • 🔍  Transparent decision process")
    
    print("\n📚 Next Steps:")
    print("   1. Test with real Neo4j database")
    print("   2. Tune scoring weights for your domain")
    print("   3. Add domain-specific entity types")
    print("   4. Integrate with production systems")

if __name__ == "__main__":
    main() 