"""
Environment Variable Loader

This module handles loading environment variables from .env files
for the agentic search engine.
"""

import os


def load_env_file() -> None:
    """
    Load environment variables from .env file if it exists.
    
    Tries multiple possible locations for the .env file:
    1. Project root (AgenticSearch/.env)
    2. src directory
    3. question_answering directory
    4. Current working directory
    """
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'),
        os.path.join(os.path.dirname(__file__), '.env'),
        '.env'
    ]
    
    for env_file in possible_paths:
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
            print(f"Loaded environment variables from {env_file}")
            return
    
    print("Warning: .env file not found in any expected location")


# Load environment variables when module is imported
load_env_file()

