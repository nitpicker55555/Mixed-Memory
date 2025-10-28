"""
Agentic Search Engine - Main Entry Point

This is the main entry point for the refactored agentic search engine.
All functionality has been modularized for better maintainability.

Usage:
    python agentic_search_engine_refactored.py --database test9 --questions data/questions.json --range 1-10
    python agentic_search_engine_refactored.py --database mydb --single-question "What is the location of the event?"
"""

import os
import argparse

# Import environment loader first to set up environment variables
import env_loader

# Import modularized components
from search_engine_core import AgenticSearchEngine
from batch_processor import (
    parse_question_range,
    load_questions_from_file,
    run_questions_batch
)


def main():
    """Main entry point with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Agentic Search Engine - Dynamic Question Answering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agentic_search_engine_refactored.py --database test9 --questions data/questions.json --range 1-10
  python agentic_search_engine_refactored.py --database database13questions --questions /path/to/questions.json --range 5-15 --output results/
  python agentic_search_engine_refactored.py --database mydb --single-question "What is the location?"
        """
    )
    
    parser.add_argument(
        "--database",
        required=True,
        help="Neo4j database name"
    )
    
    parser.add_argument(
        "--questions",
        help="Path to questions JSON file (required for batch mode)"
    )
    
    parser.add_argument(
        "--range",
        help="Question range (e.g., '1-10' or '5') (required for batch mode)"
    )
    
    parser.add_argument(
        "--output",
        help="Output directory for results (optional)"
    )
    
    parser.add_argument(
        "--single-question",
        help="Run a single custom question (ignores --questions and --range)"
    )
    
    args = parser.parse_args()
    
    # Initialize the search engine
    engine = AgenticSearchEngine(
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "password"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        neo4j_database=args.database,
    )
    
    try:
        if args.single_question:
            # Run single custom question
            print(f"Running custom question on database '{args.database}'")
            print(f"Question: {args.single_question}")
            print("-" * 50)
            
            answer = engine.search(args.single_question)
            print(f"Answer: {answer}")
            
        else:
            # Batch mode requires questions file and range
            if not args.questions or not args.range:
                print("Error: Batch mode requires both --questions and --range arguments")
                print("Use --single-question for single question mode")
                return
            
            # Load questions and run batch
            questions = load_questions_from_file(args.questions)
            start_idx, end_idx = parse_question_range(args.range)
            
            # Validate range
            if start_idx < 1 or end_idx > len(questions):
                print(f"Error: Invalid range {start_idx}-{end_idx}. "
                      f"Questions file has {len(questions)} questions.")
                return
            
            results = run_questions_batch(engine, questions, start_idx, end_idx, args.output)
            
            # Print summary
            print(f"\nSummary:")
            print(f"   Database: {args.database}")
            print(f"   Questions: {start_idx}-{end_idx}")
            print(f"   Total time: {results['metadata']['total_duration']:.2f}s")
            successful = sum(1 for r in results['results'] if r['status'] == 'success')
            print(f"   Success rate: {successful}/{len(results['results'])}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        engine.close()


if __name__ == "__main__":
    main()

