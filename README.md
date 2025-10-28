# AgenticSearch

An agentic search system for querying knowledge graphs built from narrative text using Neo4j and OpenAI.

## Quick Setup

1. **Install dependencies:**
   ```bash
   pip install python-dotenv openai neo4j numpy
   ```

2. **Configure environment** - Create `.env` file:
   ```env
   OPENAI_API_KEY=your_openai_key
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   ```

3. **Start Neo4j** and ensure it's running on `bolt://localhost:7687`

## Data Locations

### Books
- **13-chapter book**: `data/book_gpt4omini_13chapters.json`
- **196-chapter book**: `data/book_claude_196chapters.json`

### Questions
- **13-chapter questions**: `data/questions_gpt4omini_13chapters.json`
- **196-chapter questions**: `data/questions_claude_196chapters.json`

### Results
- **13-chapter results**: `results13Chapters/`
- **196-chapter results**: `result196Chapters/`

### Cache
- **Embeddings**: `cache/embeddings/` (generated automatically)
- **Neo4j exports**: `cache/neo4j/` (database backups in JSON format)

## Usage

### 1. Generate Knowledge Graph

```bash
cd src/graph_generation

# For 13-chapter book:
python dynamic_graph_generator.py \
  --book-path ../../data/book_gpt4omini_13chapters.json \
  --database your_database_name

# For 196-chapter book:
python dynamic_graph_generator.py \
  --book-path ../../data/book_claude_196chapters.json \
  --database your_database_name
```

This creates:
- Event, Person, and Location nodes in Neo4j
- Relationships between entities
- Embeddings in `cache/embeddings/`

### 2. Run Agentic Search

```bash
cd src/question_answering

# Basic usage:
python agentic_search_engine_refactored.py \
  --database your_database_name \
  --questions ../../data/questions_gpt4omini_13chapters.json \
  --range 1-10

# Save results to folder:
python agentic_search_engine_refactored.py \
  --database your_database_name \
  --questions ../../data/questions_gpt4omini_13chapters.json \
  --range 1-10 \
  --output ../../results13Chapters/
```

**Output files:**
- `questions_X_Y_results_TIMESTAMP.json` - Complete results with all iterations
- `report_X_Y_TIMESTAMP.txt` - Human-readable summary report

## Restoring Neo4j Database

If you have exported databases in `cache/neo4j/`:

1. **From Neo4j Browser:**
   ```cypher
   CREATE DATABASE your_database_name;
   ```

2. **Import using Python:**
   ```python
   import json
   from neo4j import GraphDatabase
   
   # Load export
   with open('cache/neo4j/database13questions/complete_export.json') as f:
       data = json.load(f)
   
   # Connect and import (write your own import script based on the JSON structure)
   ```

3. **Or regenerate** using the graph generation script (recommended)

## Project Structure

```
AgenticSearch/
├── data/                           # Input data
│   ├── book_gpt4omini_13chapters.json
│   ├── book_claude_196chapters.json
│   ├── questions_gpt4omini_13chapters.json
│   └── questions_claude_196chapters.json
├── src/
│   ├── graph_generation/
│   │   └── dynamic_graph_generator.py    # Generate knowledge graphs
│   └── question_answering/
│       └── agentic_search_engine_refactored.py  # Run queries
├── cache/
│   ├── embeddings/                 # Generated embeddings (auto)
│   └── neo4j/                     # Database exports
├── results13Chapters/              # Results for 13-chapter book
├── result196Chapters/              # Results for 196-chapter book
└── .env                           # Your configuration (not in repo)
```

## Common Workflows

### Complete Pipeline for New Book

```bash
# 1. Generate graph
cd src/graph_generation
python dynamic_graph_generator.py \
  --book-path ../../data/your_book.json \
  --database mydb

# 2. Run questions
cd ../question_answering
python agentic_search_engine_refactored.py \
  --database mydb \
  --questions ../../data/your_questions.json \
  --output ../../results/
```

### Test with Small Question Range

```bash
python agentic_search_engine_refactored.py \
  --database mydb \
  --questions ../../data/questions_gpt4omini_13chapters.json \
  --range 1-5
```

### Run All Questions

```bash
python agentic_search_engine_refactored.py \
  --database mydb \
  --questions ../../data/questions_gpt4omini_13chapters.json \
  --output ../../results/
```

## Requirements

- Python 3.8+
- Neo4j 5.0+
- OpenAI API key

**Python packages:**
- `python-dotenv` - Environment variables
- `openai` - OpenAI API client
- `neo4j` - Neo4j Python driver
- `numpy` - Array operations for embeddings

## Troubleshooting

**Neo4j connection error:**
- Check Neo4j is running
- Verify `.env` credentials

**OpenAI API error:**
- Check `OPENAI_API_KEY` in `.env`
- Verify API key is active

**No results found:**
- Ensure database has been generated
- Check embeddings exist in `cache/embeddings/`
- Verify database name matches

**Missing embeddings:**
- Run graph generation script - it creates embeddings automatically

## License

Master's Thesis Project - See institution guidelines for usage terms.

