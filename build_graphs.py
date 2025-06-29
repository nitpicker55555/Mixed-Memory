import networkx as nx
from memory_graph_builder import MemoryGraphBuilder

def build_r_graph(builder: MemoryGraphBuilder) -> nx.MultiDiGraph:
    """
    Build R graph (relationship graph) from extracted data.
    
    :param builder: MemoryGraphBuilder instance
    :return: NetworkX MultiDiGraph representing relationships
    """
    G = nx.MultiDiGraph()
    
    if not builder.graph_data or "R" not in builder.graph_data:
        print("[WARNING] No R graph data available")
        return G
    
    for entry in builder.graph_data["R"]:
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
    
    builder.R_graph_nx = G
    print(f"[INFO] Built R graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
    return G

def build_l_dict(builder: MemoryGraphBuilder) -> dict:
    """
    Build L dictionary (label dictionary) from extracted data.
    
    :param builder: MemoryGraphBuilder instance
    :return: Dictionary representing entity labels
    """
    L_dict = {}
    
    if not builder.graph_data or "L" not in builder.graph_data:
        print("[WARNING] No L dictionary data available")
        return L_dict
    
    for entry in builder.graph_data["L"]:
        label = entry["Label"]
        entity = entry["Entity"]
        time = entry["time"]
        
        if entity not in L_dict:
            L_dict[entity] = []
        
        L_dict[entity].append({
            "label": label,
            "time": time
        })
    
    builder.L_dict = L_dict
    print(f"[INFO] Built L dictionary with {len(L_dict)} entities and {sum(len(labels) for labels in L_dict.values())} total labels")
    return L_dict

def build_all_graphs(builder: MemoryGraphBuilder):
    """
    Build R graph and L dictionary.
    
    :param builder: MemoryGraphBuilder instance
    """
    print("[INFO] Building R graph and L dictionary...")
    build_r_graph(builder)
    build_l_dict(builder)

if __name__ == "__main__":
    # Example usage
    sample_content = "This is a sample book content for testing."
    builder = MemoryGraphBuilder(sample_content)
    
    # Mock graph data for testing
    builder.graph_data = {
        "R": [
            {
                "E1": "Alice",
                "E2": "Bob",
                "R": [
                    {
                        "time": "2024-01",
                        "relationship": "met",
                        "event": "Alice met Bob at a conference."
                    }
                ]
            }
        ],
        "L": [
            {
                "Label": "Person",
                "Entity": "Alice",
                "time": "2024-01"
            },
            {
                "Label": "Student",
                "Entity": "Alice",
                "time": "2024-01"
            }
        ]
    }
    
    build_all_graphs(builder)
    print("L Dictionary:", builder.L_dict) 