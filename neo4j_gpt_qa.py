import os
import json
import numpy as np
from numpy.linalg import norm
from neo4j import GraphDatabase
from openai import OpenAI

# --------- Config ---------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Please set OPENAI_API_KEY as an environment variable.")

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://api.openai-hub.com/v1"  # your custom proxy if needed
)

uri = "neo4j://127.0.0.1:7687"
username = "neo4j"
password = "JUcvo0027"
DATABASE_NAME = "try1"

driver = GraphDatabase.driver(uri, auth=(username, password))

# Path to save JSON trace
JSON_TRACE_PATH = "/Users/yunanli/Desktop/MasterThesis/MemoryGraph/neo4jgraph_path.json"
NODE_EMBEDDING_INDEX_PATH = "/Users/yunanli/Desktop/MasterThesis/MemoryGraph/node_embedding_index.json"

# --------- Embedding Functions ---------

def embed_text(text):
    """
    Get OpenAI embedding for a single text.
    """
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=[text]
    )
    return np.array(response.data[0].embedding)

def cosine_similarity(a, b):
    return np.dot(a, b) / (norm(a) * norm(b) + 1e-8)

# --------- Graph Schema Functions ---------

def get_graph_schema():
    schema = {}
    with driver.session(database=DATABASE_NAME) as session:
        result = session.run("CALL db.labels()")
        labels = [record["label"] for record in result]
        schema["labels"] = labels

        result = session.run("CALL db.relationshipTypes()")
        rel_types = [record["relationshipType"] for record in result]
        schema["relationships"] = rel_types

        # Optional property sampling skipped here for brevity
    return schema

# --------- Node Embedding Index ---------

def extract_all_node_names(schema):
    """
    Extract all node names from Neo4j for embedding.
    """
    names = set()
    with driver.session(database=DATABASE_NAME) as session:
        for label in schema["labels"]:
            result = session.run(
                f"""
                MATCH (n:{label})
                WHERE n.name IS NOT NULL
                RETURN DISTINCT n.name AS name
                LIMIT 10000
                """
            )
            for record in result:
                name = record["name"]
                if name:
                    names.add(name)
    return list(names)

def build_node_embedding_index(schema, output_path=NODE_EMBEDDING_INDEX_PATH):
    names = extract_all_node_names(schema)
    index = []
    for name in names:
        emb = embed_text(name)
        index.append({
            "name": name,
            "embedding": emb.tolist()
        })
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved embedding index with {len(index)} nodes to {output_path}.")

def load_node_embedding_index(path=NODE_EMBEDDING_INDEX_PATH):
    with open(path, "r", encoding="utf-8") as f:
        index = json.load(f)
    # Convert embeddings back to numpy arrays
    for item in index:
        item["embedding"] = np.array(item["embedding"])
    return index

def find_best_matching_node(question_text, index, threshold=0.55):
    """
    Find the node name with the highest cosine similarity to the question.
    """
    query_emb = embed_text(question_text)
    best_name = None
    best_score = -1.0

    for item in index:
        sim = cosine_similarity(query_emb, item["embedding"])
        if sim > best_score:
            best_score = sim
            best_name = item["name"]

    if best_score >= threshold:
        print(f"✅ Found matching node: {best_name} (score={best_score:.4f})")
        return best_name
    else:
        print("⚠️ No sufficiently close node found via embedding search.")
        return None

# --------- Query Generation ---------

def question_to_cypher(question, schema):
    """
    Generate a Cypher query from a natural language question using GPT.
    """
    node_labels = ", ".join(schema['labels'])
    rel_types = ", ".join(schema['relationships'])

    prompt = f"""
You are an expert Cypher engineer for Neo4j.

GRAPH SCHEMA:
- Node Labels: {node_labels}
- Relationship Types: {rel_types}

RULES FOR GENERATING CYPHER:
[... same prompt as before, omitted for brevity ...]

USER QUESTION:
{question}
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are a brilliant Cypher engineer who only outputs Cypher queries, no explanations."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0,
        max_tokens=1000
    )

    cypher_query = response.choices[0].message.content.strip()

    if cypher_query:
        return clean_cypher_query(cypher_query)
    else:
        return ""

def generate_cypher_for_node(node_name):
    """
    Generate a Cypher query focused on a specific node name.
    """
    cypher_query = f"""
        MATCH path = (n)-[*1..3]-(m)
        WHERE toLower(n.name) CONTAINS "{node_name.lower()}"
        RETURN nodes(path) AS nodes, relationships(path) AS relationships
        LIMIT 50
    """
    return cypher_query

def clean_cypher_query(cypher_query):
    if cypher_query.startswith("```"):
        cypher_query = cypher_query.strip("`")
        lines = cypher_query.splitlines()
        if lines and lines[0].lower() in ["cypher", "python", "sql"]:
            lines = lines[1:]
        if lines and lines[-1].strip() == "":
            lines = lines[:-1]
        cypher_query = "\n".join(lines)
    return cypher_query.strip()

# --------- Neo4j Execution ---------

def run_cypher_query(cypher_query):
    with driver.session(database=DATABASE_NAME) as session:
        result = session.run(cypher_query)
        records = [record.data() for record in result]
        return records, records

# --------- Answer Generation ---------

def answer_with_gpt(question, cypher_result):
    prompt = f"""You are an expert at answering questions using Neo4j graph data.\nThe user asked: \"{question}\"\nThe Cypher query result is: {cypher_result}\nPlease provide a concise, clear answer to the user's question based on the result."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=400
    )
    answer = response.choices[0].message.content
    return answer.strip() if answer else ""

# --------- JSON Saving ---------

def save_to_json(data, path):
    if os.path.exists(path):
        if os.path.getsize(path) == 0:
            all_data = []
        else:
            with open(path, "r", encoding="utf-8") as f:
                all_data = json.load(f)
    else:
        all_data = []

    all_data.append(data)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

# --------- Pipeline Function ---------

def handle_question(question, schema, embedding_index_path=NODE_EMBEDDING_INDEX_PATH):

    index = load_node_embedding_index(embedding_index_path)
    matched_node = find_best_matching_node(question, index)

    if matched_node:
        cypher_query = generate_cypher_for_node(matched_node)
    else:
        cypher_query = question_to_cypher(question, schema)

    cypher_result, trace_info = run_cypher_query(cypher_query)
    answer = answer_with_gpt(question, cypher_result)

    record = {
        "question": question,
        "cypher_query": cypher_query,
        "graph_trace": trace_info,
        "answer": answer
    }
    save_to_json(record, JSON_TRACE_PATH)

    print(f"Final answer:\n{answer}")

    return answer

def extract_all_node_names(schema):
    names = set()
    missing_nodes = []
    with driver.session(database=DATABASE_NAME) as session:
        for label in schema["labels"]:
            result = session.run(
                f"""
                MATCH (n:{label})
                RETURN DISTINCT n.name AS name, n
                LIMIT 10000
                """
            )
            for record in result:
                name = record["name"]
                if name and name.strip():
                    names.add(name.strip())
                else:
                    missing_nodes.append(record["n"])
    print(f"⚠️ Nodes missing name attribute: {len(missing_nodes)}")
    for node in missing_nodes:
        print(node)
    return list(names)

if __name__ == "__main__":
    schema = get_graph_schema()
    question = "List all person connected to Astronomy Night"
    handle_question(question, schema)



# # 
# import os
# import json
# from neo4j import GraphDatabase
# from openai import OpenAI

# # --------- Config ---------
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# if not OPENAI_API_KEY:
#     raise ValueError("Please set OPENAI_API_KEY as an environment variable.")

# client = OpenAI(
#     api_key=OPENAI_API_KEY,
#     base_url="https://api.openai-hub.com/v1"  # your custom proxy if needed
# )

# uri = "neo4j://127.0.0.1:7687"
# username = "neo4j"
# password = "JUcvo0027"
# DATABASE_NAME = "try1"  # Specify which database to use consistently

# driver = GraphDatabase.driver(uri, auth=(username, password))

# # Path to save JSON trace
# JSON_TRACE_PATH = "/Users/yunanli/Desktop/MasterThesis/MemoryGraph/neo4jgraph_path.json"

# # --------- Functions ---------

# def get_graph_schema():
#     schema = {}
#     with driver.session(database=DATABASE_NAME) as session:
#         # 获取所有节点标签
#         result = session.run("CALL db.labels()")
#         labels = [record["label"] for record in result]
#         schema["labels"] = labels

#         # 获取所有关系类型
#         result = session.run("CALL db.relationshipTypes()")
#         rel_types = [record["relationshipType"] for record in result]
#         schema["relationships"] = rel_types

#         # 尝试获取节点属性（如果支持的话）
#         node_props = {}
#         try:
#             result = session.run("CALL db.schema.nodeTypeProperties()")
#             for record in result:
#                 label = record["nodeType"]
#                 prop = record["propertyName"]
#                 node_props.setdefault(label, set()).add(prop)
#             schema["node_properties"] = {k: list(v) for k, v in node_props.items()}
#         except Exception as e:
#             print(f"Warning: db.schema.nodeTypeProperties() not available: {e}")
#             # 备用方案：手动采样节点属性
#             node_props = {}
#             for label in labels:
#                 try:
#                     result = session.run(f"MATCH (n:{label}) RETURN keys(n) AS props LIMIT 10")
#                     all_keys = set()
#                     for record in result:
#                         all_keys.update(record["props"])
#                     node_props[label] = list(all_keys)
#                 except Exception:
#                     node_props[label] = []
#             schema["node_properties"] = node_props

#         # 尝试获取关系属性（如果支持的话）
#         rel_props = {}
#         try:
#             result = session.run("CALL db.schema.relationshipTypeProperties()")
#             for record in result:
#                 rel_type = record["relationshipType"]
#                 prop = record["propertyName"]
#                 rel_props.setdefault(rel_type, set()).add(prop)
#             schema["relationship_properties"] = {k: list(v) for k, v in rel_props.items()}
#         except Exception as e:
#             print(f"Warning: db.schema.relationshipTypeProperties() not available: {e}")
#             # 备用方案：手动采样关系属性
#             rel_props = {}
#             for rel_type in rel_types:
#                 try:
#                     result = session.run(f"MATCH ()-[r:{rel_type}]-() RETURN keys(r) AS props LIMIT 10")
#                     all_keys = set()
#                     for record in result:
#                         all_keys.update(record["props"])
#                     rel_props[rel_type] = list(all_keys)
#                 except Exception:
#                     rel_props[rel_type] = []
#             schema["relationship_properties"] = rel_props

#         # 尝试获取关系模式（如果支持的话）
#         rel_patterns = []
#         try:
#             result = session.run("CALL db.schema.visualization()")
#             for record in result:
#                 for rel in record["relationships"]:
#                     rel_patterns.append({
#                         "type": rel["type"],
#                         "start": rel["startNodeType"],
#                         "end": rel["endNodeType"]
#                     })
#             schema["relationship_patterns"] = rel_patterns
#         except Exception as e:
#             print(f"Warning: db.schema.visualization() not available: {e}")
#             # 备用方案：手动采样关系模式
#             rel_patterns = []
#             for rel_type in rel_types:
#                 try:
#                     result = session.run(f"""
#                                         MATCH (start)-[r:{rel_type}]->(end) 
#                                         RETURN DISTINCT labels(start) AS start_labels, labels(end) AS end_labels 
#                                         LIMIT 20
#                                     """)
#                     for record in result:
#                         for start_label in record["start_labels"]:
#                             for end_label in record["end_labels"]:
#                                 rel_patterns.append({
#                                     "type": rel_type,
#                                     "start": start_label,
#                                     "end": end_label
#                                 })
#                 except Exception:
#                     pass
#             schema["relationship_patterns"] = rel_patterns

#     return schema

# def question_to_cypher(question, schema):
#     """
#     Generate a Cypher query from a natural language question,
#     searching for relevant nodes or general info if no specific node is detected.
#     """

#     # Convert lists for nice printing
#     node_labels = ", ".join(schema['labels'])
#     rel_types = ", ".join(schema['relationships'])

#     # The actual system prompt for GPT
#     prompt = f"""
# You are an expert Cypher engineer for Neo4j.

# GRAPH SCHEMA:
# - Node Labels: {node_labels}
# - Relationship Types: {rel_types}

# RULES FOR GENERATING CYPHER:

# 1. FIRST, analyze the user question to check if it mentions a specific entity (person, place, event, object, etc.).

#     - Check if any word or phrase in the question closely matches a known node label or likely entity name (case-insensitive).
#     - For example:
#         - "New York" might match a node with name = "New York" or label Place.
#         - "Ezra Edwards" might match a Person node.

# 2. IF a specific entity is detected:
#     - Generate Cypher like this:

#         MATCH path = (n)-[*1..3]-(m)
#         WHERE toLower(n.name) CONTAINS "<lowercased entity name>"
#         RETURN nodes(path) AS nodes, relationships(path) AS relationships
#         LIMIT 50

#     - This finds the neighborhood around the matched node, regardless of label or relationship type.

# 3. IF the question is global (like "list all events", or "how many people exist"):
#     - Generate the correct Cypher for that broader question.

# 4. For fuzzy matching:
#     - Consider partial matches or spelling variations if possible.
#     - If the question mentions e.g. "nyc", generate Cypher that also searches for "New York".

# IMPORTANT:
# - Do NOT assume only Person nodes.
# - Use meaningful relationship types where possible, but generic patterns are acceptable if the question is broad.
# - Write only the Cypher query. Do NOT include explanations or markdown formatting.

# USER QUESTION:
# {question}
# """

#     response = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[
#             {
#                 "role": "system",
#                 "content": "You are a brilliant Cypher engineer who only outputs Cypher queries, no explanations."
#             },
#             {
#                 "role": "user",
#                 "content": prompt
#             }
#         ],
#         temperature=0,
#         max_tokens=1000
#     )

#     cypher_query = response.choices[0].message.content.strip()

#     if cypher_query:
#         return clean_cypher_query(cypher_query)
#     else:
#         return ""

# def clean_cypher_query(cypher_query):
#     if cypher_query.startswith("```"):
#         cypher_query = cypher_query.strip("`")
#         lines = cypher_query.splitlines()
#         if lines and lines[0].lower() in ["cypher", "python", "sql"]:
#             lines = lines[1:]
#         if lines and lines[-1].strip() == "":
#             lines = lines[:-1]
#         cypher_query = "\n".join(lines)
#     return cypher_query.strip()

# def save_to_json(data, path):
#     """
#     Append data to a JSON file (array of records).
#     """
#     if os.path.exists(path):
#         # Check if file size is zero
#         if os.path.getsize(path) == 0:
#             all_data = []
#         else:
#             with open(path, "r", encoding="utf-8") as f:
#                 all_data = json.load(f)
#     else:
#         all_data = []

#     all_data.append(data)

#     with open(path, "w", encoding="utf-8") as f:
#         json.dump(all_data, f, indent=2, ensure_ascii=False)

# def run_cypher_query(cypher_query):
#     """
#     Run the Cypher query and return the result and a trace (nodes/relationships).
#     """
#     with driver.session(database=DATABASE_NAME) as session:
#         result = session.run(cypher_query)
#         records = [record.data() for record in result]
#         return records, records  # You can customize the trace as needed

# def ensure_path_variable_in_cypher(cypher_query):
#     """
#     If the query returns nodes(path) or relationships(path) but does not define 'path', fix it.
#     """
#     import re
#     # Only fix if RETURN uses nodes(path) or relationships(path) and 'MATCH path =' is missing
#     if ("nodes(path)" in cypher_query or "relationships(path)" in cypher_query) and "MATCH path =" not in cypher_query:
#         # Find the first MATCH ... pattern and insert 'path ='
#         cypher_query = re.sub(r"MATCH\s*\(", "MATCH path = (", cypher_query, count=1)
#     return cypher_query

# def answer_with_gpt(question, cypher_result):
#     """
#     Use GPT to answer the question based on the Cypher result.
#     """
#     prompt = f"""You are an expert at answering questions using Neo4j graph data.\nThe user asked: \"{question}\"\nThe Cypher query result is: {cypher_result}\nPlease provide a concise, clear answer to the user's question based on the result."""
#     response = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.2,
#         max_tokens=400
#     )
#     answer = response.choices[0].message.content
#     return answer.strip() if answer else ""

# # --------- MAIN ---------

# if __name__ == "__main__":
#     schema = get_graph_schema()
#     print("Graph schema detected:\n", schema)

#     question = "List all person connected to Kylee Beard, and the relationship type"

#     cypher_query = question_to_cypher(question, schema)
#     print(f"\nGenerated Cypher query:\n{cypher_query}\n")

#     cypher_query = ensure_path_variable_in_cypher(cypher_query)
#     print(f"\nFixed Cypher query (if needed):\n{cypher_query}\n")

#     cypher_result, trace_info = run_cypher_query(cypher_query)
#     print(f"Cypher result:\n{cypher_result}\n")
#     print(f"Trace info:\n{trace_info}\n")

#     answer = answer_with_gpt(question, cypher_result)
#     print(f"Final answer:\n{answer}")

#     # Save to JSON
#     record = {
#         "question": question,
#         "cypher_query": cypher_query,
#         "graph_trace": trace_info,
#         "answer": answer
#     }
#     save_to_json(record, JSON_TRACE_PATH)
#     print(f"\nSaved record to {JSON_TRACE_PATH}")

#     driver.close()
