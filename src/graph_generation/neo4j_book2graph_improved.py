import os
import json
import math
from neo4j import GraphDatabase
from openai import OpenAI

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# ---------- CONFIG ----------

# Get the script directory and calculate relative path to data
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
BOOK_JSON_PATH = os.path.join(PROJECT_ROOT, "data", "book.json")

print(f"Script directory: {SCRIPT_DIR}")
print(f"Project root: {PROJECT_ROOT}")
print(f"Book JSON path: {BOOK_JSON_PATH}")
print(f"Book file exists: {os.path.exists(BOOK_JSON_PATH)}")

# Use environment variables
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "test9")

# Load your OpenAI key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set.")

# OpenAI client configuration
try:
    client = OpenAI(api_key=OPENAI_API_KEY)
    print("✅ OpenAI client initialized successfully")
except Exception as e:
    print(f"❌ Error initializing OpenAI client: {e}")
    # Try with base_url if available
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

# ---------- NEO4J CONNECTION ----------

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)

# ---------- FUNCTIONS ----------

def load_book_json(path):
    """Load your book.json file as a string."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def split_text(text, max_tokens=3000):
    """
    Split text into chunks suitable for OpenAI API calls.
    """
    # For simplicity, split on paragraphs (double newlines).
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) < max_tokens:
            current_chunk += para + "\n\n"
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks

def extract_chapter_number(chunk_text):
    """
    Try to extract chapter number from the chunk text.
    """
    import re
    # Look for "Chapter X" patterns
    chapter_match = re.search(r'chapter\s+(\d+)', chunk_text, re.IGNORECASE)
    if chapter_match:
        return int(chapter_match.group(1))
    return None

def extract_graph_from_chunk(chunk_text, chunk_index, num_repeats=3):
    """
    Run the same chunk through GPT multiple times with improved schema-specific prompt.
    """
    all_graphs = []
    chapter_num = extract_chapter_number(chunk_text)

    for i in range(num_repeats):
        print(f"→ GPT Pass {i+1} on chunk {chunk_index}…")
        
        prompt = f"""
You are an intelligent memory extraction agent. Extract a knowledge graph from this book text that follows a specific schema designed to answer complex queries.

REQUIRED SCHEMA:

Node Types and Properties:
1. Event nodes (label: "Event"):
   - name: event identifier/title
   - date: when it occurred (extract exact dates like "March 23, 2024")
   - location: where it took place (extract specific location names)
   - event_type: type of event (e.g., "Archery Tournament", "Environmental Summit", "Theater Performance")
   - participants: list of people involved (as array)
   - chapter: chapter number (use {chapter_num if chapter_num else 'null'})
   - description: detailed description of what happened

2. Person nodes (label: "Person"):
   - name: person's full name

3. Location nodes (label: "Location"):
   - name: location name

CRITICAL REQUIREMENTS:
- Extract ALL events, no matter how small
- For each event, identify WHO was involved (participants)
- Extract specific dates and locations
- Categorize events by type (Archery Tournament, Environmental Summit, etc.)
- Create Person nodes for all mentioned people
- Create Location nodes for all mentioned places

Your output MUST be valid JSON with two arrays:
- "nodes"
- "relationships"

Each node:
{{
    "id": "unique_identifier",  
    "labels": ["Event"/"Person"/"Location"],   
    "properties": {{
        "name": "...",
        "date": "...",     // For Events only
        "location": "...", // For Events only  
        "event_type": "...", // For Events only
        "participants": ["person1", "person2"], // For Events only
        "chapter": {chapter_num if chapter_num else 'null'}, // For Events only
        "description": "..." // For Events only
    }}
}}

Each relationship:
{{
    "start_node_id": "...",
    "end_node_id": "...",
    "type": "PARTICIPATED_IN"/"OCCURRED_AT"/"OCCURRED_ON",
    "properties": {{}}
}}

Relationship types:
- PARTICIPATED_IN: Person -> Event
- OCCURRED_AT: Event -> Location  
- OCCURRED_ON: Event -> Date (if you create Date nodes)

Focus on extracting:
- Events with their participants, dates, locations, and types
- All people mentioned
- All locations mentioned
- Temporal information (dates/times)

Only output pure JSON — no extra text.

BOOK CHUNK:
\"\"\"
{chunk_text}
\"\"\"
        """

        response = client.chat.completions.create(
            model="gpt-4o",  # Updated to use gpt-4o
            messages=[
                {"role": "system", "content": "You are a skilled graph data extractor that follows precise schemas. Extract comprehensive knowledge graphs from text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )

        result_text = response.choices[0].message.content
        if result_text is None:
            print(f"⚠️ Empty response from GPT on pass {i+1} for chunk {chunk_index}")
            continue
        result_text = result_text.strip()

        if result_text.startswith("```json"):
            result_text = result_text[len("```json"):].strip()
        if result_text.endswith("```"):
            result_text = result_text[:-3].strip()

        try:
            graph_data = json.loads(result_text)
            
            # Validate that we have the required structure
            if "nodes" in graph_data and "relationships" in graph_data:
                # Add chunk info for debugging
                graph_data["chunk_index"] = chunk_index
                graph_data["chunk_pass"] = i + 1
                all_graphs.append(graph_data)
                print(f"✅ Successfully parsed {len(graph_data.get('nodes', []))} nodes and {len(graph_data.get('relationships', []))} relationships")
            else:
                print(f"⚠️ Invalid graph structure on pass {i+1} for chunk {chunk_index}")
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error on pass {i+1} for chunk {chunk_index}: {e}")
            print("RAW GPT OUTPUT:\n", result_text[:500] + "...")
            continue

    if not all_graphs:
        print(f"⚠️ No successful parses for chunk {chunk_index}")
        return {
            "nodes": [],
            "relationships": []
        }

    # Merge all results into a single graph
    merged_graph = merge_graph_data(all_graphs)
    return merged_graph

def merge_graph_data(graph_list):
    """
    Merge multiple graph chunks into one graph, handling duplicates intelligently.
    """
    merged_nodes = {}
    merged_relationships = []
    relationship_set = set()

    for graph in graph_list:
        # Merge nodes (overwrite with latest data for same ID)
        for node in graph.get("nodes", []):
            node_id = node["id"]
            merged_nodes[node_id] = node

        # Merge relationships (avoid duplicates)
        for rel in graph.get("relationships", []):
            # Create a signature for the relationship
            rel_sig = (rel["start_node_id"], rel["end_node_id"], rel["type"])
            if rel_sig not in relationship_set:
                relationship_set.add(rel_sig)
                merged_relationships.append(rel)

    final_graph = {
        "nodes": list(merged_nodes.values()),
        "relationships": merged_relationships
    }

    print(f"📊 Merged graph: {len(final_graph['nodes'])} nodes, {len(final_graph['relationships'])} relationships")
    return final_graph

# --- Neo4j ingestion with improved error handling ---

def create_node(tx, node):
    """Create a node in Neo4j with proper error handling."""
    try:
        labels = ":".join(node["labels"])
        props = node["properties"].copy()
        props["id"] = node["id"]

        # Handle special cases for property types
        keys_to_remove = []
        for key, value in props.items():
            if isinstance(value, list):
                # Convert lists to Neo4j array format
                props[key] = value
            elif value is None:
                # Mark null values for removal
                keys_to_remove.append(key)
        
        # Remove null values
        for key in keys_to_remove:
            del props[key]

        prop_assignments = []
        for k in props.keys():
            prop_assignments.append(f"n.{k} = ${k}")

        query = f"""
            MERGE (n:{labels} {{id: $id}})
            SET {', '.join(prop_assignments)}
        """
        tx.run(query, **props)
        
    except Exception as e:
        print(f"❌ Error creating node {node.get('id', 'unknown')}: {e}")

def create_relationship(tx, relationship):
    """Create a relationship in Neo4j with proper error handling."""
    try:
        rel_type = relationship["type"]
        start_id = relationship["start_node_id"] 
        end_id = relationship["end_node_id"]
        props = relationship.get("properties", {})

        query = f"""
            MATCH (a {{id: $start_id}})
            MATCH (b {{id: $end_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r += $props
        """
        tx.run(query, start_id=start_id, end_id=end_id, props=props)
        
    except Exception as e:
        print(f"❌ Error creating relationship {start_id} -> {end_id}: {e}")

def clear_database(tx):
    """Clear all nodes and relationships from the database."""
    tx.run("MATCH (n) DETACH DELETE n")

def create_indexes(tx):
    """Create indexes for efficient querying based on schema analysis."""
    indexes = [
        "CREATE INDEX event_name_idx IF NOT EXISTS FOR (e:Event) ON (e.name)",
        "CREATE INDEX event_date_idx IF NOT EXISTS FOR (e:Event) ON (e.date)", 
        "CREATE INDEX event_location_idx IF NOT EXISTS FOR (e:Event) ON (e.location)",
        "CREATE INDEX event_type_idx IF NOT EXISTS FOR (e:Event) ON (e.event_type)",
        "CREATE INDEX event_participants_idx IF NOT EXISTS FOR (e:Event) ON (e.participants)",
        "CREATE INDEX person_name_idx IF NOT EXISTS FOR (p:Person) ON (p.name)",
        "CREATE INDEX location_name_idx IF NOT EXISTS FOR (l:Location) ON (l.name)"
    ]
    
    for index_query in indexes:
        try:
            tx.run(index_query)
        except Exception as e:
            print(f"⚠️ Index creation warning: {e}")

def write_graph_to_neo4j(graph_json):
    """Write the graph to Neo4j with proper setup."""
    nodes = graph_json.get("nodes", [])
    relationships = graph_json.get("relationships", [])

    with driver.session(database=NEO4J_DATABASE) as session:
        # Clear existing data
        print("🗑️ Clearing existing data...")
        session.execute_write(clear_database)
        
        # Create indexes
        print("📊 Creating indexes...")
        session.execute_write(create_indexes)
        
        # Import nodes
        print(f"📝 Importing {len(nodes)} nodes...")
        for node in nodes:
            session.execute_write(create_node, node)
            
        # Import relationships  
        print(f"🔗 Importing {len(relationships)} relationships...")
        for rel in relationships:
            session.execute_write(create_relationship, rel)

    print(f"✅ Successfully imported {len(nodes)} nodes and {len(relationships)} relationships into Neo4j database '{NEO4J_DATABASE}'!")

# ---------- MAIN ----------

if __name__ == "__main__":
    print("🚀 Starting improved book-to-graph conversion...")
    
    # Load book
    book_text = load_book_json(BOOK_JSON_PATH)
    print(f"📖 Loaded book with {len(book_text)} characters")
    
    # Split into chunks
    chunks = split_text(book_text, max_tokens=3000)
    print(f"📄 Split into {len(chunks)} chunks")

    all_graphs = []

    # Process each chunk
    for idx, chunk in enumerate(chunks):
        print(f"\n📝 Processing chunk {idx+1}/{len(chunks)}...")
        try:
            chunk_graph = extract_graph_from_chunk(chunk, idx)
            all_graphs.append(chunk_graph)
        except Exception as e:
            print(f"❌ Error processing chunk {idx}: {e}")

    # Merge all graphs
    print(f"\n🔄 Merging {len(all_graphs)} graph chunks...")
    final_graph = merge_graph_data(all_graphs)

    # Save to file
    out_path = os.path.join(PROJECT_ROOT, "results", "final_graph_improved.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_graph, f, indent=2, ensure_ascii=False)
    print(f"💾 Saved final graph to {out_path}")

    # Write to Neo4j
    print(f"\n🏗️ Writing to Neo4j database '{NEO4J_DATABASE}'...")
    write_graph_to_neo4j(final_graph)

    # Print statistics
    nodes_by_label = {}
    for node in final_graph.get("nodes", []):
        for label in node.get("labels", []):
            nodes_by_label[label] = nodes_by_label.get(label, 0) + 1
    
    print(f"\n📊 Final Statistics:")
    print(f"   Total Nodes: {len(final_graph.get('nodes', []))}")
    for label, count in nodes_by_label.items():
        print(f"   - {label}: {count}")
    print(f"   Total Relationships: {len(final_graph.get('relationships', []))}")

    driver.close()
    print("✅ Graph import complete!") 

# import os
# import json
# import math
# from neo4j import GraphDatabase
# from openai import OpenAI

# # Load environment variables
# from dotenv import load_dotenv
# load_dotenv()

# # ---------- CONFIG ----------

# # Get the script directory and calculate relative path to data
# SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
# BOOK_JSON_PATH = os.path.join(PROJECT_ROOT, "data", "book.json")

# print(f"Script directory: {SCRIPT_DIR}")
# print(f"Project root: {PROJECT_ROOT}")
# print(f"Book JSON path: {BOOK_JSON_PATH}")
# print(f"Book file exists: {os.path.exists(BOOK_JSON_PATH)}")

# # Use environment variables
# NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
# NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
# NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
# NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "test9")

# # Load your OpenAI key
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# if not OPENAI_API_KEY:
#     raise ValueError("OPENAI_API_KEY environment variable is not set.")

# # OpenAI client configuration
# try:
#     client = OpenAI(api_key=OPENAI_API_KEY)
#     print("✅ OpenAI client initialized successfully")
# except Exception as e:
#     print(f"❌ Error initializing OpenAI client: {e}")
#     # Try with base_url if available
#     OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
#     if OPENAI_BASE_URL:
#         try:
#             client = OpenAI(
#                 api_key=OPENAI_API_KEY,
#                 base_url=OPENAI_BASE_URL
#             )
#             print("✅ OpenAI client initialized with custom base URL")
#         except Exception as e2:
#             print(f"❌ Error with custom URL: {e2}")
#             raise e2
#     else:
#         raise e

# # ---------- NEO4J CONNECTION ----------

# driver = GraphDatabase.driver(
#     NEO4J_URI,
#     auth=(NEO4J_USER, NEO4J_PASSWORD)
# )

# # ---------- FUNCTIONS ----------

# def load_book_json(path):
#     """Load your book.json file as a string."""
#     with open(path, "r", encoding="utf-8") as f:
#         return f.read()

# def split_text(text, max_tokens=3000):
#     """
#     Split text into chunks suitable for OpenAI API calls.
#     """
#     # For simplicity, split on paragraphs (double newlines).
#     paragraphs = text.split("\n\n")
#     chunks = []
#     current_chunk = ""

#     for para in paragraphs:
#         if len(current_chunk) + len(para) < max_tokens:
#             current_chunk += para + "\n\n"
#         else:
#             if current_chunk.strip():
#                 chunks.append(current_chunk.strip())
#             current_chunk = para + "\n\n"

#     if current_chunk.strip():
#         chunks.append(current_chunk.strip())

#     return chunks

# def extract_chapter_number(chunk_text):
#     """
#     Try to extract chapter number from the chunk text.
#     """
#     import re
#     # Look for "Chapter X" patterns
#     chapter_match = re.search(r'chapter\s+(\d+)', chunk_text, re.IGNORECASE)
#     if chapter_match:
#         return int(chapter_match.group(1))
#     return None

# def extract_graph_from_chunk(chunk_text, chunk_index, num_repeats=3):
#     """
#     Run the same chunk through GPT multiple times with improved schema-specific prompt.
#     """
#     all_graphs = []
#     chapter_num = extract_chapter_number(chunk_text)

#     for i in range(num_repeats):
#         print(f"→ GPT Pass {i+1} on chunk {chunk_index}…")
        
#         prompt = f"""
# You are an intelligent memory extraction agent. Extract a knowledge graph from this book text that follows a specific schema designed to answer complex queries.

# REQUIRED SCHEMA:

# Node Types and Properties:
# 1. Event nodes (label: "Event"):
#    - name: event identifier/title
#    - date: when it occurred (extract exact dates like "March 23, 2024")
#    - location: where it took place (extract specific location names)
#    - event_type: type of event (e.g., "Archery Tournament", "Environmental Summit", "Theater Performance")
#    - participants: list of people involved (as array)
#    - chapter: chapter number (use {chapter_num if chapter_num else 'null'})
#    - description: detailed description of what happened

# 2. Person nodes (label: "Person"):
#    - name: person's full name

# 3. Location nodes (label: "Location"):
#    - name: location name

# CRITICAL REQUIREMENTS:
# - Extract ALL events, no matter how small
# - For each event, identify WHO was involved (participants)
# - Extract specific dates and locations
# - Categorize events by type (Archery Tournament, Environmental Summit, etc.)
# - Create Person nodes for all mentioned people
# - Create Location nodes for all mentioned places

# Your output MUST be valid JSON with two arrays:
# - "nodes"
# - "relationships"

# Each node:
# {{
#     "id": "unique_identifier",  
#     "labels": ["Event"/"Person"/"Location"],   
#     "properties": {{
#         "name": "...",
#         "date": "...",     // For Events only
#         "location": "...", // For Events only  
#         "event_type": "...", // For Events only
#         "chapter": {chapter_num if chapter_num else 'null'}, // For Events only
#         "description": "..." // For Events only
#     }}
# }}

# Each relationship:
# {{
#     "start_node_id": "...",
#     "end_node_id": "...",
#     "type": "PARTICIPATED_IN"/"OCCURRED_AT"/"OCCURRED_ON",
#     "properties": {{}}
# }}

# Relationship types:
# - PARTICIPATED_IN: Person -> Event
# - OCCURRED_AT: Event -> Location  
# - OCCURRED_ON: Event -> Date (if you create Date nodes)

# Focus on extracting:
# - Events with their participants, dates, locations, and types
# - All people mentioned
# - All locations mentioned
# - Temporal information (dates/times)

# Only output pure JSON — no extra text.

# BOOK CHUNK:
# \"\"\"
# {chunk_text}
# \"\"\"
#         """

#         response = client.chat.completions.create(
#             model="gpt-4o",  # Updated to use gpt-4o
#             messages=[
#                 {"role": "system", "content": "You are a skilled graph data extractor that follows precise schemas. Extract comprehensive knowledge graphs from text."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.1
#         )

#         result_text = response.choices[0].message.content
#         if result_text is None:
#             print(f"⚠️ Empty response from GPT on pass {i+1} for chunk {chunk_index}")
#             continue
#         result_text = result_text.strip()

#         if result_text.startswith("```json"):
#             result_text = result_text[len("```json"):].strip()
#         if result_text.endswith("```"):
#             result_text = result_text[:-3].strip()

#         try:
#             graph_data = json.loads(result_text)
            
#             # Validate that we have the required structure
#             if "nodes" in graph_data and "relationships" in graph_data:
#                 # Add chunk info for debugging
#                 graph_data["chunk_index"] = chunk_index
#                 graph_data["chunk_pass"] = i + 1
#                 all_graphs.append(graph_data)
#                 print(f"✅ Successfully parsed {len(graph_data.get('nodes', []))} nodes and {len(graph_data.get('relationships', []))} relationships")
#             else:
#                 print(f"⚠️ Invalid graph structure on pass {i+1} for chunk {chunk_index}")
                
#         except json.JSONDecodeError as e:
#             print(f"❌ JSON parsing error on pass {i+1} for chunk {chunk_index}: {e}")
#             print("RAW GPT OUTPUT:\n", result_text[:500] + "...")
#             continue

#     if not all_graphs:
#         print(f"⚠️ No successful parses for chunk {chunk_index}")
#         return {
#             "nodes": [],
#             "relationships": []
#         }

#     # Merge all results into a single graph
#     merged_graph = merge_graph_data(all_graphs)
#     return merged_graph

# def merge_graph_data(graph_list):
#     """
#     Merge multiple graph chunks into one graph, handling duplicates intelligently.
#     """
#     merged_nodes = {}
#     merged_relationships = []
#     relationship_set = set()

#     for graph in graph_list:
#         # Merge nodes (overwrite with latest data for same ID)
#         for node in graph.get("nodes", []):
#             node_id = node["id"]
#             merged_nodes[node_id] = node

#         # Merge relationships (avoid duplicates)
#         for rel in graph.get("relationships", []):
#             # Create a signature for the relationship
#             rel_sig = (rel["start_node_id"], rel["end_node_id"], rel["type"])
#             if rel_sig not in relationship_set:
#                 relationship_set.add(rel_sig)
#                 merged_relationships.append(rel)

#     final_graph = {
#         "nodes": list(merged_nodes.values()),
#         "relationships": merged_relationships
#     }

#     print(f"📊 Merged graph: {len(final_graph['nodes'])} nodes, {len(final_graph['relationships'])} relationships")
#     return final_graph

# # --- Neo4j ingestion with improved error handling ---

# def create_node(tx, node):
#     """Create a node in Neo4j with proper error handling."""
#     try:
#         labels = ":".join(node["labels"])
#         props = node["properties"].copy()
#         props["id"] = node["id"]

#         # Handle special cases for property types
#         keys_to_remove = []
#         for key, value in props.items():
#             if isinstance(value, list):
#                 # Convert lists to Neo4j array format
#                 props[key] = value
#             elif value is None:
#                 # Mark null values for removal
#                 keys_to_remove.append(key)
        
#         # Remove null values
#         for key in keys_to_remove:
#             del props[key]

#         prop_assignments = []
#         for k in props.keys():
#             prop_assignments.append(f"n.{k} = ${k}")

#         query = f"""
#             MERGE (n:{labels} {{id: $id}})
#             SET {', '.join(prop_assignments)}
#         """
#         tx.run(query, **props)
        
#     except Exception as e:
#         print(f"❌ Error creating node {node.get('id', 'unknown')}: {e}")

# def create_relationship(tx, relationship):
#     """Create a relationship in Neo4j with proper error handling."""
#     try:
#         rel_type = relationship["type"]
#         start_id = relationship["start_node_id"] 
#         end_id = relationship["end_node_id"]
#         props = relationship.get("properties", {})

#         query = f"""
#             MATCH (a {{id: $start_id}})
#             MATCH (b {{id: $end_id}})
#             MERGE (a)-[r:{rel_type}]->(b)
#             SET r += $props
#         """
#         tx.run(query, start_id=start_id, end_id=end_id, props=props)
        
#     except Exception as e:
#         print(f"❌ Error creating relationship {start_id} -> {end_id}: {e}")

# def clear_database(tx):
#     """Clear all nodes and relationships from the database."""
#     tx.run("MATCH (n) DETACH DELETE n")

# def create_indexes(tx):
#     """Create indexes for efficient querying based on schema analysis."""
#     indexes = [
#         "CREATE INDEX event_name_idx IF NOT EXISTS FOR (e:Event) ON (e.name)",
#         "CREATE INDEX event_date_idx IF NOT EXISTS FOR (e:Event) ON (e.date)", 
#         "CREATE INDEX event_location_idx IF NOT EXISTS FOR (e:Event) ON (e.location)",
#         "CREATE INDEX event_type_idx IF NOT EXISTS FOR (e:Event) ON (e.event_type)",
#         "CREATE INDEX event_participants_idx IF NOT EXISTS FOR (e:Event) ON (e.participants)",
#         "CREATE INDEX person_name_idx IF NOT EXISTS FOR (p:Person) ON (p.name)",
#         "CREATE INDEX location_name_idx IF NOT EXISTS FOR (l:Location) ON (l.name)"
#     ]
    
#     for index_query in indexes:
#         try:
#             tx.run(index_query)
#         except Exception as e:
#             print(f"⚠️ Index creation warning: {e}")

# def write_graph_to_neo4j(graph_json):
#     """Write the graph to Neo4j with proper setup."""
#     nodes = graph_json.get("nodes", [])
#     relationships = graph_json.get("relationships", [])

#     with driver.session(database=NEO4J_DATABASE) as session:
#         # Clear existing data
#         print("🗑️ Clearing existing data...")
#         session.execute_write(clear_database)
        
#         # Create indexes
#         print("📊 Creating indexes...")
#         session.execute_write(create_indexes)
        
#         # Import nodes
#         print(f"📝 Importing {len(nodes)} nodes...")
#         for node in nodes:
#             session.execute_write(create_node, node)
            
#         # Import relationships  
#         print(f"🔗 Importing {len(relationships)} relationships...")
#         for rel in relationships:
#             session.execute_write(create_relationship, rel)

#     print(f"✅ Successfully imported {len(nodes)} nodes and {len(relationships)} relationships into Neo4j database '{NEO4J_DATABASE}'!")

# # ---------- MAIN ----------

# if __name__ == "__main__":
#     print("🚀 Starting improved book-to-graph conversion...")
    
#     # Load book
#     book_text = load_book_json(BOOK_JSON_PATH)
#     print(f"📖 Loaded book with {len(book_text)} characters")
    
#     # Split into chunks
#     chunks = split_text(book_text, max_tokens=3000)
#     print(f"📄 Split into {len(chunks)} chunks")

#     all_graphs = []

#     # Process each chunk
#     for idx, chunk in enumerate(chunks):
#         print(f"\n📝 Processing chunk {idx+1}/{len(chunks)}...")
#         try:
#             chunk_graph = extract_graph_from_chunk(chunk, idx)
#             all_graphs.append(chunk_graph)
#         except Exception as e:
#             print(f"❌ Error processing chunk {idx}: {e}")

#     # Merge all graphs
#     print(f"\n🔄 Merging {len(all_graphs)} graph chunks...")
#     final_graph = merge_graph_data(all_graphs)

#     # Save to file
#     out_path = os.path.join(PROJECT_ROOT, "results", "final_graph_improved.json")
#     os.makedirs(os.path.dirname(out_path), exist_ok=True)
#     with open(out_path, "w", encoding="utf-8") as f:
#         json.dump(final_graph, f, indent=2, ensure_ascii=False)
#     print(f"💾 Saved final graph to {out_path}")

#     # Write to Neo4j
#     print(f"\n🏗️ Writing to Neo4j database '{NEO4J_DATABASE}'...")
#     write_graph_to_neo4j(final_graph)

#     # Print statistics
#     nodes_by_label = {}
#     for node in final_graph.get("nodes", []):
#         for label in node.get("labels", []):
#             nodes_by_label[label] = nodes_by_label.get(label, 0) + 1
    
#     print(f"\n📊 Final Statistics:")
#     print(f"   Total Nodes: {len(final_graph.get('nodes', []))}")
#     for label, count in nodes_by_label.items():
#         print(f"   - {label}: {count}")
#     print(f"   Total Relationships: {len(final_graph.get('relationships', []))}")

#     driver.close()
#     print("✅ Graph import complete!") 