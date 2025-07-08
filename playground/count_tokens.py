#!/usr/bin/env python3
"""
Script to count tokens in the View.java file using Gemini 2.5 Pro API.
"""

import os
import google.generativeai as genai
from dotenv import load_dotenv
import sys
from pathlib import Path
import contextlib
import io

# Load environment variables
load_dotenv()

def get_all_java_files(base_dir):
    """
    Generator that yields all Java file paths from the java_source_code_files directory.
    
    Args:
        base_dir (str): Base directory containing java_source_code_files
        
    Yields:
        Path: Absolute path to each .java file
    """
    java_source_dir = Path(base_dir)
    
    if not java_source_dir.exists():
        print(f"Error: Directory not found: {java_source_dir}")
        return
    
    # Recursively find all .java files
    for java_file in java_source_dir.rglob("*.java"):
        yield java_file

def setup_gemini_model(model_name="gemini-2.5-pro"):
    """Set up the Gemini model."""
    try:
        # Configure the client with your API key
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        print("Gemini API configured successfully")
    except KeyError:
        print("Error: The GEMINI_API_KEY environment variable is not set.")
        print("Please set your API key as an environment variable.")
        sys.exit(1)
    
    try:
        model = genai.GenerativeModel(model_name=model_name)
        print(f"{model_name} model initialized")
        return model
    except Exception as e:
        print(f"Error setting up Gemini model: {e}")
        sys.exit(1)

def read_java_file(file_path):
    """Read the entire java file."""
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"Successfully read java file from {file_path}")
        print(f"    File size: {len(content):,} characters")
        return content
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

def count_tokens(model, content):
    """Count tokens in the content using the Gemini model."""
    try:
        print("Counting tokens...")
        token_count = model.count_tokens(content)
        return token_count.total_tokens
    except Exception as e:
        print(f"Error counting tokens: {e}")
        return None

def main():
    base_dir = "/Users/musanto/Documents/Karim_Research/Memoization/memo_packages_database/phase1/java_source_code_files"
    model_naeme = "gemini-2.0-flash"
    token_limit = 248500  # Set the token limit for comparison

    print("Token Counter")
    print("=" * 40)

    # Set up the model
    model = setup_gemini_model(model_name=model_naeme)
    
    total_token_count = 0
    file_count = 0
    
    # Iterate over all Java files and count tokens
    for file_path in get_all_java_files(base_dir):
        # Read the file and count tokens silently

        with contextlib.redirect_stdout(io.StringIO()):
            content = read_java_file(file_path)
            token_count = count_tokens(model, content)

        if token_count is not None and token_count > token_limit:
            print(f"{file_path.name} has a token count above {token_limit}: {token_count:,}")
        
    #     if token_count is not None:
    #         total_token_count += token_count
    #         file_count += 1
    #     else:
    #         print(f"Failed to count tokens for {file_path}")
    
    # After processing all files, print the cumulative results
    # if file_count > 0:
    #     print(f"\nCumulative Results for {file_count} files:")
    #     print(f"   Total tokens: {total_token_count:,}")
    #     print(f"   Token limit:  250,000")
    #     print(f"   Status: {'UNDER limit' if total_token_count <= 250000 else 'OVER limit'}")
        
    #     if total_token_count > 250000:
    #         print(f"   Excess: {total_token_count - 250000:,} tokens over the limit")
    #         print(f"   Percentage: {(total_token_count / 250000) * 100:.1f}% of the limit")
    # else:
    #     print("No valid Java files found or failed to count tokens for all files.")

if __name__ == "__main__":
    main()
