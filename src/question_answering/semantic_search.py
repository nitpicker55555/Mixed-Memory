"""
Semantic Search Module

This module provides semantic search capabilities using embeddings
and keyword similarity matching for the agentic search engine.
"""

import os
import json
from typing import Dict, List, Optional
import numpy as np
from openai import OpenAI


class SemanticSearchEngine:
    """
    Semantic search using pre-computed embeddings.
    
    This class loads node embeddings and provides similarity-based
    search functionality to find relevant events.
    """
    
    def __init__(self, database_name: str, client: OpenAI):
        """
        Initialize semantic search engine.
        
        Args:
            database_name: Name of the Neo4j database
            client: OpenAI client for generating query embeddings
        """
        self.database_name = database_name
        self.client = client
        self.embeddings = None
        self.event_data = []
        
        self._load_embeddings()
    
    def _load_embeddings(self) -> None:
        """Load pre-computed node embeddings from cache files."""
        try:
            # Construct file paths
            embedding_file = f"../../cache/embeddings_{self.database_name}.npz"
            json_file = f"../../cache/embeddings_{self.database_name}.json"
            
            if os.path.exists(embedding_file) and os.path.exists(json_file):
                # Load embeddings matrix
                data = np.load(embedding_file)
                self.embeddings = data['embeddings']
                
                # Load node data
                with open(json_file, 'r', encoding='utf-8') as f:
                    self.event_data = json.load(f)
                
                print(f"Loaded {len(self.event_data)} node embeddings for semantic search")
            else:
                print(f"Warning: No embedding files found for database {self.database_name}")
                self.embeddings = None
                self.event_data = []
                
        except Exception as e:
            print(f"Warning: Failed to load embeddings: {e}")
            self.embeddings = None
            self.event_data = []
    
    def search(self, query_text: str, top_k: int = 5, similarity_threshold: float = 0.5) -> List[Dict]:
        """
        Perform semantic search to find similar events.
        
        Args:
            query_text: Text query to search for
            top_k: Number of top results to return
            similarity_threshold: Minimum cosine similarity threshold
            
        Returns:
            List of search results with similarity scores
        """
        if self.embeddings is None or not self.event_data:
            return []
        
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            
            # Generate query embedding
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=query_text
            )
            query_embedding = np.array(response.data[0].embedding).reshape(1, -1)
            
            # Calculate cosine similarity
            similarities = cosine_similarity(query_embedding, self.embeddings)[0]
            
            # Find top matches above threshold
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                if similarities[idx] > similarity_threshold:
                    node_data = self.event_data[idx]
                    results.append({
                        'node_data': node_data,
                        'similarity': float(similarities[idx]),
                        'text': node_data.get('text', ''),
                        'node_type': node_data.get('node_type', ''),
                        'properties': node_data.get('properties', {})
                    })
            
            return results
            
        except Exception as e:
            print(f"Warning: Semantic search failed: {e}")
            return []


class KeywordSemanticSearcher:
    """
    Keyword-based semantic search for query enhancement.
    
    This class provides functionality to find semantically similar
    keywords and suggest better search terms.
    """
    
    def __init__(self, database_name: str):
        """
        Initialize keyword semantic searcher.
        
        Args:
            database_name: Name of the Neo4j database
        """
        self.database_name = database_name
        self.loaded = False
        self.keyword_embeddings = None
        self.keywords = []
        
        self._load_keyword_embeddings()
    
    def _load_keyword_embeddings(self) -> None:
        """Load keyword embeddings from cache."""
        try:
            embedding_file = f"../../embeddings/keyword_embeddings_{self.database_name}.npz"
            json_file = f"../../embeddings/keyword_embeddings_{self.database_name}.json"
            
            if os.path.exists(embedding_file) and os.path.exists(json_file):
                # Load embeddings
                data = np.load(embedding_file)
                self.keyword_embeddings = data['embeddings']
                
                # Load keywords
                with open(json_file, 'r', encoding='utf-8') as f:
                    keyword_data = json.load(f)
                    self.keywords = keyword_data.get('keywords', [])
                
                self.loaded = True
                print(f"Keyword semantic searcher loaded for {self.database_name}")
            else:
                print(f"Warning: No keyword embeddings found for database {self.database_name}")
                
        except Exception as e:
            print(f"Warning: Failed to load keyword embeddings: {e}")
            self.loaded = False
    
    def find_similar_keywords(self, keyword: str, top_k: int = 3, 
                             similarity_threshold: float = 0.6) -> List[Dict]:
        """
        Find semantically similar keywords.
        
        Args:
            keyword: Keyword to find matches for
            top_k: Number of results to return
            similarity_threshold: Minimum similarity threshold
            
        Returns:
            List of similar keywords with similarity scores
        """
        if not self.loaded or self.keyword_embeddings is None:
            return []
        
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            
            # Find keyword in list
            if keyword in self.keywords:
                idx = self.keywords.index(keyword)
                keyword_embedding = self.keyword_embeddings[idx].reshape(1, -1)
            else:
                # If keyword not in list, return empty
                return []
            
            # Calculate similarities
            similarities = cosine_similarity(keyword_embedding, self.keyword_embeddings)[0]
            
            # Find top matches
            top_indices = np.argsort(similarities)[::-1][1:top_k+1]  # Skip self
            
            results = []
            for idx in top_indices:
                if similarities[idx] >= similarity_threshold:
                    results.append({
                        'keyword': self.keywords[idx],
                        'similarity': float(similarities[idx])
                    })
            
            return results
            
        except Exception as e:
            print(f"Warning: Keyword similarity search failed: {e}")
            return []


def enhance_keyword_with_semantics(keyword_searcher: Optional[KeywordSemanticSearcher], 
                                  keyword: str) -> Dict[str, str]:
    """
    Enhance a keyword using semantic search to find better alternatives.
    
    Args:
        keyword_searcher: KeywordSemanticSearcher instance or None
        keyword: Keyword to enhance
        
    Returns:
        Dictionary with enhanced keyword and suggested search field
    """
    if not keyword_searcher or not keyword:
        return {"keyword": keyword, "field": "event_type"}
    
    try:
        # Find similar keywords
        similar_keywords = keyword_searcher.find_similar_keywords(
            keyword, top_k=3, similarity_threshold=0.6
        )
        
        if similar_keywords:
            best_match = similar_keywords[0]
            best_keyword = best_match['keyword']
            
            # Determine search field based on keyword length
            # Longer keywords are likely event names, shorter are types
            search_field = "name" if len(best_keyword.split()) > 2 else "event_type"
            
            print(f"Found semantic replacement: '{keyword}' -> '{best_keyword}' "
                  f"(field: {search_field}, similarity: {best_match['similarity']:.3f})")
            
            return {"keyword": best_keyword, "field": search_field}
        
        return {"keyword": keyword, "field": "event_type"}
        
    except Exception as e:
        print(f"Warning: Keyword enhancement failed: {e}")
        return {"keyword": keyword, "field": "event_type"}

