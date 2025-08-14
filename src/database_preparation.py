#!/usr/bin/env python3
"""
Database Preparation Module for Agentic Search

This module handles:
1. Node embedding generation and storage
2. Property key extraction and storage
3. Database schema analysis

All data is cached to avoid repeated processing.
"""

import json
import os
import numpy as np
from datetime import datetime
from typing import Dict, List, Set, Any, Optional
from neo4j import GraphDatabase
from openai import OpenAI

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Manual .env loading as fallback
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()


class DatabasePreparator:
    """Handles database preparation tasks for agentic search"""
    
    def __init__(self, neo4j_uri: str = None, neo4j_user: str = None, 
                 neo4j_password: str = None, neo4j_database: str = None,
                 openai_api_key: str = None):
        """
        Initialize the database preparator
        
        Args:
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username  
            neo4j_password: Neo4j password
            neo4j_database: Neo4j database name
            openai_api_key: OpenAI API key
        """
        # Get connection parameters from environment or arguments
        self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USER", os.getenv("NEO4J_USERNAME", "neo4j"))
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD", "password")
        self.neo4j_database = neo4j_database or os.getenv("NEO4J_DATABASE", "neo4j")
        
        # Initialize connections
        self.driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))
        
        if openai_api_key:
            self.gpt_client = OpenAI(api_key=openai_api_key)
        else:
            self.gpt_client = OpenAI()  # Uses environment variable
        
        # Cache directory
        self.cache_dir = os.path.join(os.path.dirname(__file__), 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        print(f"📊 Database Preparator initialized for database: {self.neo4j_database}")
    
    def get_embedding_filename(self) -> str:
        """Get the embedding cache filename for current database"""
        return os.path.join(self.cache_dir, f"embedding_{self.neo4j_database}.json")
    
    def get_property_keys_filename(self) -> str:
        """Get the property keys cache filename for current database"""
        return os.path.join(self.cache_dir, f"propertykey_{self.neo4j_database}.json")
    
    def extract_all_nodes(self) -> List[Dict[str, Any]]:
        """Extract all nodes from the database with their properties"""
        print("🔍 Extracting all nodes from database...")
        
        nodes = []
        try:
            with self.driver.session(database=self.neo4j_database) as session:
                # Get all nodes with their labels and properties
                query = """
                MATCH (n)
                RETURN id(n) as node_id, 
                       labels(n) as labels, 
                       properties(n) as properties
                """
                
                result = session.run(query)
                for record in result:
                    node_data = {
                        'node_id': record['node_id'],
                        'labels': record['labels'],
                        'properties': record['properties']
                    }
                    nodes.append(node_data)
                
                print(f"✅ Extracted {len(nodes)} nodes from database")
                return nodes
                
        except Exception as e:
            print(f"❌ Error extracting nodes: {e}")
            return []
    
    def generate_node_embeddings(self, nodes: List[Dict[str, Any]]) -> Dict[str, List[float]]:
        """Generate embeddings for all nodes using OpenAI"""
        print("🧠 Generating embeddings for nodes...")
        
        embeddings = {}
        batch_size = 100  # Process in batches to avoid API rate limits
        
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i+batch_size]
            print(f"   Processing batch {i//batch_size + 1}/{(len(nodes) + batch_size - 1)//batch_size}")
            
            try:
                # Prepare text representations for embedding
                texts = []
                node_ids = []
                
                for node in batch:
                    # Create a text representation of the node
                    labels_str = ', '.join(node['labels']) if node['labels'] else 'Unknown'
                    
                    # Extract key properties for text representation
                    props = node['properties']
                    prop_parts = []
                    
                    # Prioritize name, title, or description properties
                    for key in ['name', 'title', 'description', 'type']:
                        if key in props and props[key]:
                            prop_parts.append(f"{key}: {props[key]}")
                    
                    # Add other properties
                    for key, value in props.items():
                        if key not in ['name', 'title', 'description', 'type'] and value:
                            prop_parts.append(f"{key}: {value}")
                    
                    props_str = ', '.join(prop_parts) if prop_parts else 'No properties'
                    
                    # Create text representation
                    text = f"Node labels: {labels_str}. Properties: {props_str}"
                    texts.append(text)
                    node_ids.append(str(node['node_id']))
                
                # Get embeddings from OpenAI
                response = self.gpt_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=texts
                )
                
                # Store embeddings
                for j, embedding_data in enumerate(response.data):
                    node_id = node_ids[j]
                    embeddings[node_id] = embedding_data.embedding
                
            except Exception as e:
                print(f"⚠️ Error generating embeddings for batch {i//batch_size + 1}: {e}")
                continue
        
        print(f"✅ Generated embeddings for {len(embeddings)} nodes")
        return embeddings
    
    def save_embeddings(self, embeddings: Dict[str, List[float]]) -> str:
        """Save embeddings to JSON file"""
        filename = self.get_embedding_filename()
        
        embedding_data = {
            'database': self.neo4j_database,
            'generated_at': datetime.now().isoformat(),
            'total_nodes': len(embeddings),
            'embedding_model': 'text-embedding-3-small',
            'embeddings': embeddings
        }
        
        with open(filename, 'w') as f:
            json.dump(embedding_data, f, indent=2)
        
        print(f"💾 Saved embeddings to: {filename}")
        return filename
    
    def load_embeddings(self) -> Optional[Dict[str, Any]]:
        """Load embeddings from cache if available"""
        filename = self.get_embedding_filename()
        
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                print(f"📂 Loaded cached embeddings from: {filename}")
                print(f"   Database: {data.get('database')}")
                print(f"   Generated: {data.get('generated_at')}")
                print(f"   Total nodes: {data.get('total_nodes')}")
                return data
            except Exception as e:
                print(f"⚠️ Error loading cached embeddings: {e}")
                return None
        else:
            print(f"📂 No cached embeddings found for database: {self.neo4j_database}")
            return None
    
    def extract_property_keys(self) -> Dict[str, Set[str]]:
        """Extract all property keys from the database, organized by node label"""
        print("🗝️ Extracting property keys from database...")
        
        property_keys = {}
        
        try:
            with self.driver.session(database=self.neo4j_database) as session:
                # Get all node labels
                labels_result = session.run("CALL db.labels()")
                labels = [record[0] for record in labels_result]
                
                print(f"   Found node labels: {labels}")
                
                # For each label, get all property keys
                for label in labels:
                    query = f"""
                    MATCH (n:{label})
                    UNWIND keys(n) as key
                    RETURN DISTINCT key
                    ORDER BY key
                    """
                    
                    result = session.run(query)
                    keys = [record['key'] for record in result]
                    property_keys[label] = set(keys)
                    
                    print(f"   {label}: {len(keys)} property keys")
                
                # Also get relationship property keys
                rel_query = """
                MATCH ()-[r]->()
                UNWIND keys(r) as key
                RETURN DISTINCT type(r) as rel_type, collect(DISTINCT key) as keys
                """
                
                rel_result = session.run(rel_query)
                relationship_keys = {}
                for record in rel_result:
                    rel_type = record['rel_type']
                    keys = record['keys']
                    relationship_keys[rel_type] = set(keys)
                
                if relationship_keys:
                    property_keys['_relationships'] = relationship_keys
                    print(f"   Relationships: {len(relationship_keys)} types with properties")
                
                print(f"✅ Extracted property keys for {len(labels)} node types")
                return property_keys
                
        except Exception as e:
            print(f"❌ Error extracting property keys: {e}")
            return {}
    
    def save_property_keys(self, property_keys: Dict[str, Set[str]]) -> str:
        """Save property keys to JSON file"""
        filename = self.get_property_keys_filename()
        
        # Convert sets to lists for JSON serialization
        serializable_keys = {}
        for label, keys in property_keys.items():
            if label == '_relationships':
                serializable_keys[label] = {rel_type: list(rel_keys) for rel_type, rel_keys in keys.items()}
            else:
                serializable_keys[label] = list(keys)
        
        property_data = {
            'database': self.neo4j_database,
            'generated_at': datetime.now().isoformat(),
            'total_labels': len([k for k in property_keys.keys() if k != '_relationships']),
            'property_keys': serializable_keys
        }
        
        with open(filename, 'w') as f:
            json.dump(property_data, f, indent=2)
        
        print(f"💾 Saved property keys to: {filename}")
        return filename
    
    def load_property_keys(self) -> Optional[Dict[str, Any]]:
        """Load property keys from cache if available"""
        filename = self.get_property_keys_filename()
        
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                print(f"📂 Loaded cached property keys from: {filename}")
                print(f"   Database: {data.get('database')}")
                print(f"   Generated: {data.get('generated_at')}")
                print(f"   Total labels: {data.get('total_labels')}")
                return data
            except Exception as e:
                print(f"⚠️ Error loading cached property keys: {e}")
                return None
        else:
            print(f"📂 No cached property keys found for database: {self.neo4j_database}")
            return None
    
    def vector_search(self, query_text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Perform vector search to find most similar nodes
        
        Args:
            query_text: The search query text
            top_k: Number of top results to return
            
        Returns:
            List of similar nodes with similarity scores
        """
        # Load embeddings
        embedding_data = self.load_embeddings()
        if not embedding_data:
            print("⚠️ No embeddings available for vector search")
            return []
        
        embeddings = embedding_data['embeddings']
        
        try:
            # Generate embedding for query
            response = self.gpt_client.embeddings.create(
                model="text-embedding-3-small",
                input=[query_text]
            )
            query_embedding = response.data[0].embedding
            
            # Calculate similarities
            similarities = []
            for node_id, node_embedding in embeddings.items():
                # Calculate cosine similarity
                similarity = np.dot(query_embedding, node_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(node_embedding)
                )
                similarities.append({
                    'node_id': node_id,
                    'similarity': float(similarity)
                })
            
            # Sort by similarity and return top k
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            return similarities[:top_k]
            
        except Exception as e:
            print(f"❌ Error in vector search: {e}")
            return []
    
    def get_node_details(self, node_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get detailed information for specific nodes"""
        if not node_ids:
            return {}
        
        try:
            with self.driver.session(database=self.neo4j_database) as session:
                # Convert string IDs to integers
                int_ids = [int(node_id) for node_id in node_ids]
                
                query = """
                MATCH (n)
                WHERE id(n) IN $node_ids
                RETURN id(n) as node_id, 
                       labels(n) as labels, 
                       properties(n) as properties
                """
                
                result = session.run(query, node_ids=int_ids)
                node_details = {}
                
                for record in result:
                    node_id = str(record['node_id'])
                    node_details[node_id] = {
                        'labels': record['labels'],
                        'properties': record['properties']
                    }
                
                return node_details
                
        except Exception as e:
            print(f"❌ Error getting node details: {e}")
            return {}
    
    def prepare_database(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Main method to prepare database for agentic search
        
        Args:
            force_refresh: If True, regenerate all cached data
            
        Returns:
            Dictionary with preparation status and file paths
        """
        print("🚀 PREPARING DATABASE FOR AGENTIC SEARCH")
        print("=" * 50)
        print(f"Database: {self.neo4j_database}")
        print(f"Force refresh: {force_refresh}")
        print()
        
        result = {
            'database': self.neo4j_database,
            'embeddings_file': None,
            'property_keys_file': None,
            'embeddings_generated': False,
            'property_keys_generated': False,
            'preparation_time': datetime.now().isoformat()
        }
        
        # 1. Handle embeddings
        print("📊 STEP 1: Node Embeddings")
        print("-" * 30)
        
        embeddings_data = None if force_refresh else self.load_embeddings()
        
        if embeddings_data is None:
            print("🔨 Generating new embeddings...")
            nodes = self.extract_all_nodes()
            if nodes:
                embeddings = self.generate_node_embeddings(nodes)
                if embeddings:
                    result['embeddings_file'] = self.save_embeddings(embeddings)
                    result['embeddings_generated'] = True
                else:
                    print("❌ Failed to generate embeddings")
            else:
                print("❌ No nodes found in database")
        else:
            result['embeddings_file'] = self.get_embedding_filename()
            print("✅ Using cached embeddings")
        
        # 2. Handle property keys
        print(f"\n🗝️ STEP 2: Property Keys")
        print("-" * 30)
        
        property_data = None if force_refresh else self.load_property_keys()
        
        if property_data is None:
            print("🔨 Extracting property keys...")
            property_keys = self.extract_property_keys()
            if property_keys:
                result['property_keys_file'] = self.save_property_keys(property_keys)
                result['property_keys_generated'] = True
            else:
                print("❌ Failed to extract property keys")
        else:
            result['property_keys_file'] = self.get_property_keys_filename()
            print("✅ Using cached property keys")
        
        print(f"\n✅ DATABASE PREPARATION COMPLETE")
        print("=" * 50)
        
        return result
    
    def close(self):
        """Clean up database connection"""
        if self.driver:
            self.driver.close()


def main():
    """Test the database preparation functionality"""
    print("🧪 Testing Database Preparation")
    print("=" * 40)
    
    try:
        # Initialize preparator
        preparator = DatabasePreparator()
        
        # Prepare database
        result = preparator.prepare_database()
        
        print(f"\nPreparation result:")
        for key, value in result.items():
            print(f"  {key}: {value}")
        
        # Test vector search
        if result['embeddings_file']:
            print(f"\n🔍 Testing vector search...")
            similar_nodes = preparator.vector_search("archery tournament", top_k=5)
            
            if similar_nodes:
                print(f"Found {len(similar_nodes)} similar nodes:")
                node_ids = [node['node_id'] for node in similar_nodes[:3]]
                node_details = preparator.get_node_details(node_ids)
                
                for i, node in enumerate(similar_nodes[:3]):
                    node_id = node['node_id']
                    similarity = node['similarity']
                    details = node_details.get(node_id, {})
                    
                    print(f"  {i+1}. Node {node_id} (similarity: {similarity:.3f})")
                    if details:
                        print(f"     Labels: {details.get('labels', [])}")
                        print(f"     Properties: {details.get('properties', {})}")
        
        # Close connection
        preparator.close()
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 