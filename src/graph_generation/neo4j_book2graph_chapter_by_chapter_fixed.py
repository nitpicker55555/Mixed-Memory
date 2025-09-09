#!/usr/bin/env python3
"""
Chapter-by-Chapter Book to Neo4j Graph Converter
Processes book chapters individually and updates the graph database incrementally
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Tuple
from openai import OpenAI
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
BOOK_JSON_PATH = os.path.join(PROJECT_ROOT, "data", "book.json")

# Neo4j Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "test10")

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

print(f"Script directory: {SCRIPT_DIR}")
print(f"Project root: {PROJECT_ROOT}")
print(f"Book JSON path: {BOOK_JSON_PATH}")
print(f"Book file exists: {os.path.exists(BOOK_JSON_PATH)}")

# Initialize OpenAI client
try:
    client = OpenAI(api_key=OPENAI_API_KEY)
    print("✅ OpenAI client initialized successfully")
except Exception as e:
    print(f"❌ Error initializing OpenAI client: {e}")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
    if OPENAI_BASE_URL:
        try:
            client = OpenAI(
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL
            )
            print("✅ OpenAI client initialized with custom base URL")
        except Exception as e2:
            print(f"❌ Error with custom URL: {e2}")
            raise e2
    else:
        raise e

# Initialize Neo4j driver
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def split_book_into_chapters(text: str) -> List[Tuple[str, str]]:
    """Split book text into individual chapters"""
    chapters = []
    
    # Split by "Chapter" followed by a number
    chapter_pattern = r'Chapter\s+(\d+)'
    splits = re.split(chapter_pattern, text)
    
    if len(splits) > 1:
        # Remove the first empty split if it exists
        if splits[0].strip() == "":
            splits = splits[1:]
        
        # Group chapter numbers with their content
        for i in range(0, len(splits) - 1, 2):
            if i + 1 < len(splits):
                chapter_num = splits[i].strip()
                chapter_content = splits[i + 1].strip()
                if chapter_content:
                    chapters.append((f"Chapter {chapter_num}", chapter_content))
    
    print(f"📄 Split book into {len(chapters)} chapters")
    return chapters

def extract_graph_from_text(text: str, chapter_name: str) -> Dict[str, Any]:
    """Extract entities and relationships from text using GPT"""
    
    prompt = f"""
    Analyze the following text from {chapter_name} and extract:
    1. Events with properties: name, event_type, date, location, description
    2. People with properties: name, description, role
    3. Locations with properties: name, description, type
    4. Relationships between entities

    Return a JSON object with:
    {{
        "nodes": [
            {{
                "id": "unique_id",
                "label": "Event|Person|Location", 
                "properties": {{...}}
            }}
        ],
        "relationships": [
            {{
                "from_id": "source_node_id",
                "to_id": "target_node_id", 
                "type": "PARTICIPATED_IN|OCCURRED_AT|etc",
                "properties": {{}}
            }}
        ]
    }}

    Text: {text}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        content = response.choices[0].message.content
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            print(f"⚠️ No valid JSON found in GPT response for {chapter_name}")
            return {"nodes": [], "relationships": []}
            
    except Exception as e:
        print(f"❌ Error processing {chapter_name}: {e}")
        return {"nodes": [], "relationships": []}

def clear_database():
    """Clear all existing data in the database"""
    with driver.session(database=NEO4J_DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("��️ Database cleared")

def write_chapter_to_neo4j(graph_data: Dict[str, Any], chapter_name: str):
    """Write a single chapter's graph data to Neo4j"""
    
    def create_nodes(tx, nodes):
        for node in nodes:
            label = node.get("label", "Unknown")
            node_id = node.get("id")
            properties = node.get("properties", {})
            
            # Build property string for Cypher
            prop_strings = []
            for key, value in properties.items():
                if isinstance(value, str):
                    prop_strings.append(f"{key}: '{value.replace(chr(39), chr(92)+chr(39))}'")
                else:
                    prop_strings.append(f"{key}: {json.dumps(value)}")
            
            prop_string = "{" + ", ".join(prop_strings) + "}" if prop_strings else "{}"
            
            query = f"MERGE (n:{label} {{id: '{node_id}'}}) SET n += {prop_string}"
            tx.run(query)
    
    def create_relationships(tx, relationships):
        for rel in relationships:
            from_id = rel.get("from_id")
            to_id = rel.get("to_id")
            rel_type = rel.get("type", "RELATED_TO")
            properties = rel.get("properties", {})
            
            # Build property string for Cypher
            prop_strings = []
            for key, value in properties.items():
                if isinstance(value, str):
                    prop_strings.append(f"{key}: '{value.replace(chr(39), chr(92)+chr(39))}'")
                else:
                    prop_strings.append(f"{key}: {json.dumps(value)}")
            
            prop_string = "{" + ", ".join(prop_strings) + "}" if prop_strings else "{}"
            
            query = f"""
            MATCH (a {{id: '{from_id}'}}), (b {{id: '{to_id}'}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r += {prop_string}
            """
            tx.run(query)
    
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            # Create nodes
            nodes = graph_data.get("nodes", [])
            if nodes:
                session.execute_write(create_nodes, nodes)
                print(f"✅ Created {len(nodes)} nodes from {chapter_name}")
            
            # Create relationships
            relationships = graph_data.get("relationships", [])
            if relationships:
                session.execute_write(create_relationships, relationships)
                print(f"✅ Created {len(relationships)} relationships from {chapter_name}")
                
    except Exception as e:
        print(f"❌ Error writing {chapter_name} to Neo4j: {e}")

def get_database_stats():
    """Get current database statistics"""
    with driver.session(database=NEO4J_DATABASE) as session:
        # Count nodes
        result = session.run("MATCH (n) RETURN count(n) as node_count")
        node_count = result.single()["node_count"]
        
        # Count relationships
        result = session.run("MATCH ()-[r]->() RETURN count(r) as rel_count")
        rel_count = result.single()["rel_count"]
        
        return node_count, rel_count

def main():
    """Main function to process book chapter by chapter"""
    print("🚀 Starting chapter-by-chapter book-to-graph conversion...")
    
    # Load book content
    with open(BOOK_JSON_PATH, 'r', encoding='utf-8') as f:
        book_text = json.load(f)
    
    print(f"📖 Loaded book with {len(book_text)} characters")
    
    # Split into chapters
    chapters = split_book_into_chapters(book_text)
    
    if not chapters:
        print("❌ No chapters found in the book!")
        return
    
    # Ask user if they want to clear the database
    clear_db = input(f"\n🗑️ Clear existing data in database '{NEO4J_DATABASE}'? (y/N): ").lower().strip()
    if clear_db in ['y', 'yes']:
        clear_database()
    
    # Get initial stats
    initial_nodes, initial_rels = get_database_stats()
    print(f"📊 Starting with {initial_nodes} nodes and {initial_rels} relationships")
    
    # Process each chapter
    total_chapters = len(chapters)
    for i, (chapter_name, chapter_content) in enumerate(chapters, 1):
        print(f"\n📝 Processing {chapter_name} ({i}/{total_chapters})...")
        print(f"   Content length: {len(chapter_content)} characters")
        
        # Extract graph data from chapter
        graph_data = extract_graph_from_text(chapter_content, chapter_name)
        
        if graph_data and (graph_data.get("nodes") or graph_data.get("relationships")):
            # Write to database immediately
            write_chapter_to_neo4j(graph_data, chapter_name)
            
            # Show updated stats
            current_nodes, current_rels = get_database_stats()
            print(f"📊 Database now has {current_nodes} nodes and {current_rels} relationships")
            
            # Save chapter result to file
            results_dir = os.path.join(PROJECT_ROOT, "results", "chapter_results")
            os.makedirs(results_dir, exist_ok=True)
            
            chapter_file = os.path.join(results_dir, f"{chapter_name.lower().replace(' ', '_')}_graph.json")
            with open(chapter_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "chapter": chapter_name,
                    "processed_at": datetime.now().isoformat(),
                    "nodes_count": len(graph_data.get("nodes", [])),
                    "relationships_count": len(graph_data.get("relationships", [])),
                    "graph_data": graph_data
                }, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Saved chapter result to: {chapter_file}")
        else:
            print(f"⚠️ No data extracted from {chapter_name}")
        
        # Small pause between chapters
        print("⏸️  Pausing for 2 seconds...")
        import time
        time.sleep(2)
    
    # Final statistics
    final_nodes, final_rels = get_database_stats()
    print(f"\n✅ Chapter-by-chapter processing completed!")
    print(f"📊 Final database stats:")
    print(f"   Nodes: {final_nodes} (added {final_nodes - initial_nodes})")
    print(f"   Relationships: {final_rels} (added {final_rels - initial_rels})")
    print(f"   Processed: {total_chapters} chapters")
    
    # Save final summary
    summary_file = os.path.join(PROJECT_ROOT, "results", f"chapter_processing_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    os.makedirs(os.path.dirname(summary_file), exist_ok=True)
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "processing_completed_at": datetime.now().isoformat(),
            "database": NEO4J_DATABASE,
            "total_chapters_processed": total_chapters,
            "initial_stats": {"nodes": initial_nodes, "relationships": initial_rels},
            "final_stats": {"nodes": final_nodes, "relationships": final_rels},
            "chapters": [name for name, _ in chapters]
        }, f, indent=2)
    
    print(f"💾 Saved processing summary to: {summary_file}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️  Processing interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
    finally:
        driver.close()
        print("🔌 Database connection closed")
