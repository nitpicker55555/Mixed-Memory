#!/usr/bin/env python3
"""
Data processing script for Memory Graph project.
This script processes events, books, and graph answers data.
"""

import json
import os
import pandas as pd
from typing import Dict, List, Any
from memory_graph_builder import MemoryGraphBuilder
from extract_graph_elements import extract_graph_elements
from build_graphs import build_all_graphs
from visualize_graphs import visualize_all_graphs, create_graph_summary

class DataProcessor:
    def __init__(self, data_dir: str = "data"):
        """
        Initialize the data processor.
        
        :param data_dir: Directory containing the data files
        """
        self.data_dir = data_dir
        self.events = None
        self.meta_events = None
        self.book_data = None
        self.graph_answers = {}
        
    def load_events(self):
        """Load events data."""
        events_path = os.path.join(self.data_dir, "events.json")
        with open(events_path, 'r', encoding='utf-8') as f:
            self.events = json.load(f)
        print(f"[INFO] Loaded {len(self.events)} events")
        
    def load_meta_events(self):
        """Load meta events data."""
        meta_events_path = os.path.join(self.data_dir, "meta_events.json")
        with open(meta_events_path, 'r', encoding='utf-8') as f:
            self.meta_events = json.load(f)
        print(f"[INFO] Loaded {len(self.meta_events)} meta events")
        
    def load_book_data(self):
        """Load book data."""
        book_path = os.path.join(self.data_dir, "books", "model_claude-3-5-sonnet-20240620_itermax_10_Idefault_nbchapters_19_nbtokens_10397", "book.json")
        with open(book_path, 'r', encoding='utf-8') as f:
            self.book_data = json.load(f)
        print(f"[INFO] Loaded book data")
        
    def load_graph_answers(self):
        """Load graph answers data."""
        graph_answers_dir = os.path.join(self.data_dir, "graph_answers")
        for filename in os.listdir(graph_answers_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(graph_answers_dir, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    # Remove quotes if present
                    if content.startswith('"') and content.endswith('"'):
                        content = content[1:-1]
                    self.graph_answers[filename] = content
        print(f"[INFO] Loaded {len(self.graph_answers)} graph answers")
        
    def create_story_text(self) -> str:
        """Create a story text from events and meta events."""
        if not self.events or not self.meta_events:
            print("[ERROR] Events or meta events not loaded")
            return ""
            
        story_parts = []
        
        # Add events
        for event in self.events:
            try:
                if len(event) >= 5:
                    date, location, person, activity, description = event[:5]
                    story_part = f"On {date}, at {location}, {person} participated in {activity}. {description}."
                    story_parts.append(story_part)
                else:
                    print(f"[WARNING] Skipping event with insufficient data: {event}")
            except Exception as e:
                print(f"[WARNING] Error processing event {event}: {e}")
                continue
            
        # Add meta events
        for meta_event in self.meta_events:
            try:
                if len(meta_event) >= 5:
                    date, location, person, activity, description = meta_event[:5]
                    story_part = f"On {date}, at {location}, {person} participated in {activity}. {description}."
                    story_parts.append(story_part)
                else:
                    print(f"[WARNING] Skipping meta event with insufficient data: {meta_event}")
            except Exception as e:
                print(f"[WARNING] Error processing meta event {meta_event}: {e}")
                continue
            
        return " ".join(story_parts)
        
    def analyze_graph_answers(self):
        """Analyze the graph answers data."""
        print("\n=== Graph Answers Analysis ===")
        
        # Count answer lengths
        lengths = [len(answer) for answer in self.graph_answers.values()]
        print(f"Total answers: {len(self.graph_answers)}")
        print(f"Average answer length: {sum(lengths) / len(lengths):.1f} characters")
        print(f"Shortest answer: {min(lengths)} characters")
        print(f"Longest answer: {max(lengths)} characters")
        
        # Show some examples
        print("\n=== Sample Answers ===")
        for i, (filename, answer) in enumerate(list(self.graph_answers.items())[:5]):
            print(f"\n{filename}:")
            print(f"  {answer[:100]}{'...' if len(answer) > 100 else ''}")
            
    def generate_memory_graphs(self, story_text: str):
        """Generate memory graphs from story text."""
        print("\n=== Generating Memory Graphs ===")
        
        # Initialize builder
        builder = MemoryGraphBuilder(
            book_content=story_text,
            graph_json_path="generated_memory_graph.json",
            graph_image_dir="generated_graphs"
        )
        
        # Run the pipeline
        try:
            extract_graph_elements(builder)
            builder.save_graph_json()
            build_all_graphs(builder)
            visualize_all_graphs(builder)
            create_graph_summary(builder)
            
            return builder
        except Exception as e:
            print(f"[ERROR] Failed to generate memory graphs: {e}")
            return None
            
    def run_full_pipeline(self):
        """Run the complete data processing pipeline."""
        print("=" * 60)
        print("MEMORY GRAPH DATA PROCESSING PIPELINE")
        print("=" * 60)
        
        # Load all data
        print("\n[STEP 1] Loading data...")
        self.load_events()
        self.load_meta_events()
        self.load_book_data()
        self.load_graph_answers()
        
        # Analyze data
        print("\n[STEP 2] Analyzing data...")
        self.analyze_graph_answers()
        
        # Create story text
        print("\n[STEP 3] Creating story text...")
        story_text = self.create_story_text()
        print(f"Story text length: {len(story_text)} characters")
        
        # Generate memory graphs
        print("\n[STEP 4] Generating memory graphs...")
        builder = self.generate_memory_graphs(story_text)
        
        if builder:
            print("\n" + "=" * 60)
            print("PIPELINE COMPLETED SUCCESSFULLY!")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("PIPELINE FAILED!")
            print("=" * 60)
            
        return builder

def main():
    """Main function."""
    processor = DataProcessor()
    builder = processor.run_full_pipeline()
    
    if builder:
        print("\n[SUCCESS] Memory graph generation completed!")
        print("  - Generated JSON: generated_memory_graph.json")
        print("  - Generated graphs: generated_graphs/")
    else:
        print("\n[ERROR] Memory graph generation failed!")

if __name__ == "__main__":
    main() 