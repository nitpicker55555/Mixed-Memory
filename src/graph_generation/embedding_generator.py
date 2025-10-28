"""
Node Embedding Generator for Agentic Search Engine

This module generates semantic embeddings for knowledge graph nodes to enable
similarity-based search and improve the agentic search engine's retrieval capabilities.

The embeddings are generated using OpenAI's text-embedding model and cached
for efficient query-time access.

Author: Yunan Li
Master Thesis Project - Agentic Search Engine
"""

import json
import os
import numpy as np
from typing import Dict, List, Any
from neo4j import GraphDatabase
from openai import OpenAI
from dotenv import load_dotenv
import logging
from dataclasses import dataclass

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class NodeEmbedding:
    """Structured representation of a node embedding."""
    node_id: str
    label: str
    embedding: List[float]
    text_content: str


class EmbeddingGenerator:
    """
    Generate semantic embeddings for graph nodes.
    
    This class creates vector representations of nodes based on their properties,
    enabling similarity-based search and semantic query expansion in the 
    agentic search engine.
    """
    
    def __init__(self, database_name: str = "test9"):
        """
        Initialize the embedding generator.
        
        Args:
            database_name: Name of the Neo4j database
        """
        self.database_name = database_name
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Establish Neo4j connection
        self.driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI'),
            auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
        )
        
        self.embeddings_cache = []

    def generate_text_for_node(self, node_data: Dict[str, Any], label: str) -> str:
        """
        Generate descriptive text for a node to create meaningful embeddings.
        
        This method constructs a natural language description of the node by
        combining its properties in a semantically meaningful way.
        
        Args:
            node_data: Dictionary containing node properties
            label: Node label (Event, Person, Location)
            
        Returns:
            Descriptive text suitable for embedding generation
        """
        if label == "Event":
            # Create comprehensive event description
            parts = []
            
            if node_data.get('name'):
                parts.append(f"Event: {node_data['name']}")
            
            if node_data.get('event_type'):
                parts.append(f"Type: {node_data['event_type']}")
            
            if node_data.get('description'):
                parts.append(f"Description: {node_data['description']}")
            
            if node_data.get('location'):
                parts.append(f"Location: {node_data['location']}")
            
            if node_data.get('date'):
                parts.append(f"Date: {node_data['date']}")
            
            if node_data.get('participants'):
                participants = node_data['participants']
                if participants:
                    parts.append(f"Participants: {', '.join(participants)}")
            
            return ". ".join(parts)
        
        elif label == "Person":
            parts = []
            
            if node_data.get('name'):
                parts.append(f"Person: {node_data['name']}")
            
            if node_data.get('description'):
                parts.append(f"Description: {node_data['description']}")
            
            return ". ".join(parts) if parts else f"Person: {node_data.get('name', 'Unknown')}"
        
        elif label == "Location":
            parts = []
            
            if node_data.get('name'):
                parts.append(f"Location: {node_data['name']}")
            
            if node_data.get('description'):
                parts.append(f"Description: {node_data['description']}")
            
            return ". ".join(parts) if parts else f"Location: {node_data.get('name', 'Unknown')}"
        
        # Default fallback
        return f"{label}: {node_data.get('name', 'Unknown')}"

    def fetch_nodes_for_embedding(self) -> List[Dict[str, Any]]:
        """
        Fetch all nodes from the database for embedding generation.
        
        Returns:
            List of dictionaries containing node information
        """
        nodes = []
        
        with self.driver.session(database=self.database_name) as session:
            # Retrieve all nodes with their properties
            result = session.run("""
                MATCH (n)
                RETURN elementId(n) as node_id, labels(n) as labels, properties(n) as props
            """)
            
            for record in result:
                node_id = record["node_id"]
                labels = record["labels"]
                props = record["props"]
                
                # Use primary label (first in list)
                primary_label = labels[0] if labels else "Unknown"
                
                nodes.append({
                    "node_id": node_id,
                    "label": primary_label,
                    "properties": props
                })
        
        logger.info(f"Fetched {len(nodes)} nodes for embedding")
        return nodes

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts using OpenAI API.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
                encoding_format="float"
            )
            
            embeddings = [item.embedding for item in response.data]
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return []

    def process_all_nodes(self) -> None:
        """
        Process all nodes and generate embeddings.
        
        This method fetches all nodes from the database, generates descriptive
        text for each node, and creates embeddings using the OpenAI API.
        """
        logger.info("Starting embedding generation for all nodes...")
        
        # Fetch nodes from database
        nodes = self.fetch_nodes_for_embedding()
        
        # Prepare texts for embedding
        texts = []
        node_info = []
        
        for node in nodes:
            text = self.generate_text_for_node(node["properties"], node["label"])
            texts.append(text)
            node_info.append({
                "node_id": node["node_id"],
                "label": node["label"],
                "text": text
            })
        
        # Generate embeddings in batches (API has batch size limits)
        batch_size = 100
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
            
            batch_embeddings = self.generate_embeddings_batch(batch_texts)
            all_embeddings.extend(batch_embeddings)
        
        # Store embeddings in cache
        for i, embedding in enumerate(all_embeddings):
            node_embedding = NodeEmbedding(
                node_id=node_info[i]["node_id"],
                label=node_info[i]["label"],
                embedding=embedding,
                text_content=node_info[i]["text"]
            )
            self.embeddings_cache.append(node_embedding)
        
        logger.info(f"Generated {len(self.embeddings_cache)} embeddings")

    def save_embeddings_to_cache(self) -> None:
        """
        Save embeddings to cache files for search engine usage.
        
        This method creates two cache formats:
        1. JSON format for compatibility and inspection
        2. Compressed NumPy format for efficient loading
        """
        cache_dir = "/Users/yunanli/Desktop/MasterThesisNew/AgenticSearch/cache"
        os.makedirs(cache_dir, exist_ok=True)
        
        # Prepare embeddings data
        embeddings_data = {}
        
        for node_embedding in self.embeddings_cache:
            embeddings_data[node_embedding.node_id] = {
                "label": node_embedding.label,
                "embedding": node_embedding.embedding,
                "text_content": node_embedding.text_content
            }
        
        # Save as JSON
        cache_file = f"{cache_dir}/embeddings_{self.database_name}.json"
        with open(cache_file, 'w') as f:
            json.dump(embeddings_data, f, indent=2)
        
        logger.info(f"Embeddings saved to {cache_file}")
        
        # Save as compressed NumPy array for faster loading
        numpy_file = f"{cache_dir}/embeddings_{self.database_name}.npz"
        
        try:
            node_ids = [emb.node_id for emb in self.embeddings_cache]
            embeddings_matrix = np.array([emb.embedding for emb in self.embeddings_cache])
            
            np.savez_compressed(
                numpy_file,
                node_ids=node_ids,
                embeddings=embeddings_matrix,
                labels=[emb.label for emb in self.embeddings_cache]
            )
            
            logger.info(f"Numpy embeddings saved to {numpy_file}")
            
        except Exception as e:
            logger.warning(f"Could not save numpy embeddings: {e}")

    def update_graph_with_embeddings(self) -> None:
        """
        Optionally store embeddings directly in the Neo4j graph.
        
        Note: This method stores embeddings as JSON strings in the graph.
        For most use cases, the cached files are sufficient and more efficient.
        """
        logger.info("Updating graph nodes with embeddings...")
        
        with self.driver.session(database=self.database_name) as session:
            for node_embedding in self.embeddings_cache:
                # Convert embedding to JSON string for storage
                embedding_str = json.dumps(node_embedding.embedding)
                
                session.run("""
                    MATCH (n)
                    WHERE elementId(n) = $node_id
                    SET n.embedding = $embedding, n.embedding_text = $text
                """,
                    node_id=node_embedding.node_id,
                    embedding=embedding_str,
                    text=node_embedding.text_content
                )
        
        logger.info("Graph updated with embeddings")

    def generate_statistics(self) -> Dict[str, Any]:
        """
        Generate statistics about the embeddings.
        
        Returns:
            Dictionary containing embedding count, dimension, and label distribution
        """
        if not self.embeddings_cache:
            return {"error": "No embeddings generated"}
        
        stats = {
            "total_embeddings": len(self.embeddings_cache),
            "embedding_dimension": len(self.embeddings_cache[0].embedding),
            "labels_distribution": {}
        }
        
        # Count embeddings by label
        for emb in self.embeddings_cache:
            label = emb.label
            stats["labels_distribution"][label] = stats["labels_distribution"].get(label, 0) + 1
        
        return stats

    def close(self) -> None:
        """Close database connection."""
        self.driver.close()


def main():
    """Main function for standalone execution."""
    import sys
    
    # Get database name from command line argument
    database_name = sys.argv[1] if len(sys.argv) > 1 else "test9"
    
    logger.info("Starting Node Embedding Generation")
    logger.info(f"Database: {database_name}")
    
    generator = EmbeddingGenerator(database_name)
    
    try:
        # Process all nodes and generate embeddings
        generator.process_all_nodes()
        
        # Save embeddings to cache files
        generator.save_embeddings_to_cache()
        
        # Optionally update graph (disabled by default)
        # generator.update_graph_with_embeddings()
        
        # Display statistics
        stats = generator.generate_statistics()
        logger.info("Embedding Generation Statistics:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
        
        logger.info("Embedding generation completed successfully")
        
    except Exception as e:
        logger.error(f"Error during embedding generation: {e}")
        raise
    finally:
        generator.close()


if __name__ == "__main__":
    main()
