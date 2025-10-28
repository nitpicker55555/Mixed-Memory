import json
import os
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from neo4j import GraphDatabase
from openai import OpenAI
from dotenv import load_dotenv
import logging

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
    chapter_number: int
    confidence_score: float


@dataclass
class PersonInfo:
    """Structured representation of a person entity."""
    name: str
    first_appearance_chapter: int
    description: str


@dataclass
class LocationInfo:
    """Structured representation of a location entity."""
    name: str
    first_appearance_chapter: int
    description: str


class OptimizedEventGraphGenerator:
    """
    Graph generator optimized for agentic search engine compatibility.
    
    This class implements the extraction of events and entities from narrative
    text and their transformation into a structured Neo4j graph database.
    """
    
    def __init__(self, database_name: str = "test9"):
        """
        Initialize the graph generator.
        
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
        
        # Track discovered event types dynamically
        self.discovered_event_types = set()
        self.default_event_type = "Event"

    def extract_events_from_chapter(self, chapter_text: str, 
                                    chapter_number: int) -> List[EventInfo]:
        """
        Extract detailed event information from a chapter using LLM.
        
        Args:
            chapter_text: Complete text of the chapter
            chapter_number: Chapter number for tracking purposes
            
        Returns:
            List of extracted EventInfo objects
        """
        prompt = f"""Extract events from this chapter text. Return ONLY a JSON array.

Instructions:
- Identify the most specific event type for each event (e.g., "Workshop", "Performance", "Exhibition", "Competition")
- Use natural, descriptive event types based on what actually happens in the text
- Avoid generic types like "Event" unless necessary

Chapter {chapter_number}: {chapter_text}

Return format:
[{{"name": "Event Name", "event_type": "Specific Event Type", "date": "Date or Unknown", "location": "Location", "participants": ["Person1"], "description": "Brief description", "confidence_score": 0.9}}]"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Extract events as JSON array. Return only valid JSON, no explanations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            
            # Parse and clean JSON response
            response_text = response.choices[0].message.content.strip()
            response_text = response_text.replace('```json', '').replace('```', '').strip()
            
            # Extract JSON array from response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx == -1:
                logger.warning(f"No JSON array found in response for Chapter {chapter_number}")
                return []
            
            # Handle truncated JSON responses
            if end_idx == 0:
                logger.warning(f"JSON appears truncated for Chapter {chapter_number}, attempting repair...")
                last_brace = response_text.rfind('}')
                if last_brace != -1:
                    json_str = response_text[start_idx:last_brace+1] + ']'
                else:
                    logger.error(f"Cannot repair truncated JSON for Chapter {chapter_number}")
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
                    name=event_data.get('name', f'Event in Chapter {chapter_number}') 
                         or f'Event in Chapter {chapter_number}',
                    event_type=event_type,
                    date=self._normalize_date(event_data.get('date') or 'Unknown'),
                    location=event_data.get('location', 'Unknown Location') 
                            or 'Unknown Location',
                    participants=event_data.get('participants', []) or [],
                    description=event_data.get('description', '') or '',
                    chapter_number=chapter_number,
                    confidence_score=event_data.get('confidence_score', 0.5) or 0.5
                )
                
                # Track discovered event types
                self.discovered_event_types.add(event_type)
                
                # Filter by confidence threshold
                if event.confidence_score >= 0.7:
                    events.append(event)
                    logger.info(f"Extracted event: {event.name} from Chapter {chapter_number}")
            
            return events
            
        except Exception as e:
            logger.error(f"Error extracting events from Chapter {chapter_number}: {e}")
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
        
        normalized = event_type.strip()
        
        # Standardize common event types
        type_mapping = {
            'workshop': 'Workshop',
            'workshops': 'Workshop',
            'performance': 'Performance',
            'performances': 'Performance',
            'exhibition': 'Exhibition',
            'exhibitions': 'Exhibition',
            'festival': 'Festival',
            'festivals': 'Festival',
            'hackathon': 'Hackathon',
            'hackathons': 'Hackathon',
            'competition': 'Competition',
            'competitions': 'Competition',
            'tournament': 'Tournament',
            'tournaments': 'Tournament',
            'gathering': 'Gathering',
            'gatherings': 'Gathering',
            'meeting': 'Gathering',
            'meetings': 'Gathering'
        }
        
        lower_type = normalized.lower()
        if lower_type in type_mapping:
            return type_mapping[lower_type]
        
        # Default: capitalize each word
        return ' '.join(word.capitalize() for word in normalized.split())

    def _normalize_date(self, date_str: str) -> str:
        """
        Normalize date string to expected format.
        
        The search engine expects dates in the format 'Month Day, Year'
        (e.g., 'March 23, 2024').
        
        Args:
            date_str: Raw date string
            
        Returns:
            Normalized date string or empty string if unknown
        """
        if date_str == "Unknown" or not date_str:
            return ""
        
        # Try to match various date formats
        date_patterns = [
            r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',     # March 23, 2024
            r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})',  # 03/23/2024
            r'(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})',  # 2024/03/23
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, date_str)
            if match:
                return date_str  # Keep original if already in good format
        
        return date_str

    def extract_entities_from_chapter(self, chapter_text: str, 
                                     chapter_number: int) -> Tuple[List[PersonInfo], List[LocationInfo]]:
        """
        Extract person and location entities from chapter text.
        
        Args:
            chapter_text: Complete text of the chapter
            chapter_number: Chapter number for tracking purposes
            
        Returns:
            Tuple of (persons list, locations list)
        """
        chunk_size = 4000
        all_persons = {}
        all_locations = {}
        
        # Process text in chunks to avoid token limits
        for i in range(0, len(chapter_text), chunk_size):
            chunk = chapter_text[i:i + chunk_size]
            chunk_num = i // chunk_size + 1
            
            prompt = f"""Extract persons and locations from this text chunk. Return JSON only.

Chunk {chunk_num}: {chunk}

Format: {{"persons": [{{"name": "Full Name", "description": "Role or description"}}], "locations": [{{"name": "Place Name", "description": "Type of place"}}]}}"""
        
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Extract person and location entities. Return valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=1500
                )
                
                # Parse and clean JSON response
                response_text = response.choices[0].message.content.strip()
                response_text = response_text.replace('```json', '').replace('```', '').strip()
                
                # Extract JSON object from response
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                
                if start_idx == -1:
                    logger.warning(f"No JSON object found in chunk {chunk_num} for Chapter {chapter_number}")
                    continue
                
                # Handle truncated JSON
                if end_idx == 0:
                    logger.warning(f"JSON appears truncated for entities in chunk {chunk_num}")
                    last_bracket = response_text.rfind(']')
                    if last_bracket != -1:
                        remaining = response_text[last_bracket:]
                        brace_pos = remaining.find('}')
                        if brace_pos != -1:
                            json_str = response_text[start_idx:last_bracket + brace_pos + 1]
                        else:
                            json_str = response_text[start_idx:last_bracket] + ']}'
                    else:
                        logger.error(f"Cannot repair truncated JSON for entities in chunk {chunk_num}")
                        continue
                else:
                    json_str = response_text[start_idx:end_idx]
                
                entities_data = json.loads(json_str)
                
                # Collect persons (avoid duplicates)
                for p in entities_data.get('persons', []):
                    name = p.get('name')
                    if name and name not in all_persons:
                        all_persons[name] = PersonInfo(
                            name=name,
                            first_appearance_chapter=chapter_number,
                            description=p.get('description', '') or ''
                        )
                
                # Collect locations (avoid duplicates)
                for l in entities_data.get('locations', []):
                    name = l.get('name')
                    if name and name not in all_locations:
                        all_locations[name] = LocationInfo(
                            name=name,
                            first_appearance_chapter=chapter_number,
                            description=l.get('description', '') or ''
                        )
                        
            except Exception as e:
                logger.warning(f"Error extracting entities from chunk {chunk_num} in Chapter {chapter_number}: {e}")
                continue
        
        return list(all_persons.values()), list(all_locations.values())

    def process_book_data(self, book_json_path: str) -> None:
        """
        Process the entire book and extract all events and entities.
        
        Args:
            book_json_path: Path to the book JSON file
        """
        logger.info("Starting book data processing...")
        
        with open(book_json_path, 'r', encoding='utf-8') as f:
            book_text = f.read().strip('"')  # Remove surrounding quotes if present
        
        # Split into chapters
        chapters = self._split_into_chapters(book_text)
        
        for chapter_num, chapter_text in enumerate(chapters, 1):
            logger.info(f"Processing Chapter {chapter_num}...")
            
            # Extract events
            events = self.extract_events_from_chapter(chapter_text, chapter_num)
            self.events_cache.extend(events)
            
            # Extract persons and locations
            persons, locations = self.extract_entities_from_chapter(chapter_text, chapter_num)
            
            # Update entity caches (avoid duplicates)
            for person in persons:
                if person.name not in self.persons_cache:
                    self.persons_cache[person.name] = person
            
            for location in locations:
                if location.name not in self.locations_cache:
                    self.locations_cache[location.name] = location
        
        logger.info(f"Extraction complete: {len(self.events_cache)} events, "
                   f"{len(self.persons_cache)} persons, {len(self.locations_cache)} locations")
        if self.discovered_event_types:
            logger.info(f"Discovered event types: {sorted(self.discovered_event_types)}")

    def _split_into_chapters(self, book_text: str) -> List[str]:
        """
        Split book text into individual chapters.
        
        Args:
            book_text: Complete book text
            
        Returns:
            List of chapter texts
        """
        chapters = re.split(r'\n\n(?=Chapter \d+)', book_text)
        chapters = [chapter.strip() for chapter in chapters if chapter.strip()]
        return chapters

    def create_graph(self) -> None:
        """
        Create the Neo4j knowledge graph from cached entities.
        
        This method creates nodes for events, persons, and locations, along with
        their relationships. It also establishes database constraints and indexes
        for optimal query performance.
        """
        logger.info(f"Creating graph in database: {self.database_name}")
        
        with self.driver.session(database=self.database_name) as session:
            # Clear existing data
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Cleared existing graph data")
            
            # Create constraints and indexes
            self._create_constraints_and_indexes(session)
            
            # Create nodes
            self._create_event_nodes(session)
            self._create_person_nodes(session)
            self._create_location_nodes(session)
            
            # Create relationships
            self._create_relationships(session)
            
        logger.info("Graph creation complete")

    def _create_constraints_and_indexes(self, session) -> None:
        """Create database constraints and indexes for performance optimization."""
        constraints = [
            "CREATE CONSTRAINT event_name_unique IF NOT EXISTS FOR (e:Event) REQUIRE e.name IS UNIQUE",
            "CREATE CONSTRAINT person_name_unique IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE", 
            "CREATE CONSTRAINT location_name_unique IF NOT EXISTS FOR (l:Location) REQUIRE l.name IS UNIQUE"
        ]
        
        indexes = [
            "CREATE INDEX event_type_index IF NOT EXISTS FOR (e:Event) ON (e.event_type)",
            "CREATE INDEX event_date_index IF NOT EXISTS FOR (e:Event) ON (e.date)",
            "CREATE INDEX event_location_index IF NOT EXISTS FOR (e:Event) ON (e.location)"
        ]
        
        for constraint in constraints:
            try:
                session.run(constraint)
            except Exception as e:
                logger.warning(f"Constraint creation warning: {e}")
        
        for index in indexes:
            try:
                session.run(index)
            except Exception as e:
                logger.warning(f"Index creation warning: {e}")

    def _create_event_nodes(self, session) -> None:
        """Create Event nodes with all required properties."""
        logger.info("Creating Event nodes...")
        
        for event in self.events_cache:
            participants = event.participants if event.participants else []
            
            session.run("""
                CREATE (e:Event {
                    name: $name,
                    event_type: $event_type,
                    date: $date,
                    location: $location,
                    participants: $participants,
                    description: $description,
                    chapter_number: $chapter_number,
                    confidence_score: $confidence_score
                })
            """, 
                name=event.name,
                event_type=event.event_type,
                date=event.date,
                location=event.location,
                participants=participants,
                description=event.description,
                chapter_number=event.chapter_number,
                confidence_score=event.confidence_score
            )
        
        logger.info(f"Created {len(self.events_cache)} Event nodes")

    def _create_person_nodes(self, session) -> None:
        """Create Person nodes."""
        logger.info("Creating Person nodes...")
        
        for person in self.persons_cache.values():
            session.run("""
                CREATE (p:Person {
                    name: $name,
                    first_appearance_chapter: $first_appearance_chapter,
                    description: $description
                })
            """,
                name=person.name,
                first_appearance_chapter=person.first_appearance_chapter,
                description=person.description
            )
        
        logger.info(f"Created {len(self.persons_cache)} Person nodes")

    def _create_location_nodes(self, session) -> None:
        """Create Location nodes."""
        logger.info("Creating Location nodes...")
        
        for location in self.locations_cache.values():
            session.run("""
                CREATE (l:Location {
                    name: $name,
                    first_appearance_chapter: $first_appearance_chapter,
                    description: $description
                })
            """,
                name=location.name,
                first_appearance_chapter=location.first_appearance_chapter,
                description=location.description
            )
        
        logger.info(f"Created {len(self.locations_cache)} Location nodes")

    def _create_relationships(self, session) -> None:
        """Create relationships between nodes."""
        logger.info("Creating relationships...")
        
        # Create PARTICIPATED_IN relationships
        for event in self.events_cache:
            for participant in event.participants:
                session.run("""
                    MATCH (p:Person {name: $person_name})
                    MATCH (e:Event {name: $event_name})
                    MERGE (p)-[:PARTICIPATED_IN]->(e)
                """,
                    person_name=participant,
                    event_name=event.name
                )
        
        # Create OCCURRED_AT relationships
        for event in self.events_cache:
            if event.location and event.location != "Unknown Location":
                session.run("""
                    MATCH (e:Event {name: $event_name})
                    MATCH (l:Location {name: $location_name})
                    MERGE (e)-[:OCCURRED_AT]->(l)
                """,
                    event_name=event.name,
                    location_name=event.location
                )
        
        logger.info("Relationships created successfully")

    def save_property_keys(self) -> None:
        """Save property keys cache file for search engine integration."""
        cache_dir = "/Users/yunanli/Desktop/MasterThesisNew/AgenticSearch/cache"
        os.makedirs(cache_dir, exist_ok=True)
        
        property_keys = {
            "Event": ["name", "event_type", "date", "location", "participants", 
                     "description", "chapter_number", "confidence_score"],
            "Person": ["name", "first_appearance_chapter", "description"],
            "Location": ["name", "first_appearance_chapter", "description"]
        }
        
        cache_file = f"{cache_dir}/propertykey_{self.database_name}.json"
        with open(cache_file, 'w') as f:
            json.dump(property_keys, f, indent=2)
        
        logger.info(f"Property keys saved to {cache_file}")

    def generate_statistics(self) -> Dict[str, Any]:
        """
        Generate comprehensive statistics about the created graph.
        
        Returns:
            Dictionary containing node counts, relationship counts, and 
            event type distribution
        """
        with self.driver.session(database=self.database_name) as session:
            stats = {}
            
            # Count nodes by label
            result = session.run("MATCH (n) RETURN labels(n) as labels, count(n) as count")
            for record in result:
                label = record["labels"][0] if record["labels"] else "Unknown"
                stats[f"{label}_nodes"] = record["count"]
            
            # Count relationships by type
            result = session.run("MATCH ()-[r]->() RETURN type(r) as type, count(r) as count")
            for record in result:
                stats[f"{record['type']}_relationships"] = record["count"]
            
            # Event type distribution
            result = session.run(
                "MATCH (e:Event) RETURN e.event_type, count(*) as count ORDER BY count DESC"
            )
            event_types = {}
            for record in result:
                event_types[record["e.event_type"]] = record["count"]
            stats["event_type_distribution"] = event_types
            
            return stats

    def close(self) -> None:
        """Close database connection."""
        self.driver.close()


def main():
    """Main function for standalone execution."""
    logger.info("Starting Optimized Event Graph Generation")
    
    generator = OptimizedEventGraphGenerator("test9")
    
    try:
        # Process book data
        book_path = "/Users/yunanli/Desktop/MasterThesisNew/AgenticSearch/data/book.json"
        generator.process_book_data(book_path)
        
        # Create graph
        generator.create_graph()
        generator.save_property_keys()
        
        # Display statistics
        stats = generator.generate_statistics()
        logger.info("Graph Generation Statistics:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
        
        logger.info("Graph generation completed successfully")
        
    except Exception as e:
        logger.error(f"Error during graph generation: {e}")
        raise
    finally:
        generator.close()


if __name__ == "__main__":
    main()
