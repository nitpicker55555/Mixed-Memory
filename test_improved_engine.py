#!/usr/bin/env python3
"""
Test script for the improved agentic search engine
"""

import sys
import os
sys.path.append('src/question_answering')

try:
    from agentic_search_engine import AgenticSearchEngine
    print("✅ Successfully imported AgenticSearchEngine")
    
    # Test question
    question = "List all locations visited by Lucy Carter in chronological order according to the story's timeline."
    print(f"Testing question: {question}")
    
    # Initialize engine
    engine = AgenticSearchEngine()
    print("✅ Successfully initialized AgenticSearchEngine")
    
    # Run search with limited iterations for testing
    print("🔍 Starting search...")
    result = engine.search(question, max_iterations=2)
    
    print("\n" + "="*80)
    print("🎯 SEARCH RESULTS:")
    print("="*80)
    
    print(f"Session ID: {result['session_id']}")
    print(f"Question: {result['question']}")
    print(f"Final Answer: {result['final_answer']}")
    print(f"Standardized Answer: {result['standardized_answer']}")
    print(f"Total Iterations: {result['total_iterations']}")
    print(f"Search Successful: {result['search_successful']}")
    print(f"Query History: {result['query_history']}")
    print(f"Reasoning Chain: {result['reasoning_chain']}")
    
    # Close driver connection
    if hasattr(engine, 'driver'):
        engine.driver.close()
        print("✅ Closed database connection")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc() 