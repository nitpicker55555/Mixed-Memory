# Memory Graph Project

This project implements a memory graph system for processing and analyzing episodic memory data from books and events. It provides tools for building, visualizing, and analyzing memory graphs based on narrative content.

## Repository

This project is hosted on GitHub: [https://github.com/nitpicker55555/Mixed-Memory.git](https://github.com/nitpicker55555/Mixed-Memory.git)

## Project Structure

```
MemoryGraph/
├── data/                          # Data files
│   ├── books/                     # Generated book content
│   ├── events.json               # Event data
│   ├── graph_answers/            # Graph answer data
│   └── meta_events.json          # Meta event data
├── memory_graph_builder.py        # Main memory graph builder class
├── extract_graph_elements.py      # Graph element extraction functions
├── build_graphs.py               # R graph and L dictionary building
├── visualize_graphs.py           # Graph visualization functions
├── process_data.py               # Data processing and analysis
├── main.py                       # Main pipeline script
├── graph_generation.py           # Original graph generation script
└── README.md                     # This file
```

## Features

- **Memory Graph Construction**: Builds R graphs (relationship networks) and L dictionaries (semantic labels)
- **Data Processing**: Loads and processes events, meta-events, books, and graph answers
- **Visualization**: Creates visual representations of memory graphs
- **Analysis Tools**: Provides utilities for analyzing graph structures and relationships

## Data Format

### Events (`events.json`)
Contains event data with timestamps, descriptions, and relationships.

### Meta Events (`meta_events.json`)
Contains higher-level event groupings and semantic information.

### Books
Structured book content with chapters, paragraphs, and metadata.

### Graph Answers (`graph_answers/`)
Contains graph-based question-answer pairs for evaluation.

## Usage

### Basic Usage

```python
from process_data import DataProcessor

# Initialize data processor
processor = DataProcessor()

# Load all data
events, meta_events, books, graph_answers = processor.load_all_data()

# Create story text from events
story_text = processor.create_story_text(events)

# Generate memory graph
from memory_graph_builder import MemoryGraphBuilder
builder = MemoryGraphBuilder()
R_graph, L_dict = builder.build_memory_graph(story_text)
```

### Running the Main Pipeline

```bash
python main.py
```

### Data Processing

```bash
python process_data.py
```

## Dependencies

- NetworkX (for graph operations)
- Matplotlib (for visualization)
- Pandas (for data processing)
- JSON (for data loading)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/nitpicker55555/Mixed-Memory.git
cd Mixed-Memory
```

2. Install dependencies:
```bash
pip install networkx matplotlib pandas
```

## Contributing

This project is part of a master's thesis on episodic memory benchmarking. For questions or contributions, please contact the repository owner.

## License

This project is for academic research purposes. 