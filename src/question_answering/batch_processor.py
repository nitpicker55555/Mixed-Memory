"""
Batch Question Processing Module

This module provides functionality for processing multiple questions
in batch mode and generating comprehensive reports.
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Tuple


def parse_question_range(range_str: str) -> Tuple[int, int]:
    """
    Parse question range string.
    
    Args:
        range_str: Range string like '1-10' or '5'
        
    Returns:
        Tuple of (start_index, end_index)
        
    Example:
        >>> parse_question_range('1-10')
        (1, 10)
        >>> parse_question_range('5')
        (5, 5)
    """
    if '-' in range_str:
        start, end = range_str.split('-')
        return int(start.strip()), int(end.strip())
    else:
        num = int(range_str.strip())
        return num, num


def load_questions_from_file(questions_path: str) -> List[Dict]:
    """
    Load questions from JSON file.
    
    Args:
        questions_path: Path to questions JSON file
        
    Returns:
        List of question dictionaries
        
    Raises:
        Exception: If file cannot be loaded
    """
    try:
        with open(questions_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)
        print(f"Loaded {len(questions)} questions from {questions_path}")
        return questions
    except Exception as e:
        print(f"Error loading questions file: {e}")
        raise


def run_questions_batch(
    engine, questions: List[Dict], 
    start_idx: int, end_idx: int, 
    output_dir: str = None
) -> Dict:
    """
    Run a batch of questions through the search engine.
    
    Args:
        engine: AgenticSearchEngine instance
        questions: List of question dictionaries
        start_idx: Starting question index (1-based)
        end_idx: Ending question index (1-based)
        output_dir: Optional output directory for results
        
    Returns:
        Dictionary with batch results and metadata
    """
    results = {
        "metadata": {
            "start_time": datetime.now().isoformat(),
            "database": engine.database,
            "question_range": f"{start_idx}-{end_idx}",
            "total_questions": end_idx - start_idx + 1
        },
        "results": []
    }
    
    print(f"\nRunning questions {start_idx}-{end_idx} on database '{engine.database}'")
    print("=" * 70)
    
    for i in range(start_idx - 1, min(end_idx, len(questions))):
        question_data = questions[i]
        q_idx = question_data.get('q_idx', i + 1)
        question_text = question_data.get('question', '')
        
        print(f"\nQuestion {q_idx}: {question_text}")
        print("-" * 50)
        
        try:
            start_time = datetime.now()
            answer = engine.search(question_text)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                "question_idx": q_idx,
                "question": question_text,
                "answer": answer,
                "duration_seconds": duration,
                "status": "success",
                "timestamp": start_time.isoformat()
            }
            
            # Extract token usage from answer
            if isinstance(answer, dict) and 'token_usage' in answer:
                result['token_usage'] = answer['token_usage']
            
            # Add expected answer if available
            if 'correct_answer' in question_data:
                result['expected_answer'] = question_data['correct_answer']
            
            print(f"Answer: {answer}")
            print(f"Duration: {duration:.2f}s")
            
            # Print token usage
            if 'token_usage' in result:
                tokens = result['token_usage']
                print(f"Tokens: {tokens['total_tokens']} total "
                      f"({tokens['prompt_tokens']} prompt + "
                      f"{tokens['completion_tokens']} completion, "
                      f"{tokens['calls_count']} calls)")
            
        except Exception as e:
            result = {
                "question_idx": q_idx,
                "question": question_text,
                "answer": None,
                "error": str(e),
                "status": "error",
                "timestamp": datetime.now().isoformat()
            }
            print(f"Error: {e}")
        
        results["results"].append(result)
    
    results["metadata"]["end_time"] = datetime.now().isoformat()
    results["metadata"]["total_duration"] = sum(
        r.get("duration_seconds", 0) for r in results["results"]
    )
    
    # Save results if output directory specified
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save JSON results
        filename = f"questions_{start_idx}_{end_idx}_results_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\nResults saved to: {filepath}")
        
        # Generate report
        report_filepath = generate_agentic_report(
            results, output_dir, start_idx, end_idx, timestamp
        )
        print(f"Report saved to: {report_filepath}")
    
    return results


def generate_agentic_report(
    results: Dict, output_dir: str, 
    start_idx: int, end_idx: int, timestamp: str
) -> str:
    """
    Generate comprehensive results report.
    
    Args:
        results: Results dictionary from batch processing
        output_dir: Output directory
        start_idx: Starting question index
        end_idx: Ending question index
        timestamp: Timestamp string
        
    Returns:
        Path to generated report file
    """
    # Calculate statistics
    total_questions = len(results["results"])
    successful_searches = sum(
        1 for r in results["results"] 
        if r.get("answer", {}).get("search_successful", False)
    )
    questions_with_answers = sum(
        1 for r in results["results"] 
        if r.get("answer", {}).get("final_answer") is not None
    )
    success_rate = (successful_searches / total_questions * 100) if total_questions > 0 else 0
    answer_rate = (questions_with_answers / total_questions * 100) if total_questions > 0 else 0
    
    # Calculate average iterations
    iteration_counts = [
        r.get("answer", {}).get("total_iterations", 0) 
        for r in results["results"]
    ]
    avg_iterations = sum(iteration_counts) / len(iteration_counts) if iteration_counts else 0
    
    # Build report content
    report_content = f"""AGENTIC SEARCH BATCH RESULTS REPORT
==================================================

Execution Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Question Range: {start_idx}-{end_idx}
Total Questions Processed: {total_questions}
Successful Searches: {successful_searches} ({success_rate:.1f}%)
Questions with Answers: {questions_with_answers} ({answer_rate:.1f}%)
Average Iterations per Question: {avg_iterations:.1f}

DETAILED RESULTS:
------------------------------

"""
    
    for i, result in enumerate(results["results"], 1):
        question_text = result.get("question", "")
        expected_answer = result.get("expected_answer", [])
        
        # Format expected answer
        if isinstance(expected_answer, list):
            expected_str = str(expected_answer)
        else:
            expected_str = str(expected_answer) if expected_answer else "None"
        
        # Get predicted answer
        predicted_answer = result.get("answer", {}).get("final_answer")
        if predicted_answer is None:
            predicted_str = "None"
        elif isinstance(predicted_answer, list):
            predicted_str = str(predicted_answer)
        else:
            predicted_str = str(predicted_answer)
        
        # Get search success
        search_success = result.get("answer", {}).get("search_successful", False)
        
        # Calculate confidence
        iterations = result.get("answer", {}).get("total_iterations", 0)
        if search_success and predicted_answer:
            confidence = max(0.0, 1.0 - (iterations - 1) * 0.2)
        else:
            confidence = 0.0
        
        # Use correct question number
        question_num = start_idx + i - 1
        
        # Get token usage if available
        token_info = ""
        if 'token_usage' in result:
            tokens = result['token_usage']
            token_info = f"""  Token Usage: {tokens['total_tokens']} total ({tokens['prompt_tokens']} prompt + {tokens['completion_tokens']} completion, {tokens['calls_count']} calls)
"""
        
        report_content += f"""Question {question_num}:
  Text: {question_text}
  Expected: {expected_str}
  Predicted: {predicted_str}
  Search Success: {search_success}
  Confidence: {confidence:.2f}
  Iterations: {iterations}
{token_info}
"""
    
    # Save report
    report_filename = f"report_{start_idx}_{end_idx}_{timestamp}.txt"
    report_filepath = os.path.join(output_dir, report_filename)
    
    with open(report_filepath, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    return report_filepath

