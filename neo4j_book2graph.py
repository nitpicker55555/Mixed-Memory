import os
import json
import math
from neo4j import GraphDatabase
from openai import OpenAI

# ---------- CONFIG ----------

BOOK_JSON_PATH = "/Users/yunanli/Desktop/MasterThesis/MemoryGraph/data/books/model_claude-3-5-sonnet-20240620_itermax_10_Idefault_nbchapters_19_nbtokens_10397/book.json"

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "JUcvo0027"
NEO4J_DATABASE = "memorygraphdb"

# Load your OpenAI key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set.")

# If you use a proxy (like openai-hub), otherwise remove base_url:
client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://api.openai-hub.com/v1"
)

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


def extract_graph_from_chunk(chunk_text, chunk_index, num_repeats=5):
    """
    Run the same chunk through GPT multiple times
    and merge the results into a single graph.
    """
    all_graphs = []

    for i in range(num_repeats):
        print(f"→ GPT Pass {i+1} on chunk {chunk_index}…")
        
        prompt = f"""
You are an intelligent memory extraction agent.

Read the following part of a book and transform it into a graph suitable for import into a Neo4j database.

Your output MUST be valid JSON with two arrays:
- "nodes"
- "relationships"

Each node:
{{
    "id": "...",  
    "labels": ["..."],   
    "properties": {{
        "name": "...",
        "time": "...",
        ...
    }}
}}

Each relationship:
{{
    "start_node_id": "...",
    "end_node_id": "...",
    "type": "...",
    "properties": {{
        "time": "...",
        "event": "...",
        ...
    }}
}}

Guidelines:
- Create meaningful labels for nodes, create as many labels as possible. The labels should at least include Person, Event, Place, you should create another label
- Fill as many properties as possible from the book. 
- Use unique IDs for nodes so relationships can connect properly.
- Represent events, dates, actions, and roles as relationships and properties.

Only output pure JSON — no extra text.

BOOK CHUNK:
\"\"\"
{chunk_text}
\"\"\"
        """

        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a skilled graph data extractor."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )

        result_text = response.choices[0].message.content.strip()

        if result_text.startswith("```json"):
            result_text = result_text[len("```json"):].strip()
        if result_text.endswith("```"):
            result_text = result_text[:-3].strip()

        try:
            graph_data = json.loads(result_text)
            all_graphs.append(graph_data)
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error on pass {i+1} for chunk {chunk_index}: {e}")
            print("RAW GPT OUTPUT:\n", result_text)
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
    Merge multiple graph chunks into one graph.
    """
    merged_nodes = {}
    merged_relationships = []

    for graph in graph_list:
        for node in graph.get("nodes", []):
            merged_nodes[node["id"]] = node
        merged_relationships.extend(graph.get("relationships", []))

    final_graph = {
        "nodes": list(merged_nodes.values()),
        "relationships": merged_relationships
    }

    return final_graph

# --- Neo4j ingestion ---

def create_node(tx, node):
    labels = ":".join(node["labels"])
    props = node["properties"]
    props["id"] = node["id"]

    prop_string = ", ".join(f"{k}: ${k}" for k in props.keys())

    query = f"""
        MERGE (n:{labels} {{id: $id}})
        SET n += {{{prop_string}}}
    """
    tx.run(query, **props)

def create_relationship(tx, relationship):
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

def write_graph_to_neo4j(graph_json):
    nodes = graph_json.get("nodes", [])
    relationships = graph_json.get("relationships", [])

    with driver.session(database=NEO4J_DATABASE) as session:
        for node in nodes:
            session.execute_write(create_node, node)
        for rel in relationships:
            session.execute_write(create_relationship, rel)

    print(f"Imported {len(nodes)} nodes and {len(relationships)} relationships into Neo4j!")

# ---------- MAIN ----------

if __name__ == "__main__":
    book_text = load_book_json(BOOK_JSON_PATH)
    chunks = split_text(book_text, max_tokens=3000)

    all_graphs = []

    for idx, chunk in enumerate(chunks):
        try:
            chunk_graph = extract_graph_from_chunk(chunk, idx)
            all_graphs.append(chunk_graph)
        except Exception as e:
            print(f"❌ Error processing chunk {idx}: {e}")

    final_graph = merge_graph_data(all_graphs)

    out_path = "/Users/yunanli/Desktop/MasterThesis/MemoryGraph/final_graph.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_graph, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved final graph to {out_path}")

    write_graph_to_neo4j(final_graph)

    driver.close()
    print("✅ Graph import complete.")
