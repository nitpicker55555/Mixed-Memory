#!/usr/bin/env python3
"""
Node Embedding Generation Script
- Extract all nodes from Neo4j test9 database
- Generate embeddings for each node
- Save to NewStory/node_embeddings.json
"""

import os
import json
import numpy as np
from neo4j import GraphDatabase
from openai import OpenAI
from typing import Dict, List, Any, Optional
import time

# ---------- CONFIG ----------

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "JUcvo0027"
NEO4J_DATABASE = "test9"

# Load your OpenAI key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set.")

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

def extract_all_nodes():
    """Extract all nodes and their properties from Neo4j"""
    
    query = """
    MATCH (n)
    RETURN 
        id(n) as node_id,
        labels(n) as labels,
        properties(n) as props
    """
    
    nodes = []
    
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query)
        for record in result:
            node_data = {
                'node_id': record['node_id'],
                'labels': record['labels'],
                'properties': dict(record['props'])
            }
            nodes.append(node_data)
    
    return nodes

def create_embedding_text(node: Dict[str, Any]) -> str:
    """Create embedding text for a node"""
    
    props = node['properties']
    labels = node['labels']
    
    # Build embedding text
    text_parts = []
    
    # Add labels
    if labels:
        text_parts.append(f"Type: {', '.join(labels)}")
    
    # Add name
    if 'name' in props:
        text_parts.append(f"Name: {props['name']}")
    
    # Add description
    if 'description' in props:
        text_parts.append(f"Description: {props['description']}")
    
    # Add date
    if 'date' in props:
        text_parts.append(f"Date: {props['date']}")
    
    # Add location
    if 'location' in props:
        text_parts.append(f"Location: {props['location']}")
    
    # Add event type
    if 'event_type' in props:
        text_parts.append(f"Event Type: {props['event_type']}")
    
    # Add participants
    if 'participants' in props and props['participants']:
        participants = props['participants']
        if isinstance(participants, list):
            text_parts.append(f"Participants: {', '.join(participants)}")
        else:
            text_parts.append(f"Participants: {participants}")
    
    # Add original story snippet (truncate to first 200 characters to avoid being too long)
    if 'original_story' in props:
        original_story = props['original_story']
        if len(original_story) > 200:
            original_story = original_story[:200] + "..."
        text_parts.append(f"Original Story: {original_story}")
    
    # Combine all text
    embedding_text = " | ".join(text_parts)
    
    return embedding_text

def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding vector for text"""
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=[text]
        )
        return response.data[0].embedding
        
    except Exception as e:
        print(f"Failed to get embedding: {e}")
        print(f"   Text: {text[:100]}...")
        return None

def create_node_identifier(node: Dict[str, Any]) -> str:
    """Create unique identifier for node"""
    props = node['properties']
    
    # Prefer using name property
    if 'name' in props:
        return props['name']
    
    # If no name, use id
    if 'id' in props:
        return props['id']
    
    # Finally use Neo4j internal ID
    return f"node_{node['node_id']}"

def main():
    """Main function"""
    print("Starting Node Embeddings generation...")
    
    # Step 1: Extract all nodes from Neo4j
    print("Extracting nodes from Neo4j...")
    nodes = extract_all_nodes()
    print(f"Extracted {len(nodes)} nodes")
    
    if not nodes:
        print("No nodes found, please ensure Neo4j database contains data")
        return
    
    # Step 2: Generate embeddings
    print("Generating embeddings...")
    embeddings_data = {"embeddings": {}}
    
    for i, node in enumerate(nodes):
        print(f"   Processing node {i+1}/{len(nodes)}: ", end="")
        
        # Create embedding text
        embedding_text = create_embedding_text(node)
        
        # Create node identifier
        node_identifier = create_node_identifier(node)
        
        print(f"{node_identifier}")
        print(f"      Text: {embedding_text[:100]}...")
        
        # Get embedding
        embedding = get_embedding(embedding_text)
        
        if embedding:
            embeddings_data["embeddings"][node_identifier] = {
                "embedding": embedding,
                "text": embedding_text,
                "labels": node['labels'],
                "properties": node['properties']
            }
            print("      Success")
        else:
            print("      Failed")
        
        # Avoid API rate limits, add slight delay
        time.sleep(0.1)
    
    # Step 3: Save embeddings
    output_file = "data/node_embeddings.json"
    print(f"\n💾 保存embeddings到 {output_file}...")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(embeddings_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 成功保存 {len(embeddings_data['embeddings'])} 个node embeddings")
        
        # 显示统计信息
        labels_count = {}
        for node_id, node_data in embeddings_data["embeddings"].items():
            for label in node_data["labels"]:
                labels_count[label] = labels_count.get(label, 0) + 1
        
        print(f"\n📊 Node类型统计:")
        for label, count in labels_count.items():
            print(f"   - {label}: {count}")
        
        # 显示第一个embedding作为样例
        if embeddings_data["embeddings"]:
            first_node = list(embeddings_data["embeddings"].keys())[0]
            first_embedding = embeddings_data["embeddings"][first_node]["embedding"]
            print(f"\n🔍 Embedding向量维度: {len(first_embedding)}")
            print(f"   第一个node: {first_node}")
            print(f"   Embedding前5个值: {first_embedding[:5]}")
        
    except Exception as e:
        print(f"❌ 保存失败: {e}")
    
    # 关闭Neo4j连接
    driver.close()
    print("\n✅ Embedding生成完成!")


if __name__ == "__main__":
    main() 