import json
from memory_graph_builder import MemoryGraphBuilder

def extract_graph_elements(builder: MemoryGraphBuilder):
    """
    Extract structured memory data from book content using LLM.
    
    :param builder: MemoryGraphBuilder instance
    """
    prompt = f"""
You are an intelligent memory extraction agent. Read the following text and extract structured memory data.

## Text:
\"\"\" 
{builder.book_content}
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
    response = builder.client.chat.completions.create(
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
        builder.graph_data = json.loads(content)
        print("[INFO] Successfully extracted graph elements")
    except json.JSONDecodeError as e:
        print("[ERROR] Failed to parse JSON output.")
        print("[DEBUG] Raw content:\n", content[:500])
        raise e

if __name__ == "__main__":
    # Example usage
    sample_content = "This is a sample book content for testing."
    builder = MemoryGraphBuilder(sample_content)
    extract_graph_elements(builder) 