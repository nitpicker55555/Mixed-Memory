"""
Dynamic Graph Generator for Agentic Search Engine

This module provides functionality to generate Neo4j knowledge graphs from textual
narratives. It orchestrates the event extraction and embedding generation processes.

Usage:
    python dynamic_graph_generator.py --book-path <path> --database <name>
    python dynamic_graph_generator.py --book-path data/book.json --database test_db

Author: Yunan Li
Master Thesis Project - Agentic Search Engine
"""

import argparse
import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from optimized_event_graph_generator import OptimizedEventGraphGenerator
from embedding_generator import EmbeddingGenerator
import logging
import time
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_inputs(book_path: str, database_name: str) -> None:
    """
    Validate input parameters before processing.
    
    Args:
        book_path: Path to the book JSON file
        database_name: Name of the Neo4j database
        
    Raises:
        FileNotFoundError: If book file does not exist
        PermissionError: If book file is not readable
        ValueError: If database name is invalid
    """
    # Check file existence and readability
    if not os.path.exists(book_path):
        raise FileNotFoundError(f"Book file not found: {book_path}")
    
    if not os.access(book_path, os.R_OK):
        raise PermissionError(f"Cannot read book file: {book_path}")
    
    # Validate database name
    if not database_name or not database_name.strip():
        raise ValueError("Database name cannot be empty")
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', database_name):
        raise ValueError(
            "Database name can only contain letters, numbers, underscores, and hyphens"
        )
    
    logger.info(f"Input validation successful: book={book_path}, database={database_name}")


def analyze_book_content(book_path: str) -> dict:
    """
    Analyze the book content to provide preprocessing insights.
    
    Args:
        book_path: Path to the book JSON file
        
    Returns:
        Dictionary containing analysis results including file size, chapter count,
        and estimated processing time
    """
    try:
        with open(book_path, 'r', encoding='utf-8') as f:
            content = f.read().strip('"')
        
        # Extract basic statistics
        total_chars = len(content)
        chapters = re.findall(r'Chapter \d+', content)
        num_chapters = len(chapters)
        
        # Estimate processing time (approximate: 15 seconds per chapter)
        estimated_time = num_chapters * 15
        
        analysis = {
            "file_size_kb": round(os.path.getsize(book_path) / 1024, 1),
            "total_characters": total_chars,
            "num_chapters": num_chapters,
            "estimated_time_seconds": estimated_time,
            "chapters_found": chapters[:5] if len(chapters) > 5 else chapters
        }
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing book content: {e}")
        return {"error": str(e)}


def generate_graph(book_path: str, database_name: str, verbose: bool = True) -> dict:
    """
    Generate complete knowledge graph with embeddings.
    
    This function orchestrates the entire graph generation pipeline:
    1. Extract events and entities from book content
    2. Create Neo4j graph structure
    3. Generate embeddings for semantic search
    
    Args:
        book_path: Path to the book JSON file
        database_name: Name of the Neo4j database
        verbose: Whether to display detailed progress information
        
    Returns:
        Dictionary containing generation statistics including node counts,
        relationship counts, and processing time
    """
    start_time = time.time()
    
    if verbose:
        logger.info("=" * 70)
        logger.info("DYNAMIC GRAPH GENERATION STARTED")
        logger.info("=" * 70)
        logger.info(f"Book: {book_path}")
        logger.info(f"Database: {database_name}")
    
    # Perform content analysis
    analysis = analyze_book_content(book_path)
    if "error" not in analysis and verbose:
        logger.info(f"Book Analysis:")
        logger.info(f"  File size: {analysis['file_size_kb']} KB")
        logger.info(f"  Chapters: {analysis['num_chapters']}")
        logger.info(f"  Estimated time: {analysis['estimated_time_seconds']} seconds")
        logger.info(f"  Chapter sample: {', '.join(analysis['chapters_found'])}")
    
    # Initialize graph generator
    generator = OptimizedEventGraphGenerator(database_name)
    
    try:
        # Step 1: Process book data and extract entities
        if verbose:
            logger.info("\n" + "=" * 50)
            logger.info("STEP 1: PROCESSING BOOK DATA")
            logger.info("=" * 50)
        
        generator.process_book_data(book_path)
        
        extraction_stats = {
            "events": len(generator.events_cache),
            "persons": len(generator.persons_cache),
            "locations": len(generator.locations_cache),
            "event_types": sorted(generator.discovered_event_types) 
                          if generator.discovered_event_types else []
        }
        
        if verbose:
            logger.info(f"Extraction complete:")
            logger.info(f"  Events: {extraction_stats['events']}")
            logger.info(f"  Persons: {extraction_stats['persons']}")
            logger.info(f"  Locations: {extraction_stats['locations']}")
            logger.info(f"  Event types: {len(extraction_stats['event_types'])}")
            if extraction_stats['event_types']:
                logger.info(f"  Discovered types: {', '.join(extraction_stats['event_types'])}")
        
        # Step 2: Create Neo4j graph
        if verbose:
            logger.info("\n" + "=" * 50)
            logger.info("STEP 2: CREATING NEO4J GRAPH")
            logger.info("=" * 50)
        
        generator.create_graph()
        generator.save_property_keys()
        
        # Step 3: Generate embeddings for semantic search
        if verbose:
            logger.info("\n" + "=" * 50)
            logger.info("STEP 3: GENERATING EMBEDDINGS")
            logger.info("=" * 50)
        
        embedding_generator = EmbeddingGenerator(database_name)
        embedding_generator.process_all_nodes()
        embedding_generator.save_embeddings_to_cache()
        
        embedding_stats = embedding_generator.generate_statistics()
        embedding_generator.close()
        
        # Compile final statistics
        graph_stats = generator.generate_statistics()
        
        final_stats = {
            "extraction": extraction_stats,
            "graph": graph_stats,
            "embeddings": embedding_stats,
            "processing_time": time.time() - start_time,
            "database_name": database_name,
            "book_path": book_path
        }
        
        if verbose:
            logger.info("\n" + "=" * 70)
            logger.info("GRAPH GENERATION COMPLETED SUCCESSFULLY")
            logger.info("=" * 70)
            logger.info(f"Total time: {final_stats['processing_time']:.2f} seconds")
            
            # Display comprehensive statistics
            print("\n" + "=" * 70)
            print("FINAL STATISTICS")
            print("=" * 70)
            
            print(f"\nSource:")
            print(f"  Book: {os.path.basename(book_path)}")
            print(f"  Database: {database_name}")
            
            print(f"\nNodes Created:")
            for key, value in graph_stats.items():
                if key.endswith('_nodes'):
                    label = key.replace('_nodes', '').title()
                    print(f"  {label}: {value}")
            
            print(f"\nRelationships Created:")
            for key, value in graph_stats.items():
                if key.endswith('_relationships'):
                    rel_type = key.replace('_relationships', '').replace('_', ' ').title()
                    print(f"  {rel_type}: {value}")
            
            if 'event_type_distribution' in graph_stats:
                print(f"\nEvent Type Distribution:")
                for event_type, count in graph_stats['event_type_distribution'].items():
                    print(f"  - {event_type}: {count}")
            
            print(f"\nEmbeddings:")
            if 'total_embeddings' in embedding_stats:
                print(f"  Total: {embedding_stats['total_embeddings']}")
                print(f"  Dimension: {embedding_stats.get('embedding_dimension', 'N/A')}")
            
            print(f"\nCache Files Generated:")
            print(f"  - propertykey_{database_name}.json")
            print(f"  - embeddings_{database_name}.json")
            print(f"  - embeddings_{database_name}.npz")
            
            print(f"\nReady for Search Engine:")
            print(f"  cd src/question_answering")
            print(f"  python run_agentic_batch.py --database {database_name}")
            
            print("=" * 70)
        
        return final_stats
        
    except Exception as e:
        logger.error(f"Graph generation failed: {e}")
        raise
    finally:
        generator.close()


def main():
    """Main entry point for command-line execution."""
    parser = argparse.ArgumentParser(
        description="Dynamic Graph Generator for Agentic Search Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dynamic_graph_generator.py --book-path data/book.json --database test_db
  python dynamic_graph_generator.py --book-path /path/to/book.json --database my_graph --quiet
        """
    )
    
    parser.add_argument(
        "--book-path",
        required=True,
        help="Path to the book JSON file"
    )
    
    parser.add_argument(
        "--database",
        required=True,
        help="Neo4j database name"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output (only errors and final statistics)"
    )
    
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate inputs and analyze book content without generating graph"
    )
    
    args = parser.parse_args()
    
    try:
        # Validate inputs
        validate_inputs(args.book_path, args.database)
        
        if args.validate_only:
            analysis = analyze_book_content(args.book_path)
            print(f"Validation successful!")
            print(f"Book analysis: {analysis}")
            return
        
        # Generate graph
        stats = generate_graph(
            book_path=args.book_path,
            database_name=args.database,
            verbose=not args.quiet
        )
        
        if args.quiet:
            print(f"Graph generated successfully for database '{args.database}'")
            print(f"Statistics: {stats['extraction']['events']} events, "
                  f"{stats['extraction']['persons']} persons, "
                  f"{stats['extraction']['locations']} locations")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
