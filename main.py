#!/usr/bin/env python3
"""
Main script for memory graph generation pipeline.
This script orchestrates the entire process of extracting, building, and visualizing memory graphs.
"""

import argparse
import os
from memory_graph_builder import MemoryGraphBuilder
from extract_graph_elements import extract_graph_elements
from build_graphs import build_all_graphs
from visualize_graphs import visualize_all_graphs, create_graph_summary

def run_pipeline(book_content: str, 
                graph_json_path: str = "graph_data.json", 
                graph_image_dir: str = "graphs", 
                env_path: str = ".env"):
    """
    Run the complete memory graph generation pipeline.
    
    :param book_content: Full story text from which to extract memory graphs
    :param graph_json_path: Path to save the extracted R graph & L dictionary JSON
    :param graph_image_dir: Directory to save visualizations of the graphs
    :param env_path: Path to .env file containing OpenAI API key
    """
    print("=" * 60)
    print("MEMORY GRAPH GENERATION PIPELINE")
    print("=" * 60)
    
    # Initialize the builder
    print("[INFO] Initializing MemoryGraphBuilder...")
    builder = MemoryGraphBuilder(book_content, graph_json_path, graph_image_dir, env_path)
    
    # Step 1: Extract graph elements
    print("\n[STEP 1] Extracting structured memory graphs...")
    extract_graph_elements(builder)
    
    # Step 2: Save JSON data
    print("\n[STEP 2] Saving graph data to JSON...")
    builder.save_graph_json()
    
    # Step 3: Build graphs
    print("\n[STEP 3] Building R graph and L dictionary...")
    build_all_graphs(builder)
    
    # Step 4: Visualize graphs
    print("\n[STEP 4] Visualizing graphs and displaying dictionary...")
    visualize_all_graphs(builder)
    
    # Step 5: Create summary
    print("\n[STEP 5] Creating summary...")
    create_graph_summary(builder)
    
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    
    return builder

def read_book_content(file_path: str) -> str:
    """
    Read book content from a file.
    
    :param file_path: Path to the book file
    :return: Book content as string
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"[ERROR] File not found: {file_path}")
        return None
    except Exception as e:
        print(f"[ERROR] Error reading file: {e}")
        return None

def main():
    """Main function to handle command line arguments and run the pipeline."""
    parser = argparse.ArgumentParser(description="Memory Graph Generation Pipeline")
    parser.add_argument("--book_file", "-f", type=str, 
                       help="Path to the book file (text format)")
    parser.add_argument("--book_content", "-c", type=str, 
                       help="Book content as string (alternative to --book_file)")
    parser.add_argument("--output_json", "-j", type=str, default="graph_data.json",
                       help="Path to save the extracted graph JSON (default: graph_data.json)")
    parser.add_argument("--output_dir", "-o", type=str, default="graphs",
                       help="Directory to save graph visualizations (default: graphs)")
    parser.add_argument("--env_file", "-e", type=str, default=".env",
                       help="Path to .env file (default: .env)")
    
    args = parser.parse_args()
    
    # Get book content
    if args.book_file:
        book_content = read_book_content(args.book_file)
        if book_content is None:
            return
    elif args.book_content:
        book_content = args.book_content
    else:
        print("[ERROR] Please provide either --book_file or --book_content")
        parser.print_help()
        return
    
    # Run the pipeline
    try:
        builder = run_pipeline(
            book_content=book_content,
            graph_json_path=args.output_json,
            graph_image_dir=args.output_dir,
            env_path=args.env_file
        )
        
        print(f"\n[SUCCESS] Pipeline completed!")
        print(f"  - JSON data saved to: {args.output_json}")
        print(f"  - Visualizations saved to: {args.output_dir}/")
        
    except Exception as e:
        print(f"[ERROR] Pipeline failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 