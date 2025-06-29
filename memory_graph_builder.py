import os
import json
import networkx as nx
from typing import List, Dict, Union
from openai import OpenAI
from dotenv import load_dotenv

class MemoryGraphBuilder:
    def __init__(self, book_content: str, graph_json_path: str = "graph_data.json", graph_image_dir: str = "graphs", env_path: str = ".env"):
        """
        Initialize the graph builder.

        :param book_content: Full story text from which to extract memory graphs.
        :param graph_json_path: Path to save the extracted R graph & L dictionary JSON.
        :param graph_image_dir: Directory to save visualizations of the graphs.
        :param env_path: Path to .env file containing OpenAI API key.
        """
        load_dotenv(env_path, override=True)
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set in the environment.")
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.openai-hub.com/v1")

        self.book_content = book_content
        self.graph_json_path = graph_json_path
        self.graph_image_dir = graph_image_dir

        os.makedirs(self.graph_image_dir, exist_ok=True)

        self.graph_data = None
        self.R_graph_nx = None
        self.L_dict = None

    def save_graph_json(self):
        """Save the extracted graph data to JSON file."""
        with open(self.graph_json_path, "w", encoding="utf-8") as f:
            json.dump(self.graph_data, f, indent=2, ensure_ascii=False)
        print(f"[INFO] Saved graph JSON to {self.graph_json_path}") 