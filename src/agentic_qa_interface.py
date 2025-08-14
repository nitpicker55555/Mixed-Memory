"""
Agentic QA Interface

This module provides a compatibility wrapper for the agentic search engine 
that can be used as a drop-in replacement for the existing QA system.
"""

import json
import os
from typing import Dict, List, Any, Optional
from agentic_search_engine import AgenticSearchEngine


class AgenticQAInterface:
    """
    Interface class that wraps the agentic search engine to provide
    compatibility with the existing QA system API
    """
    
    def __init__(self, neo4j_uri: str = "bolt://localhost:7687", 
                 neo4j_user: str = "neo4j", neo4j_password: str = "password",
                 openai_api_key: str = None):
        """
        Initialize the agentic QA interface
        
        Args:
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username  
            neo4j_password: Neo4j password
            openai_api_key: OpenAI API key (optional, uses env var if not provided)
        """
        self.engine = AgenticSearchEngine(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user, 
            neo4j_password=neo4j_password,
            openai_api_key=openai_api_key
        )
    
    def analyze_question(self, question: str, node_name: str = None, 
                        similarity: float = None) -> Dict[str, Any]:
        """
        Analyze a single question using agentic search
        
        Args:
            question: The question to analyze
            node_name: Optional node name (for compatibility, not used in agentic approach)
            similarity: Optional similarity score (for compatibility, not used)
            
        Returns:
            Dict containing the analysis result in compatible format
        """
        
        # Use agentic search to find the answer
        search_result = self.engine.search(question)
        
        # Convert to compatible format
        result = {
            "question": question,
            "predicted_answer": search_result.get("final_answer"),
            "gpt_answer_result": {
                "final_answer": search_result.get("final_answer"),
                "confidence_score": search_result.get("confidence_score", 0.0),
                "reasoning": search_result.get("reasoning_chain", []),
                "search_successful": search_result.get("search_successful", False)
            },
            "agentic_metadata": {
                "session_id": search_result.get("session_id"),
                "total_iterations": search_result.get("total_iterations", 0),
                "query_history": search_result.get("query_history", []),
                "search_strategy_used": "agentic_react_loop"
            }
        }
        
        return result
    
    def analyze_questions_batch(self, questions: List[Dict], 
                               output_file: str = None) -> List[Dict[str, Any]]:
        """
        Analyze a batch of questions using agentic search
        
        Args:
            questions: List of question dictionaries with format:
                      [{"question": "...", "answer": "...", ...}, ...]
            output_file: Optional file to save results
            
        Returns:
            List of analysis results
        """
        
        results = []
        
        for i, q_data in enumerate(questions):
            question = q_data.get("question", "")
            expected_answer = q_data.get("answer", [])
            
            print(f"Processing question {i+1}/{len(questions)}: {question}")
            
            # Analyze using agentic search
            result = self.analyze_question(question)
            
            # Add expected answer for comparison
            result["expected_answer"] = expected_answer
            result["question_id"] = i
            
            # Calculate basic accuracy if possible
            predicted = result.get("predicted_answer")
            if predicted and expected_answer:
                result["basic_match"] = self._calculate_basic_match(
                    predicted, expected_answer
                )
            
            results.append(result)
            
            # Optional: Save intermediate results
            if output_file and (i + 1) % 10 == 0:
                self._save_intermediate_results(results, output_file, i + 1)
        
        # Save final results
        if output_file:
            self._save_results(results, output_file)
        
        return results
    
    def _calculate_basic_match(self, predicted: str, expected: List[str]) -> Dict[str, Any]:
        """
        Calculate basic matching between predicted and expected answers
        
        Args:
            predicted: Predicted answer string
            expected: List of expected answer strings
            
        Returns:
            Dict with matching information
        """
        if not predicted or not expected:
            return {"match": False, "confidence": 0.0, "reason": "Missing data"}
        
        predicted_lower = predicted.lower()
        
        # Check for exact matches
        for exp in expected:
            if exp.lower() in predicted_lower or predicted_lower in exp.lower():
                return {"match": True, "confidence": 1.0, "matched_with": exp}
        
        # Check for partial matches
        for exp in expected:
            exp_words = set(exp.lower().split())
            pred_words = set(predicted_lower.split())
            
            overlap = len(exp_words.intersection(pred_words))
            if overlap > 0:
                confidence = overlap / max(len(exp_words), len(pred_words))
                if confidence > 0.5:
                    return {"match": True, "confidence": confidence, "matched_with": exp}
        
        return {"match": False, "confidence": 0.0, "reason": "No significant overlap"}
    
    def _save_intermediate_results(self, results: List[Dict], base_filename: str, 
                                  count: int):
        """Save intermediate results during batch processing"""
        filename = f"{base_filename}_intermediate_{count}.json"
        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Saved intermediate results to {filename}")
        except Exception as e:
            print(f"Error saving intermediate results: {e}")
    
    def _save_results(self, results: List[Dict], filename: str):
        """Save final results to file"""
        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Saved final results to {filename}")
        except Exception as e:
            print(f"Error saving results: {e}")
    
    def generate_report(self, results: List[Dict], output_file: str = None) -> str:
        """
        Generate a human-readable report from analysis results
        
        Args:
            results: List of analysis results
            output_file: Optional file to save the report
            
        Returns:
            Report text
        """
        
        total_questions = len(results)
        successful_searches = sum(1 for r in results 
                                if r.get("gpt_answer_result", {}).get("search_successful", False))
        
        answered_questions = sum(1 for r in results 
                               if r.get("predicted_answer") is not None)
        
        matches = sum(1 for r in results 
                     if r.get("basic_match", {}).get("match", False))
        
        avg_iterations = sum(r.get("agentic_metadata", {}).get("total_iterations", 0) 
                           for r in results) / total_questions if total_questions > 0 else 0
        
        report = f"""
Agentic Search Analysis Report
==============================

Summary Statistics:
- Total Questions: {total_questions}
- Successful Searches: {successful_searches} ({successful_searches/total_questions*100:.1f}%)
- Questions with Answers: {answered_questions} ({answered_questions/total_questions*100:.1f}%)
- Basic Answer Matches: {matches} ({matches/total_questions*100:.1f}%)
- Average Iterations per Question: {avg_iterations:.1f}

Detailed Analysis:
"""
        
        for i, result in enumerate(results):
            question = result.get("question", "Unknown")
            predicted = result.get("predicted_answer", "No answer")
            expected = result.get("expected_answer", [])
            iterations = result.get("agentic_metadata", {}).get("total_iterations", 0)
            search_success = result.get("gpt_answer_result", {}).get("search_successful", False)
            
            match_info = result.get("basic_match", {})
            match_status = "✓" if match_info.get("match", False) else "✗"
            
            report += f"""
Question {i+1}: {question}
Expected: {expected}
Predicted: {predicted}
Search Success: {search_success}
Iterations Used: {iterations}
Match: {match_status}
---
"""
        
        if output_file:
            try:
                with open(output_file, 'w') as f:
                    f.write(report)
                print(f"Report saved to {output_file}")
            except Exception as e:
                print(f"Error saving report: {e}")
        
        return report
    
    def close(self):
        """Clean up resources"""
        if self.engine:
            self.engine.close()


class AgenticQuestionAnalyzer:
    """
    Drop-in replacement class that maintains exact API compatibility
    with the existing system while using agentic search internally
    """
    
    def __init__(self, neo4j_uri: str = "bolt://localhost:7687",
                 neo4j_user: str = "neo4j", neo4j_password: str = "password"):
        """Initialize with same parameters as original system"""
        self.qa_interface = AgenticQAInterface(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user, 
            neo4j_password=neo4j_password
        )
    
    def analyze_question(self, question: str, node_name: str, similarity: float) -> Dict:
        """
        Exact API match with original system
        
        Args:
            question: Question to analyze
            node_name: Best matching node name (ignored in agentic approach)
            similarity: Similarity score (ignored in agentic approach)
            
        Returns:
            Analysis result in original format
        """
        return self.qa_interface.analyze_question(question, node_name, similarity)
    
    def close(self):
        """Clean up resources"""
        self.qa_interface.close()


# Example usage and testing
def main():
    """Example usage of the agentic QA interface"""
    
    # Initialize the interface
    qa_interface = AgenticQAInterface()
    
    try:
        # Test single question
        question = "What events did Emma Chen participate in?"
        result = qa_interface.analyze_question(question)
        
        print("Single Question Result:")
        print(json.dumps(result, indent=2))
        
        # Test batch processing
        test_questions = [
            {"question": "What events did Emma Chen participate in?", "answer": ["Event A", "Event B"]},
            {"question": "Where was the Photography Exhibition held?", "answer": ["Museum"]},
        ]
        
        batch_results = qa_interface.analyze_questions_batch(
            test_questions, 
            "test_agentic_results.json"
        )
        
        # Generate report
        report = qa_interface.generate_report(batch_results, "test_agentic_report.txt")
        print("Report generated successfully")
        
    finally:
        qa_interface.close()


if __name__ == "__main__":
    main() 