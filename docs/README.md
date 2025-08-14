# Agentic Search Engine

An intelligent, React-style agentic search system for Neo4j knowledge graphs that implements dynamic query generation with vector search and schema-aware Cypher generation.

## Features

- **React-style Search Loop**: Observe → Think → Act → Reflect
- **Vector Search**: Pre-filters relevant nodes using OpenAI embeddings
- **Schema-aware Queries**: Uses actual database schema to generate valid Cypher queries
- **Self-evaluation**: Dynamic confidence scoring and result evaluation
- **Zero Hardcoding**: All queries generated dynamically by GPT-4
- **Caching**: Automatic caching of embeddings and schema metadata

## Quick Start

### 1. Environment Setup

```bash
# Activate conda environment (if using)
conda activate cv3

# Create .env file with your credentials
cat > .env << EOF
OPENAI_API_KEY=your_openai_api_key
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=your_database_name
EOF
```

### 2. Run Batch Processing

```bash
# Process questions 1-20
python run_agentic_batch.py --questions ../Mixed-Memory/data/questions_new_book.json --range 1-20 --output results/

# Process specific questions
python run_agentic_batch.py --questions ../Mixed-Memory/data/questions_new_book.json --range 1,5,10-15 --output results/

# Quiet mode (less verbose output)
python run_agentic_batch.py --questions ../Mixed-Memory/data/questions_new_book.json --range 1-10 --quiet
```

### 3. Use Programmatically

```python
from agentic_search_engine import AgenticSearchEngine

# Initialize engine
engine = AgenticSearchEngine(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j", 
    neo4j_password="your_password",
    neo4j_database="your_database"
)

# Search for answers
result = engine.search("What events happened at Queensboro Bridge?")
print(f"Answer: {result['final_answer']}")
print(f"Confidence: {result['confidence_score']}")

# Close connection
engine.close()
```

## Core Components

### 1. Database Preparation (`database_preparation.py`)
- **Node Embeddings**: Generates and caches vector embeddings for all nodes
- **Schema Extraction**: Extracts and caches all property keys and relationship types
- **Vector Search**: Performs similarity search to find relevant nodes

### 2. Agentic Search Engine (`agentic_search_engine.py`)
- **SearchState**: Manages session state and search context
- **StrategySelector**: Dynamically selects search strategies
- **CypherQueryGenerator**: Generates schema-aware Cypher queries
- **ResultEvaluator**: Evaluates results and determines confidence

### 3. Batch Runner (`run_agentic_batch.py`)
- **Flexible Range Parsing**: `1-20`, `1,5,10-15`, `1-10,20-30`
- **Multiple Output Formats**: JSON, TXT report, CSV summary
- **Error Handling**: Graceful failure recovery
- **Progress Tracking**: Real-time processing updates

### 4. QA Interface (`agentic_qa_interface.py`)
- **Legacy Compatibility**: Drop-in replacement for existing QA systems
- **Batch Processing**: Process multiple questions with accuracy calculation
- **Report Generation**: Detailed analysis reports

## Search Strategies

The system dynamically selects from these strategies:

- **entity_focused**: Direct entity extraction and analysis
- **relationship_focused**: Explores connections between entities
- **temporal_focused**: Time-based event analysis
- **location_focused**: Geographic/venue-based queries
- **broad_exploration**: Wide-scope information gathering
- **constraint_refinement**: Narrowing search with specific constraints
- **pattern_matching**: Template-based query generation

## Performance Metrics

Recent test results (Questions 1-10):
- **Success Rate**: 100% (10/10)
- **Average Confidence**: 0.85
- **Average Iterations**: 1.6 per question
- **Processing Time**: ~32 seconds per question

## Architecture

```
Question Input
     ↓
Vector Search (find relevant nodes)
     ↓
Strategy Selection (GPT-4)
     ↓
Query Generation (schema-aware GPT-4)
     ↓
Cypher Execution
     ↓
Result Evaluation (GPT-4)
     ↓
Answer Output OR Iterate with new strategy
```

## Caching System

The system automatically caches:
- **Node Embeddings**: `cache/embedding_{database_name}.json`
- **Property Keys**: `cache/propertykey_{database_name}.json`

Caches are automatically used on subsequent runs. Use `force_refresh=True` to regenerate.

## Output Formats

### JSON Results
Complete technical results with metadata:
```json
{
  "session_id": "uuid",
  "question": "question text",
  "final_answer": "answer",
  "confidence_score": 0.95,
  "total_iterations": 2,
  "search_successful": true,
  "reasoning_chain": ["step1", "step2"],
  "query_history": ["query1", "query2"]
}
```

### Human-Readable Report
```
Question 1:
  Text: What events happened at Queensboro Bridge?
  Predicted: Archery Tournament events
  Success: True
  Confidence: 0.95
  Iterations: 1
```

### CSV Summary
Spreadsheet-compatible format for analysis and comparison.

## Requirements

- Python 3.8+
- Neo4j database
- OpenAI API key
- Required packages: `neo4j`, `openai`, `python-dotenv`, `numpy`

## Integration

The agentic search can be integrated into existing systems:

```python
from agentic_qa_interface import AgenticQuestionAnalyzer

# Drop-in replacement for traditional QA systems
analyzer = AgenticQuestionAnalyzer()
result = analyzer.analyze_question("Your question here")
```

## Error Handling

The system includes robust error handling:
- **Neo4j Connection**: Automatic retry and fallback
- **OpenAI API**: Rate limiting and error recovery  
- **Cypher Syntax**: Automatic detection and correction
- **Schema Mismatches**: Dynamic adaptation to available properties

## Monitoring

Each search session generates detailed logs:
- Strategy selection reasoning
- Query generation rationale
- Result evaluation logic
- Confidence scoring breakdown
- Performance metrics

---

For questions or issues, check the generated reports in the output directory or examine the detailed JSON results for debugging information. 