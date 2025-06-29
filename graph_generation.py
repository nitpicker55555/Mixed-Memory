import os
import json
import networkx as nx
import matplotlib.pyplot as plt
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

    def extract_graph_elements(self):
        prompt = f"""
You are an intelligent memory extraction agent. Read the following text and extract structured memory data.

## Text:
\"\"\" 
{self.book_content}
\"\"\"

## Your Task:
Extract two structures: R_Graph and L_Dictionary.

### R_Graph
- Describe **relationships between two entities over time**.
- Each entry should look like this:

{{
  "E1": "Entity A",
  "E2": "Entity B",
  "R": [
    {{
      "time": "2024-01",
      "relationship": "met",
      "event": "Entity A met Entity B at a conference."
    }},
    {{
      "time": "2025-03",
      "relationship": "collaborated with",
      "event": "They collaborated on a project."
    }}
  ]
}}

### L_Dictionary
- Your task is to categorize all named entities in the text by assigning one or more meaningful **semantic labels** to each entity.
- These labels represent **what the entity is**, or **what role/function** it plays in the described context.

- Be **analytical and imaginative** in your labeling:
  - Go beyond generic types like "Person", "Place", or "Object".
  - Include **abstract roles**, **functional identities**, **social positions**, **professions**, **categories**, or **semantic types**.

- Examples of labels:
  - "Person", "Instructor", "Athlete", "Friend", "Location", "Event", "Historical Site", "Organization", "Landmark", "Tool", "Vehicle", "Food", "Emotion", "Activity", "Pet", etc.
  - If someone is teaching parkour, labels like "Coach", "Instructor", and "Athlete" are all valid.
  - A park might be both a "Location" and a "Recreational Area".

- If an entity fits into multiple categories, include multiple label entries for the same entity (one for each label).
- Provide the **time** associated with the label if mentioned or implied.

- Format each entry as:
  {{
    "Label": "Instructor",
    "Entity": "Noa Middleton",
    "time": "2025-09-13"
  }}


### Output:
Return only JSON with keys `"R"` and `"L"`. No explanations.
"""
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[len("```json"):].strip()
        if content.endswith("```"):
            content = content[:-3].strip()

        try:
            self.graph_data = json.loads(content)
        except json.JSONDecodeError as e:
            print("[ERROR] Failed to parse JSON output.")
            print("[DEBUG] Raw content:\n", content[:500])
            raise e

    def build_r_graph(self) -> nx.MultiDiGraph:
        G = nx.MultiDiGraph()
        for entry in self.graph_data["R"]:
            E1 = entry["E1"]
            E2 = entry["E2"]
            for r in entry.get("R", []):
                G.add_node(E1, type="entity")
                G.add_node(E2, type="entity")
                G.add_edge(
                    E1, E2,
                    time=r.get("time", ""),
                    relationship=r.get("relationship", ""),
                    event=r.get("event", "")
                )
        self.R_graph_nx = G
        return G

    def build_l_dict(self) -> dict:
        L_dict = {}
        for entry in self.graph_data["L"]:
            label = entry["Label"]
            entity = entry["Entity"]
            time = entry["time"]
            
            if entity not in L_dict:
                L_dict[entity] = []
            
            L_dict[entity].append({
                "label": label,
                "time": time
            })
        self.L_dict = L_dict
        return L_dict

    def save_graph_json(self):
        with open(self.graph_json_path, "w", encoding="utf-8") as f:
            json.dump(self.graph_data, f, indent=2, ensure_ascii=False)
        print(f"[INFO] Saved graph JSON to {self.graph_json_path}")

    def visualize_graph(self, G: nx.MultiDiGraph, title: str):
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(G, seed=42)

        node_colors = [
            "skyblue" if attr.get("type") == "label" else "orange"
            for _, attr in G.nodes(data=True)
        ]

        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=800, alpha=0.9)
        nx.draw_networkx_labels(G, pos, font_size=10, font_weight="bold")

        edge_labels = {
            (u, v, k): f"{data.get('time', '')}: {data.get('relationship', '')}"
            for u, v, k, data in G.edges(keys=True, data=True)
        }

        nx.draw_networkx_edges(G, pos, arrows=True, arrowstyle="->", connectionstyle="arc3,rad=0.1")
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=9)

        plt.title(title)
        plt.axis("off")
        plt.tight_layout()
        output_path = os.path.join(self.graph_image_dir, f"{title.replace(' ', '_')}.png")
        plt.savefig(output_path)
        print(f"[INFO] Saved graph visualization to {output_path}")
        plt.close()

    def run(self):
        """
        Run the full pipeline: extract, build, save, visualize.
        """
        print("[INFO] Extracting structured memory graphs......")
        self.extract_graph_elements()
        print("[INFO] Building R graph and L dictionary...")
        self.save_graph_json()
        self.build_r_graph()
        self.build_l_dict()
        # self.save_graph_json()
        print("[INFO] Visualizing graphs...")
        self.visualize_graph(self.R_graph_nx, "R Graph")
        
        # Display L dictionary
        if self.L_dict:
            print("\n=== L Dictionary ===")
            for entity, labels in self.L_dict.items():
                print(f"{entity}:")
                for label_info in labels:
                    print(f"  - {label_info['label']} (time: {label_info['time']})")
