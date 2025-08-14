#!/usr/bin/env python3
"""
Test Questions 41-51 with Answer Comparison

This script tests the enhanced agentic search engine on chronological questions 41-51
and logs both actual answers and expected answers for comparison.
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any

def load_questions_41_to_51():
    """Load chronological questions from the batch results"""
    # Load from the actual test results that were run previously
    results_file = "/Users/yunanli/Desktop/MasterThesisNew/AgenticSearch/results_1_60/agentic_results_20250813_152117/results_1to60_20250813_161551.json"
    
    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            batch_results = json.load(f)
        
        # Look for chronological questions (questions 40-50 based on the report)
        chronological_keywords = ['most recent', 'chronological order', 'earliest to latest', 'chronological timeline']
        
        test_questions = []
        for i, result in enumerate(batch_results, 1):
            question_text = result.get('question', '').lower()
            
            # Check if this is a chronological question
            if any(keyword in question_text for keyword in chronological_keywords):
                # Extract expected answer from the predicted answer or use a default
                expected_answer = ['Unknown']  # Default
                test_questions.append({
                    'id': i,  # Use the sequence number as ID
                    'question': result.get('question', ''),
                    'answer': expected_answer,
                    'answer_type': 'Chronological',
                    'cue': f"Question {i}",
                    'debug_info': 0
                })
        
        print(f"✅ Loaded {len(test_questions)} chronological questions")
        
        # Also try to load from the questions file with different approach
        questions_file = "/Users/yunanli/Desktop/MasterThesisNew/Mixed-Memory/data/questions_new_book.json"
        
        try:
            with open(questions_file, 'r', encoding='utf-8') as f:
                all_questions = json.load(f)
            
            # Look for chronological questions in the original data
            for q in all_questions:
                question_text = q.get('question', '').lower()
                if any(keyword in question_text for keyword in chronological_keywords):
                    # Avoid duplicates
                    if not any(existing['question'] == q.get('question') for existing in test_questions):
                        test_questions.append({
                            'id': len(test_questions) + 40,  # Start from 40+
                            'question': q.get('question', ''),
                            'answer': q.get('correct_answer', ['Unknown']),
                            'answer_type': q.get('retrieval_type', 'Chronological'),
                            'cue': q.get('cue', ''),
                            'debug_info': q.get('debug_level_2', 0)
                        })
            
            print(f"✅ Total chronological questions found: {len(test_questions)}")
            
        except Exception as e:
            print(f"⚠️ Could not load from questions file: {e}")
        
        return test_questions
        
    except Exception as e:
        print(f"❌ Failed to load questions: {str(e)}")
        return []

def test_agentic_search_engine():
    """Test if the agentic search engine can be initialized"""
    try:
        from agentic_search_engine import AgenticSearchEngine
        
        # Initialize engine
        engine = AgenticSearchEngine(
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD", "password")
        )
        
        print("✅ AgenticSearchEngine initialized successfully")
        return engine
        
    except Exception as e:
        print(f"❌ Failed to initialize AgenticSearchEngine: {str(e)}")
        return None

def run_single_question_test(engine, question_data: Dict, log_file: str) -> Dict[str, Any]:
    """Run test for a single question and log results"""
    
    question_id = question_data['id']
    question = question_data['question']
    expected_answer = question_data['answer']
    
    print(f"\n{'='*80}")
    print(f"🔍 Testing Question {question_id}")
    print(f"{'='*80}")
    print(f"❓ Question: {question}")
    print(f"🎯 Expected Answer: {expected_answer}")
    print(f"📋 Answer Type: {question_data['answer_type']}")
    
    # Log to file
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*100}\n")
        f.write(f"QUESTION {question_id} TEST\n")
        f.write(f"{'='*100}\n")
        f.write(f"Timestamp: {datetime.now()}\n")
        f.write(f"Question: {question}\n")
        f.write(f"Expected Answer: {expected_answer}\n")
        f.write(f"Answer Type: {question_data['answer_type']}\n")
        f.write(f"Cue: {question_data.get('cue', 'N/A')}\n")
        f.write(f"{'-'*50}\n")
    
    start_time = time.time()
    
    try:
        # Run the search
        result = engine.search(question)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Extract results
        actual_answer = result.get('final_answer', 'No answer provided')
        confidence = result.get('confidence_score', 0.0)
        success = result.get('search_successful', False)
        query_used = result.get('query_used', 'N/A')
        reasoning = result.get('reasoning_chain', [])
        
        print(f"⏱️ Execution Time: {execution_time:.2f}s")
        print(f"🤖 Actual Answer: {actual_answer}")
        print(f"📈 Confidence: {confidence:.3f}")
        print(f"✅ Success: {success}")
        print(f"🔗 Query Used: {query_used}")
        
        # Log detailed results to file
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"EXECUTION RESULTS:\n")
            f.write(f"Execution Time: {execution_time:.2f}s\n")
            f.write(f"Actual Answer: {actual_answer}\n")
            f.write(f"Confidence: {confidence:.3f}\n")
            f.write(f"Success: {success}\n")
            f.write(f"Query Used: {query_used}\n")
            f.write(f"Reasoning Chain: {reasoning}\n")
            f.write(f"\nANSWER COMPARISON:\n")
            f.write(f"Expected: {expected_answer}\n")
            f.write(f"Actual:   {actual_answer}\n")
            
            # Simple answer matching analysis
            if isinstance(expected_answer, list) and len(expected_answer) > 0:
                expected_str = str(expected_answer[0]).lower() if expected_answer[0] else ""
            else:
                expected_str = str(expected_answer).lower()
            
            actual_str = str(actual_answer).lower()
            
            if expected_str in actual_str or actual_str in expected_str:
                match_status = "PARTIAL_MATCH"
            elif expected_str == actual_str:
                match_status = "EXACT_MATCH"
            else:
                match_status = "NO_MATCH"
            
            f.write(f"Match Status: {match_status}\n")
            f.write(f"{'='*100}\n\n")
        
        # Prepare result summary
        test_result = {
            "question_id": question_id,
            "question": question,
            "expected_answer": expected_answer,
            "actual_answer": actual_answer,
            "confidence": confidence,
            "success": success,
            "execution_time": execution_time,
            "query_used": query_used,
            "reasoning_chain": reasoning,
            "match_status": match_status,
            "full_result": result
        }
        
        print(f"📊 Match Status: {match_status}")
        
        return test_result
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Test failed: {error_msg}")
        
        # Log error
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"ERROR: {error_msg}\n")
            f.write(f"{'='*100}\n\n")
        
        return {
            "question_id": question_id,
            "question": question,
            "expected_answer": expected_answer,
            "actual_answer": None,
            "confidence": 0.0,
            "success": False,
            "execution_time": 0.0,
            "error": error_msg,
            "match_status": "ERROR"
        }

def run_questions_41_51_test():
    """Run complete test for questions 41-51"""
    
    print("🧪 Testing Questions 41-51 (Chronological Questions)")
    print("=" * 80)
    
    # Initialize log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"questions_41_51_test_{timestamp}.log"
    
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"Questions 41-51 Test Log\n")
        f.write(f"Started at: {datetime.now()}\n")
        f.write(f"Testing chronological questions with answer comparison\n")
        f.write(f"{'='*100}\n\n")
    
    print(f"📝 Logging detailed results to: {log_file}")
    
    # Load questions
    questions = load_questions_41_to_51()
    
    if not questions:
        print("❌ No questions loaded. Stopping.")
        return
    
    print(f"\n📋 Questions to test:")
    for q in questions:
        print(f"   Q{q['id']}: {q['question'][:80]}...")
    
    # Initialize engine
    print(f"\n🚀 Initializing Agentic Search Engine...")
    engine = test_agentic_search_engine()
    
    if not engine:
        print("❌ Could not initialize engine. Stopping.")
        return
    
    # Run tests
    print(f"\n🔄 Running tests for {len(questions)} questions...")
    results = []
    
    for i, question_data in enumerate(questions, 1):
        print(f"\nProgress: {i}/{len(questions)}")
        
        result = run_single_question_test(engine, question_data, log_file)
        results.append(result)
        
        # Small delay between questions
        time.sleep(1)
    
    # Generate summary
    print(f"\n{'='*80}")
    print("📈 FINAL SUMMARY")
    print(f"{'='*80}")
    
    total_questions = len(results)
    successful_questions = sum(1 for r in results if r.get('success', False))
    exact_matches = sum(1 for r in results if r.get('match_status') == 'EXACT_MATCH')
    partial_matches = sum(1 for r in results if r.get('match_status') == 'PARTIAL_MATCH')
    no_matches = sum(1 for r in results if r.get('match_status') == 'NO_MATCH')
    errors = sum(1 for r in results if r.get('match_status') == 'ERROR')
    
    avg_confidence = sum(r.get('confidence', 0) for r in results) / total_questions if total_questions > 0 else 0
    avg_time = sum(r.get('execution_time', 0) for r in results) / total_questions if total_questions > 0 else 0
    
    print(f"📊 Total Questions: {total_questions}")
    print(f"✅ Successful Executions: {successful_questions} ({successful_questions/total_questions*100:.1f}%)")
    print(f"🎯 Exact Matches: {exact_matches} ({exact_matches/total_questions*100:.1f}%)")
    print(f"🔍 Partial Matches: {partial_matches} ({partial_matches/total_questions*100:.1f}%)")
    print(f"❌ No Matches: {no_matches} ({no_matches/total_questions*100:.1f}%)")
    print(f"⚠️ Errors: {errors} ({errors/total_questions*100:.1f}%)")
    print(f"📈 Average Confidence: {avg_confidence:.3f}")
    print(f"⏱️ Average Time: {avg_time:.2f}s")
    
    # Detailed answer comparison
    print(f"\n📋 DETAILED ANSWER COMPARISON:")
    print(f"{'ID':<4} {'Status':<12} {'Expected':<30} {'Actual':<30}")
    print("-" * 80)
    
    for result in results:
        q_id = result['question_id']
        status = result.get('match_status', 'UNKNOWN')
        expected = str(result['expected_answer'])[:28] if result['expected_answer'] else 'N/A'
        actual = str(result['actual_answer'])[:28] if result['actual_answer'] else 'N/A'
        
        print(f"{q_id:<4} {status:<12} {expected:<30} {actual:<30}")
    
    # Save results to JSON
    results_file = f"questions_41_51_results_{timestamp}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_summary": {
                "total_questions": total_questions,
                "successful": successful_questions,
                "success_rate": successful_questions/total_questions if total_questions > 0 else 0,
                "exact_matches": exact_matches,
                "partial_matches": partial_matches,
                "no_matches": no_matches,
                "errors": errors,
                "average_confidence": avg_confidence,
                "average_time": avg_time,
                "log_file": log_file
            },
            "results": results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n📝 Detailed Log: {log_file}")
    print(f"💾 Results JSON: {results_file}")
    
    # Close engine
    try:
        engine.close()
    except:
        pass
    
    return results

if __name__ == "__main__":
    try:
        results = run_questions_41_51_test()
        print("\n🎉 Test completed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc() 