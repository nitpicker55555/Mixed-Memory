"""
Sentence-Level Graph Generator for Agentic Search Engine

This module implements an alternative graph generation approach that processes
text at the sentence level rather than chapter level. This fine-grained approach
may improve event localization at the cost of increased processing time.

Usage:
    python graph_gen_sentence.py --book-path <path> --database <name>
    python graph_gen_sentence.py --book-path data/book.json --database sentence_db

Author: Yunan Li
Master Thesis Project - Agentic Search Engine
"""

import argparse
import sys
import os
import re
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from embedding_generator import EmbeddingGenerator
import logging
import time
import json
from typing import List, Dict
from dataclasses import dataclass
from neo4j import GraphDatabase
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class EventInfo:
    """Structured representation of an extracted event."""
    name: str
    event_type: str
    date: str
    location: str
    participants: List[str]
    description: str
    sentence_number: int  # Sentence-level tracking instead of chapter-level
    confidence_score: float


class SentenceLevelGraphGenerator:
    """
    Graph generator that processes text sentence by sentence.
    
    This approach provides finer granularity in event localization compared
    to chapter-level processing, potentially improving retrieval precision.
    """
    
    def __init__(self, database_name: str = "13chaptersentence"):
        """
        Initialize the sentence-level graph generator.
        
        Args:
            database_name: Name of the target Neo4j database
        """
        self.database_name = database_name
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Establish Neo4j connection
        self.driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI'),
            auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
        )
        
        # Initialize entity caches
        self.events_cache = []
        self.persons_cache = {}
        self.locations_cache = {}
        
        # Track discovered event types
        self.discovered_event_types = set()
        self.default_event_type = "Event"
    
    def split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using regex-based sentence boundary detection.
        
        Args:
            text: Complete book text
            
        Returns:
            List of sentence strings
        """
        # Remove chapter headers
        text = re.sub(r'Chapter \d+\n+', '', text)
        
        # Split by sentence-ending punctuation
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Filter out very short sentences (likely artifacts)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        return sentences
    
    def extract_events_from_sentence(self, sentence: str, 
                                    sentence_number: int) -> List[EventInfo]:
        """
        Extract event information from a single sentence using LLM.
        
        Args:
            sentence: Single sentence text
            sentence_number: Sentence number for tracking purposes
            
        Returns:
            List of extracted EventInfo objects
        """
        prompt = f"""Extract events from this sentence. Return ONLY a JSON array.

If no event is mentioned, return an empty array [].

Sentence {sentence_number}: {sentence}

Return format:
[{{"name": "Event Name", "event_type": "Specific Event Type", "date": "Date or Unknown", "location": "Location", "participants": ["Person1"], "description": "Brief description", "confidence_score": 0.9}}]"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Use lightweight model for sentence-level processing
                messages=[
                    {"role": "system", "content": "Extract events as JSON array. Return only valid JSON, no explanations. If no event, return []."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500  # Reduced token limit for sentence-level processing
            )
            
            # Parse and clean JSON response
            response_text = response.choices[0].message.content.strip()
            response_text = response_text.replace('```json', '').replace('```', '').strip()
            
            # Extract JSON array from response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx == -1:
                return []
            
            # Handle truncated JSON
            if end_idx == 0:
                last_brace = response_text.rfind('}')
                if last_brace != -1:
                    json_str = response_text[start_idx:last_brace+1] + ']'
                else:
                    return []
            else:
                json_str = response_text[start_idx:end_idx]
            
            events_data = json.loads(json_str)
            
            # Process extracted events
            events = []
            for event_data in events_data:
                event_type = self._normalize_event_type(
                    event_data.get('event_type') or self.default_event_type
                )
                
                event = EventInfo(
                    name=event_data.get('name', f'Event in Sentence {sentence_number}') 
                         or f'Event in Sentence {sentence_number}',
                    event_type=event_type,
                    date=self._normalize_date(event_data.get('date') or 'Unknown'),
                    location=event_data.get('location', 'Unknown Location') 
                            or 'Unknown Location',
                    participants=event_data.get('participants', []) or [],
                    description=event_data.get('description', '') or '',
                    sentence_number=sentence_number,
                    confidence_score=event_data.get('confidence_score', 0.5) or 0.5
                )
                
                self.discovered_event_types.add(event_type)
                
                # Filter by confidence threshold
                if event.confidence_score >= 0.7:
                    events.append(event)
                    logger.info(f"Extracted event: {event.name} from Sentence {sentence_number}")
            
            return events
            
        except Exception as e:
            logger.error(f"Error extracting events from Sentence {sentence_number}: {e}")
            return []
    
    def _normalize_event_type(self, event_type: str) -> str:
        """
        Normalize event type string for consistency.
        
        Args:
            event_type: Raw event type string
            
        Returns:
            Normalized event type
        """
        if not event_type or event_type.strip() == "":
            return self.default_event_type
        return event_type.strip().title()
    
    def _normalize_date(self, date_str: str) -> str:
        """
        Normalize date format.
        
        Args:
            date_str: Raw date string
            
        Returns:
            Normalized date string or 'Unknown' if invalid
        """
        if not date_str or date_str.strip().lower() in ['unknown', 'none', '']:
            return 'Unknown'
        return date_str.strip()
    
    def process_book_data(self, book_path: str):
        """
        Process book data sentence by sentence.
        
        This method splits the book into sentences and extracts events and
        entities from each sentence individually.
        
        Args:
            book_path: Path to the book JSON file
        """
        logger.info("Loading book data...")
        
        with open(book_path, 'r', encoding='utf-8') as f:
            book_text = f.read().strip('"')  # Remove surrounding quotes if present
        
        # Split into sentences
        sentences = self.split_into_sentences(book_text)
        total_sentences = len(sentences)
        
        logger.info(f"Split book into {total_sentences} sentences")
        logger.info("Starting sentence-by-sentence event extraction...")
        
        # Process each sentence
        for idx, sentence in enumerate(sentences, 1):
            logger.info(f"Processing sentence {idx}/{total_sentences}...")
            
            events = self.extract_events_from_sentence(sentence, idx)
            self.events_cache.extend(events)
            
            # Extract persons and locations from events
            for event in events:
                # Add persons
                for person_name in event.participants:
                    if person_name not in self.persons_cache:
                        self.persons_cache[person_name] = {
                            'name': person_name,
                            'first_appearance_sentence': event.sentence_number,
                            'description': f'Participant in {event.name}'
                        }
                
                # Add location
                if event.location != 'Unknown Location':
                    if event.location not in self.locations_cache:
                        self.locations_cache[event.location] = {
                            'name': event.location,
                            'first_appearance_sentence': event.sentence_number,
                            'description': f'Location of {event.name}'
                        }
            
            # Progress update every 100 sentences
            if idx % 100 == 0:
                logger.info(f"Progress: {idx}/{total_sentences} sentences, "
                          f"{len(self.events_cache)} events found so far")
        
        logger.info(f"Extraction complete: {len(self.events_cache)} events, "
                   f"{len(self.persons_cache)} persons, {len(self.locations_cache)} locations")
    
    def create_graph(self):
        """
        Create Neo4j graph from cached entities.
        
        This method creates nodes and relationships based on the extracted
        events, persons, and locations.
        """
        logger.info("Creating Neo4j graph...")
        
        with self.driver.session(database=self.database_name) as session:
            # Clear existing data
            logger.info("Clearing existing graph data...")
            session.run("MATCH (n) DETACH DELETE n")
            
            # Create Event nodes
            logger.info(f"Creating {len(self.events_cache)} Event nodes...")
            for event in self.events_cache:
                session.run("""
                    CREATE (e:Event {
                        name: $name,
                        event_type: $event_type,
                        date: $date,
                        location: $location,
                        participants: $participants,
                        description: $description,
                        sentence_number: $sentence_number,
                        confidence_score: $confidence_score
                    })
                """, 
                name=event.name,
                event_type=event.event_type,
                date=event.date,
                location=event.location,
                participants=event.participants,
                description=event.description,
                sentence_number=event.sentence_number,
                confidence_score=event.confidence_score
                )
            
            # Create Person nodes
            logger.info(f"Creating {len(self.persons_cache)} Person nodes...")
            for person_data in self.persons_cache.values():
                session.run("""
                    CREATE (p:Person {
                        name: $name,
                        first_appearance_sentence: $first_appearance_sentence,
                        description: $description
                    })
                """,
                name=person_data['name'],
                first_appearance_sentence=person_data['first_appearance_sentence'],
                description=person_data['description']
                )
            
            # Create Location nodes
            logger.info(f"Creating {len(self.locations_cache)} Location nodes...")
            for location_data in self.locations_cache.values():
                session.run("""
                    CREATE (l:Location {
                        name: $name,
                        first_appearance_sentence: $first_appearance_sentence,
                        description: $description
                    })
                """,
                name=location_data['name'],
                first_appearance_sentence=location_data['first_appearance_sentence'],
                description=location_data['description']
                )
            
            # Create relationships
            logger.info("Creating relationships...")
            
            # PARTICIPATED_IN relationships
            session.run("""
                MATCH (e:Event), (p:Person)
                WHERE p.name IN e.participants
                CREATE (p)-[:PARTICIPATED_IN]->(e)
            """)
            
            # LOCATED_AT relationships
            session.run("""
                MATCH (e:Event), (l:Location)
                WHERE e.location = l.name
                CREATE (e)-[:LOCATED_AT]->(l)
            """)
        
        logger.info("Graph creation complete")
    
    def save_property_keys(self):
        """Save property keys to cache file for search engine integration."""
        cache_dir = "cache"
        os.makedirs(cache_dir, exist_ok=True)
        
        property_keys = {
            'Event': ['name', 'event_type', 'date', 'location', 'participants', 
                     'description', 'sentence_number', 'confidence_score'],
            'Person': ['name', 'first_appearance_sentence', 'description'],
            'Location': ['name', 'first_appearance_sentence', 'description']
        }
        
        output_file = os.path.join(cache_dir, f"propertykey_{self.database_name}.json")
        with open(output_file, 'w') as f:
            json.dump(property_keys, f, indent=2)
        
        logger.info(f"Property keys saved to {output_file}")
    
    def generate_statistics(self) -> Dict:
        """
        Generate statistics about the created graph.
        
        Returns:
            Dictionary containing node and relationship counts
        """
        with self.driver.session(database=self.database_name) as session:
            stats = {}
            
            # Count nodes by type
            result = session.run("MATCH (e:Event) RETURN count(e) as count")
            stats['event_nodes'] = result.single()['count']
            
            result = session.run("MATCH (p:Person) RETURN count(p) as count")
            stats['person_nodes'] = result.single()['count']
            
            result = session.run("MATCH (l:Location) RETURN count(l) as count")
            stats['location_nodes'] = result.single()['count']
            
            # Count relationships by type
            result = session.run("MATCH ()-[r:PARTICIPATED_IN]->() RETURN count(r) as count")
            stats['participated_in_relationships'] = result.single()['count']
            
            result = session.run("MATCH ()-[r:LOCATED_AT]->() RETURN count(r) as count")
            stats['located_at_relationships'] = result.single()['count']
            
            return stats
    
    def close(self):
        """Close database connection."""
        self.driver.close()


def generate_graph_sentence_level(book_path: str, database_name: str, 
                                  verbose: bool = True) -> Dict:
    """
    Generate graph using sentence-level processing.
    
    Args:
        book_path: Path to the book JSON file
        database_name: Name of the Neo4j database
        verbose: Whether to display detailed progress information
        
    Returns:
        Dictionary containing generation statistics
    """
    start_time = time.time()
    
    if verbose:
        logger.info("=" * 70)
        logger.info("SENTENCE-LEVEL GRAPH GENERATION STARTED")
        logger.info("=" * 70)
        logger.info(f"Book: {book_path}")
        logger.info(f"Database: {database_name}")
    
    generator = SentenceLevelGraphGenerator(database_name)
    
    try:
        # Step 1: Process book data sentence by sentence
        if verbose:
            logger.info("\n" + "=" * 50)
            logger.info("STEP 1: PROCESSING BOOK DATA (SENTENCE BY SENTENCE)")
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
        
        # Step 2: Create graph
        if verbose:
            logger.info("\n" + "=" * 50)
            logger.info("STEP 2: CREATING NEO4J GRAPH")
            logger.info("=" * 50)
        
        generator.create_graph()
        generator.save_property_keys()
        
        # Step 3: Generate embeddings
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
            "book_path": book_path,
            "processing_mode": "sentence-level"
        }
        
        if verbose:
            logger.info("\n" + "=" * 70)
            logger.info("SENTENCE-LEVEL GRAPH GENERATION COMPLETED")
            logger.info("=" * 70)
            logger.info(f"Total time: {final_stats['processing_time']:.2f} seconds")
            logger.info(f"Events: {graph_stats['event_nodes']}")
            logger.info(f"Persons: {graph_stats['person_nodes']}")
            logger.info(f"Locations: {graph_stats['location_nodes']}")
            logger.info(f"Embeddings: {embedding_stats.get('total_embeddings', 0)}")
            logger.info("=" * 70)
        
        return final_stats
        
    except Exception as e:
        logger.error(f"Graph generation failed: {e}")
        raise
    finally:
        generator.close()


def main():
    """Main entry point for command-line execution."""
    parser = argparse.ArgumentParser(
        description="Sentence-Level Graph Generator for Agentic Search Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python graph_gen_sentence.py --book-path data/book.json --database sentence_db
  python graph_gen_sentence.py --book-path /path/to/book.json --database test --quiet
        """
    )
    
    parser.add_argument(
        "--book-path",
        required=True,
        help="Path to the book JSON file"
    )
    
    parser.add_argument(
        "--database",
        default="13chaptersentence",
        help="Neo4j database name (default: 13chaptersentence)"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output"
    )
    
    args = parser.parse_args()
    
    try:
        # Generate graph
        stats = generate_graph_sentence_level(
            book_path=args.book_path,
            database_name=args.database,
            verbose=not args.quiet
        )
        
        if args.quiet:
            print(f"Graph generated successfully for database '{args.database}'")
            print(f"Statistics: {stats['extraction']['events']} events, "
                  f"{stats['extraction']['persons']} persons, "
                  f"{stats['extraction']['locations']} locations")
            print(f"Time: {stats['processing_time']:.2f} seconds")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
