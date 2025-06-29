import os
import matplotlib.pyplot as plt
import networkx as nx
from memory_graph_builder import MemoryGraphBuilder

def visualize_graph(G: nx.MultiDiGraph, title: str, output_dir: str = "graphs"):
    """
    Visualize a graph and save it as an image.
    
    :param G: NetworkX graph to visualize
    :param title: Title for the graph
    :param output_dir: Directory to save the visualization
    """
    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(G, seed=42)

    # Color nodes based on their type
    node_colors = [
        "skyblue" if attr.get("type") == "label" else "orange"
        for _, attr in G.nodes(data=True)
    ]

    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=800, alpha=0.9)
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight="bold")

    # Draw edges with labels
    edge_labels = {
        (u, v, k): f"{data.get('time', '')}: {data.get('relationship', '')}"
        for u, v, k, data in G.edges(keys=True, data=True)
    }

    nx.draw_networkx_edges(G, pos, arrows=True, arrowstyle="->", connectionstyle="arc3,rad=0.1")
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=9)

    plt.title(title)
    plt.axis("off")
    plt.tight_layout()
    
    # Save the visualization
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{title.replace(' ', '_')}.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"[INFO] Saved graph visualization to {output_path}")
    plt.close()

def visualize_all_graphs(builder: MemoryGraphBuilder):
    """
    Visualize R graph and display L dictionary.
    
    :param builder: MemoryGraphBuilder instance
    """
    print("[INFO] Visualizing graphs and displaying dictionary...")
    
    if builder.R_graph_nx:
        visualize_graph(builder.R_graph_nx, "R Graph", builder.graph_image_dir)
    else:
        print("[WARNING] R graph not available for visualization")
    
    if builder.L_dict:
        print("\n=== L Dictionary ===")
        for entity, labels in builder.L_dict.items():
            print(f"{entity}:")
            for label_info in labels:
                print(f"  - {label_info['label']} (time: {label_info['time']})")
    else:
        print("[WARNING] L dictionary not available")

def create_graph_summary(builder: MemoryGraphBuilder):
    """
    Create a summary of the graphs and dictionary.
    
    :param builder: MemoryGraphBuilder instance
    """
    print("\n=== Summary ===")
    
    if builder.R_graph_nx:
        print(f"R Graph: {builder.R_graph_nx.number_of_nodes()} nodes, {builder.R_graph_nx.number_of_edges()} edges")
        print("R Graph nodes:", list(builder.R_graph_nx.nodes())[:10])  # Show first 10 nodes
    else:
        print("R Graph: Not built")
    
    if builder.L_dict:
        total_labels = sum(len(labels) for labels in builder.L_dict.values())
        print(f"L Dictionary: {len(builder.L_dict)} entities, {total_labels} total labels")
        print("L Dictionary entities:", list(builder.L_dict.keys())[:10])  # Show first 10 entities
    else:
        print("L Dictionary: Not built")

if __name__ == "__main__":
    # Example usage
    import networkx as nx
    
    # Create a sample graph for testing
    G = nx.MultiDiGraph()
    G.add_node("Alice", type="entity")
    G.add_node("Bob", type="entity")
    G.add_node("Person", type="label")
    G.add_edge("Alice", "Bob", time="2024-01", relationship="met")
    G.add_edge("Person", "Alice", time="2024-01")
    
    # Test visualization
    visualize_graph(G, "Test Graph") 