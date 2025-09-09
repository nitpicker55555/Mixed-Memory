#!/usr/bin/env python3
"""
Agentic Search Batch Runner

This script runs agentic search on a specified range of questions from a question file.
It supports various input formats and provides comprehensive output including results and reports.

Usage:
    python run_agentic_batch.py --questions data/questions.json --range 1-20 --output results/
"""

import json
import os
import sys
import argparse
from datetime import datetime
from typing import List, Dict, Any
import time

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

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agentic_qa_interface import AgenticQAInterface


def load_questions(questions_path: str) -> List[Dict[str, Any]]:
    """
    Load questions from various file formats
    
    Args:
        questions_path: Path to questions file (JSON format)
        
    Returns:
        List of question dictionaries
    """
    print(f"📂 Loading questions from: {questions_path}")
    
    if not os.path.exists(questions_path):
        raise FileNotFoundError(f"Questions file not found: {questions_path}")
    
    try:
        with open(questions_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle different JSON structures
        if isinstance(data, list):
            questions = data
        elif isinstance(data, dict):
            if 'questions' in data:
                questions = data['questions']
            elif 'data' in data:
                questions = data['data']
            else:
                # Assume the dict values are questions
                questions = list(data.values()) if data else []
        else:
            raise ValueError("Unsupported questions file format")
        
        print(f"✅ Loaded {len(questions)} questions successfully")
        return questions
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in questions file: {e}")
    except Exception as e:
        raise ValueError(f"Error loading questions: {e}")


def parse_range(range_str: str, total_questions: int) -> List[int]:
    """
    Parse question range string into list of question indices
    
    Args:
        range_str: Range string like "1-20", "5,10,15", "1-10,15-20"
        total_questions: Total number of available questions
        
    Returns:
        List of question indices (0-based)
    """
    indices = []
    
    try:
        # Split by comma for multiple ranges/indices
        parts = range_str.split(',')
        
        for part in parts:
            part = part.strip()
            
            if '-' in part:
                # Handle range like "1-20"
                start, end = part.split('-')
                start_idx = int(start) - 1  # Convert to 0-based
                end_idx = int(end) - 1     # Convert to 0-based
                
                if start_idx < 0 or end_idx >= total_questions:
                    raise ValueError(f"Range {part} is out of bounds (1-{total_questions})")
                
                indices.extend(range(start_idx, end_idx + 1))
            else:
                # Handle single index like "5"
                idx = int(part) - 1  # Convert to 0-based
                
                if idx < 0 or idx >= total_questions:
                    raise ValueError(f"Index {part} is out of bounds (1-{total_questions})")
                
                indices.append(idx)
        
        # Remove duplicates and sort
        indices = sorted(list(set(indices)))
        
        print(f"📋 Selected questions: {[i+1 for i in indices]} (total: {len(indices)})")
        return indices
        
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError(f"Invalid range format: {range_str}. Use formats like '1-20', '5,10,15', or '1-10,15-20'")
        else:
            raise e


def setup_output_directory(output_path: str) -> str:
    """
    Setup output directory with timestamp
    
    Args:
        output_path: Base output path
        
    Returns:
        Full output directory path
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    full_output_dir = os.path.join(output_path, f"agentic_results_{timestamp}")
    
    os.makedirs(full_output_dir, exist_ok=True)
    print(f"📁 Output directory: {full_output_dir}")
    
    return full_output_dir


def save_results(results: List[Dict], output_dir: str, range_str: str) -> Dict[str, str]:
    """
    Save results in multiple formats
    
    Args:
        results: List of result dictionaries
        output_dir: Output directory path
        range_str: Range string for filename
        
    Returns:
        Dictionary of saved file paths
    """
    # Clean range string for filename
    clean_range = range_str.replace(',', '_').replace('-', 'to')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    files_saved = {}
    
    # Save raw JSON results
    json_file = os.path.join(output_dir, f"results_{clean_range}_{timestamp}.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    files_saved['json'] = json_file
    
    # Save human-readable report
    report_file = os.path.join(output_dir, f"report_{clean_range}_{timestamp}.txt")
    
    total_questions = len(results)
    successful_searches = sum(1 for r in results 
                            if r.get("gpt_answer_result", {}).get("search_successful", False))
    answered_questions = sum(1 for r in results 
                           if r.get("predicted_answer") is not None)
    avg_iterations = sum(r.get("agentic_metadata", {}).get("total_iterations", 0) 
                        for r in results) / total_questions if total_questions > 0 else 0
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("AGENTIC SEARCH BATCH RESULTS REPORT\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Question Range: {range_str}\n")
        f.write(f"Total Questions Processed: {total_questions}\n")
        f.write(f"Successful Searches: {successful_searches} ({successful_searches/total_questions*100:.1f}%)\n")
        f.write(f"Questions with Answers: {answered_questions} ({answered_questions/total_questions*100:.1f}%)\n")
        f.write(f"Average Iterations per Question: {avg_iterations:.1f}\n\n")
        
        f.write("DETAILED RESULTS:\n")
        f.write("-" * 30 + "\n\n")
        
        for i, result in enumerate(results):
            question_num = result.get("original_question_number", i + 1)
            question = result.get("question", "Unknown question")
            predicted = result.get("predicted_answer", "No answer")
            expected = result.get("expected_answer", [])
            iterations = result.get("agentic_metadata", {}).get("total_iterations", 0)
            search_success = result.get("gpt_answer_result", {}).get("search_successful", False)
            confidence = result.get("gpt_answer_result", {}).get("confidence_score", 0.0)
            
            f.write(f"Question {question_num}:\n")
            f.write(f"  Text: {question}\n")
            f.write(f"  Expected: {expected}\n")
            f.write(f"  Predicted: {predicted}\n")
            f.write(f"  Search Success: {search_success}\n")
            f.write(f"  Confidence: {confidence:.2f}\n")
            f.write(f"  Iterations: {iterations}\n")
            
            # Show reasoning chain if available
            reasoning_chain = result.get("agentic_metadata", {}).get("reasoning_chain", [])
            if reasoning_chain:
                f.write(f"  Reasoning Chain: {' → '.join(reasoning_chain[:3])}{'...' if len(reasoning_chain) > 3 else ''}\n")
            
            f.write("\n")
    
    files_saved['report'] = report_file
    
    # Save summary CSV for easy analysis
    csv_file = os.path.join(output_dir, f"summary_{clean_range}_{timestamp}.csv")
    with open(csv_file, 'w', encoding='utf-8') as f:
        f.write("question_num,question,predicted_answer,search_success,confidence,iterations\n")
        for i, result in enumerate(results):
            question_num = result.get("original_question_number", i + 1)
            question = result.get("question", "").replace('"', '""')  # Escape quotes
            predicted = str(result.get("predicted_answer", "")).replace('"', '""')
            search_success = result.get("gpt_answer_result", {}).get("search_successful", False)
            confidence = result.get("gpt_answer_result", {}).get("confidence_score", 0.0)
            iterations = result.get("agentic_metadata", {}).get("total_iterations", 0)
            
            f.write(f'{question_num},"{question}","{predicted}",{search_success},{confidence},{iterations}\n')
    
    files_saved['csv'] = csv_file
    
    return files_saved


def run_agentic_batch(questions_path: str, question_range: str, output_path: str,
                     neo4j_uri: str = "bolt://localhost:7687",
                     neo4j_user: str = "neo4j", neo4j_password: str = "password",
                     node_embeddings_path: str = None, verbose: bool = True) -> Dict[str, Any]:
    """
    Run agentic search on a batch of questions
    
    Args:
        questions_path: Path to questions file
        question_range: Range of questions to process (e.g., "1-20")
        output_path: Output directory path
        neo4j_uri: Neo4j database URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        node_embeddings_path: Path to node embeddings file (optional)
        verbose: Whether to print detailed progress
        
    Returns:
        Dictionary with execution results and statistics
    """
    
    print("🚀 AGENTIC SEARCH BATCH RUNNER")
    print("=" * 50)
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load questions
    questions = load_questions(questions_path)
    
    # Parse question range
    question_indices = parse_range(question_range, len(questions))
    selected_questions = [questions[i] for i in question_indices]
    
    # Setup output directory
    output_dir = setup_output_directory(output_path)
    
    # Initialize agentic QA interface
    print("🔧 Initializing Agentic Search Engine...")
    qa_interface = AgenticQAInterface(
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password
    )
    
    # Process questions
    print(f"\n🔍 Processing {len(selected_questions)} questions...")
    print("-" * 50)
    
    results = []
    start_time = time.time()
    
    for i, question_data in enumerate(selected_questions):
        original_index = question_indices[i]
        question_num = original_index + 1
        
        # Extract question text and expected answer
        if isinstance(question_data, dict):
            question_text = question_data.get("question", question_data.get("text", str(question_data)))
            # Try multiple possible field names for expected answer
            expected_answer = (
                question_data.get("correct_answer", []) or
                question_data.get("answer", []) or
                question_data.get("expected", [])
            )
        else:
            question_text = str(question_data)
            expected_answer = []
        
        if verbose:
            print(f"\n📝 Question {question_num} ({i+1}/{len(selected_questions)})")
            print(f"   Text: {question_text}")
        
        # Run agentic search
        try:
            result = qa_interface.analyze_question(question_text)
            
            # Add metadata
            result["original_question_number"] = question_num
            result["expected_answer"] = expected_answer
            result["processing_order"] = i + 1
            
            if verbose:
                predicted = result.get("predicted_answer", "No answer")
                iterations = result.get("agentic_metadata", {}).get("total_iterations", 0)
                confidence = result.get("gpt_answer_result", {}).get("confidence_score", 0.0)
                success = result.get("gpt_answer_result", {}).get("search_successful", False)
                
                print(f"   Predicted: {predicted}")
                print(f"   Success: {success}, Confidence: {confidence:.2f}, Iterations: {iterations}")
            
            results.append(result)
            
        except Exception as e:
            error_result = {
                "question": question_text,
                "original_question_number": question_num,
                "expected_answer": expected_answer,
                "processing_order": i + 1,
                "predicted_answer": None,
                "error": str(e),
                "gpt_answer_result": {
                    "search_successful": False,
                    "final_answer": None,
                    "confidence_score": 0.0
                },
                "agentic_metadata": {
                    "total_iterations": 0,
                    "search_strategy_used": "error"
                }
            }
            results.append(error_result)
            
            if verbose:
                print(f"   ❌ Error: {e}")
    
    # Close the QA interface
    qa_interface.close()
    
    # Calculate execution statistics
    end_time = time.time()
    execution_time = end_time - start_time
    
    total_questions = len(results)
    successful_searches = sum(1 for r in results 
                            if r.get("gpt_answer_result", {}).get("search_successful", False))
    answered_questions = sum(1 for r in results 
                           if r.get("predicted_answer") is not None)
    error_count = sum(1 for r in results if "error" in r)
    
    # Save results
    print(f"\n💾 Saving results...")
    saved_files = save_results(results, output_dir, question_range)
    
    # Final summary
    print(f"\n📊 EXECUTION SUMMARY")
    print("=" * 50)
    print(f"Total Questions Processed: {total_questions}")
    print(f"Successful Searches: {successful_searches} ({successful_searches/total_questions*100:.1f}%)")
    print(f"Questions with Answers: {answered_questions} ({answered_questions/total_questions*100:.1f}%)")
    print(f"Errors: {error_count}")
    print(f"Execution Time: {execution_time:.1f} seconds")
    print(f"Average Time per Question: {execution_time/total_questions:.1f} seconds")
    
    print(f"\n📁 Output Files:")
    for file_type, file_path in saved_files.items():
        print(f"  {file_type.upper()}: {file_path}")
    
    return {
        "results": results,
        "statistics": {
            "total_questions": total_questions,
            "successful_searches": successful_searches,
            "answered_questions": answered_questions,
            "error_count": error_count,
            "execution_time": execution_time,
            "success_rate": successful_searches / total_questions if total_questions > 0 else 0,
            "answer_rate": answered_questions / total_questions if total_questions > 0 else 0
        },
        "output_files": saved_files,
        "output_directory": output_dir
    }


def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(
        description="Run agentic search on a batch of questions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process questions 1-20 from questions.json
  python run_agentic_batch.py --questions data/questions.json --range 1-20 --output results/

  # Process specific questions with custom database
  python run_agentic_batch.py --questions data/questions.json --range 5,10,15-20 --output results/ --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j --neo4j-password mypassword

  # Process with verbose output disabled
  python run_agentic_batch.py --questions data/questions.json --range 1-100 --output results/ --quiet
        """
    )
    
    # Required arguments
    parser.add_argument("--questions", "-q", required=True,
                       help="Path to questions file (JSON format)")
    parser.add_argument("--range", "-r", required=True,
                       help="Question range to process (e.g., '1-20', '5,10,15', '1-10,15-20')")
    parser.add_argument("--output", "-o", required=True,
                       help="Output directory path")
    
    # Optional database arguments (with environment variable defaults)
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                       help="Neo4j database URI (default: bolt://localhost:7687 or NEO4J_URI env var)")
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", os.getenv("NEO4J_USERNAME", "neo4j")),
                       help="Neo4j username (default: neo4j or NEO4J_USER env var)")
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", "password"),
                       help="Neo4j password (default: password or NEO4J_PASSWORD env var)")
    
    # Optional arguments
    parser.add_argument("--node-embeddings",
                       help="Path to node embeddings file (optional)")
    parser.add_argument("--quiet", action="store_true",
                       help="Reduce output verbosity")
    
    args = parser.parse_args()
    
    try:
        # Run the batch processing
        execution_result = run_agentic_batch(
            questions_path=args.questions,
            question_range=args.range,
            output_path=args.output,
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password,
            node_embeddings_path=args.node_embeddings,
            verbose=not args.quiet
        )
        
        print(f"\n✅ Batch processing completed successfully!")
        print(f"Results saved to: {execution_result['output_directory']}")
        
        return 0
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️ Process interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error during batch processing: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 