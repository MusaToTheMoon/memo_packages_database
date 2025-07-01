from time import time
import json
from dotenv import load_dotenv
import os
import google.generativeai as genai
import sys
from pathlib import Path

load_dotenv()
project_root = os.environ.get("PROJECT_ROOT", ".")

system_prompt = """
You are analyzing Java source code to extract memoization-relevant metadata for each method.

You must output a JSON array, where each element corresponds to one method in the input Java class. Each method object must contain the following fields:

- methodSignature (string): Method name and parameter list, e.g., "int compute(int x, String s)"
- className (string): Fully qualified class name (e.g., "android.app.Service")
- reasonAboutStateAccesses (string): Discuss what state the method accesses (read/write, primitive/object, internal/global)
- stateAccesses (array of objects): List of state access records, or [] if there are none. Each record includes:
    - name (string): Fully-qualified field name accessed (e.g., this.cache, Config.VALUE)
    - scope ("INTERNAL" or "GLOBAL"): Whether the field is part of the class or external
    - type ("PRIMITIVE" or "OBJECT"): Data type classification
    - mode ("READ" or "WRITE"): Whether the field was read or written
    - idempotent (boolean or null): Set to null if mode is READ; true/false if WRITE

- reasonAboutSideEffects (string): Explain why this method has or lacks observable side effects (e.g., I/O, UI updates, logging, shared state mutation)
- hasSideEffects (boolean): True if the method performs any observable side effect
- reasonAboutNonDeterministicCalls (string): Discuss whether the method depends on non-deterministic behavior (e.g., time, randomness, system state)
- hasNonDeterministicCalls (boolean): True if the method calls time-based or random functions
- reasonAboutDependsOnArgumentsOnly (string): Explain whether the output depends purely on input parameters
- dependsOnArgumentsOnly (boolean): True if the method's return value is only determined by its arguments and constants

IMPORTANT: All fields are required.
IMPORTANT: If the method does not access any state, return stateAccesses as an empty array [].
IMPORTANT: Ignore static blocks. Ignore constructors.
VERY IMPORTANT: Output must be valid JSON. Ignore abstract methods and unimplemented interface methods. Only include methods that have a concrete implementation.
"""

def build_user_prompt(source_code, file_name):
    """
    Builds the user prompt by inserting the source code and the file name into the template.
    """
    return f"""
Here is the source code for the file you have to analyse according to the schema shared.
Extract metadata for each method in the file based on the schema. Follow all schema constraints strictly. 

### FILE NAME: 
{file_name}

### FILE SOURCE CODE:
{source_code}
"""

def trim_llm_json_output(raw_text):
    for prefix in ("'''json", "```json"):
        if raw_text.startswith(prefix):
            # Remove opening block
            raw_text = raw_text[len(prefix):].strip()

    # Remove trailing code block if it exists
    for suffix in ("'''", "```"):
        if raw_text.endswith(suffix):
            raw_text = raw_text[:-3].strip()

    return raw_text

def add_derivated_fields(llm_output):
    pass

def create_output_file_path(file_name, base_dir='.', ext="java"):
    """
    Converts a dotted Java-style package name into a file path,
    creates the directory structure if needed,
    and returns the full path to the final file (not created).
    
    Example:
        android.app.Service → ./android/app/Service.java
    """
    *dirs, class_name = file_name.split('.')
    dir_path = os.path.join(base_dir, *dirs)
    
    # create dirs if they don't already exist
    os.makedirs(dir_path, exist_ok=True)

    file_path = os.path.join(dir_path, f"{class_name}.{ext}")
    return file_path

def write_llm_output_to_file(llm_output, is_success, model_name, file_name, source_type, url, source_code_file_path):
    """
    Creates appropriate heirarchical directories based on the file name,
    and writes the LLM output to a file.
    """
    write_file_path = create_output_file_path(file_name, base_dir=os.path.join(project_root, "llm_analysis_files"), ext="json")

    # preprend metadata to llm_output
    final_write_object = {
        "file_name" : file_name,
        "source_type" : source_type,
        "url" : url,
        "source_code_file_path" : source_code_file_path,
        "is_success" : is_success,
        "llm_model_name" : model_name,
        "llm_analysis" : llm_output # this is either a JSON object or raw text, conditional on is_success
    }

    try:
        with open(write_file_path, 'w') as f:
            json.dump(final_write_object, f, indent=2)

        print(f"Successfully wrote llm analysis from {file_name} to {write_file_path}.")
    except (OSError, IOError) as e:
        print(f"Error while writing source code to file: {e}")
        print(f"File Details: {file_name}, {source_type}, {url}, {source_code_file_path}")
        print("Moving onto next URL.")

def fetch_code_from_path(file_path):
    """
    Fetches Java source code from a file path that is either relative to the project root or absolute.
    """
    file_path = Path(file_path)
    if not file_path.is_absolute():
        file_path = Path(project_root) / file_path
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r") as f:
        return f.read()

# def post_process_llm_output(llm_output):

def label_code_with_gemini(model, source_code, file_name):
    """
    Labels the source code using the LLM. Is called once per file/source code.
    Returns:
        - final_response: The LLM's response, formatted as JSON if successful else raw text.
        - success: True if the response was valid JSON, False otherwise.
    """
    user_prompt = build_user_prompt(source_code, file_name)

    try:
        response = model.generate_content(user_prompt)
        if not response:
            print("ERROR: LLM response is empty.")
            return "ERROR: LLM response is empty.", False

        trimmed_response = trim_llm_json_output(response.text)
        # Attempt to parse the JSON to validate it
        parsed_json = json.loads(trimmed_response)
        print("\nSUCCESS: LLM output was valid JSON.")
        # Pretty-print the validated JSON
        # final_response = json.dumps(parsed_json, indent=2)
        # print(final_response) # print debugging
        # return final_response, True
        return parsed_json, True

    except (json.JSONDecodeError, ValueError) as e:
        print(f"ERROR processing LLM response: {e}")
        # print("\n--- Raw LLM Output ---")
        # print(response.text)
        raw_output = response.text
        return raw_output, False

def setup_model_gemini(model_name="gemini-2.5-flash"):
    try:
        # Configure the client with your API key
        genai.configure(api_key = os.environ["GEMINI_API_KEY"])
    except KeyError:
        print("Error: The GEMINI_API_KEY environment variable is not set.")
        print("Please set your API key as an environment variable.")
        sys.exit(1)
    
    try:
        model = genai.GenerativeModel(model_name=model_name, system_instruction=system_prompt)
    except Exception as e:
        print(f"Error setting up Gemini model: {e}")
        print("Invalid model_name provided Try 'gemini-2.5-flash'.")
        sys.exit(1)

    return model

def main():
    if len(sys.argv) < 2:
        print("Example Usage: python label_llm.py <java_source_code_paths.csv> [model_name]")
        print("Please provide a path to a csv file containing paths to Java source code files, and optionally, the LLM model name (e.g., 'gemini-2.5-flash').")
        print("Format for CSV file: file_name,source_type,url,file_path")
        print("File paths should either be relative to the project root directory or absolute paths.")
        print("Also ensure project root is set in the .env file. Otherwise, it is set to the current directory by default.")
        print("Currently supported options for model_name: gemini-2.5-flash only.")
        sys.exit(1)

    path_to_csv_file = Path(sys.argv[1])
    print(f"Processing CSV file: {path_to_csv_file}")
    if not path_to_csv_file.exists():
        print(f"Error: The specified CSV file does not exist: {path_to_csv_file}")
        sys.exit(1)

    model_name = sys.argv[2] if len(sys.argv) > 2 else "gemini-2.5-flash"
    print(f"Using LLM model: {model_name}")
    if model_name.startswith("gemini"):
        model = setup_model_gemini(model_name)
    else:
        print(f"Unsupported LLM model: {model_name}. Currently only 'gemini-2.5-flash' is supported.")
        sys.exit(1)

    with open(path_to_csv_file, "r") as f:
        for line in f:
            # line := file_name,source_type,url,file_path_relative_to_project_root
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            if len(parts) != 4:
                print(f"Skipping malformed line: {line}")
                print("="*50)
                continue

            # fetch code from the file path
            try:
                source_code = fetch_code_from_path(parts[3])
            except Exception as e:
                print(e)
                print(f"Skipping this line: {line}")
                print("="*50)
                continue

            if len(source_code) > 0: # in casse the source code is empty
                print("Fetched Java source code successfully.")
                
                # feed the source code to LLM
                if model_name.startswith("gemini"):
                    llm_output, is_success = label_code_with_gemini(model, source_code, parts[0])
                    write_llm_output_to_file(llm_output, is_success, model_name, parts[0], parts[1], parts[2], parts[3])
                #=== currently only gemini is supported ===
                # elif model_name.startswith("gpt"):
                #     print("GPT model support is not implemented yet.")
                #     sys.exit(1)

            else:
                print(f"Fetching code failed.\nSkipping line: {line}.")
            print("="*50)
            
        print("Code has been fetched from all URLs in the CSV file.")

if __name__ == "__main__":
    main()