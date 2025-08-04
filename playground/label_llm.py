"""
This script labels Java source code using a large language model (LLM) to extract information relevant for memoization.
It reads Java source code from a CSV file containing file names, source types, URLs, and file paths.
It uses the Gemini LLM to analyze each method in the Java source code and outputs information in a structured JSON format.
"""

from time import time, sleep
import json
from json import JSONDecodeError
from dotenv import load_dotenv
import os
import google.generativeai as genai
import sys
from pathlib import Path
import argparse

from google.api_core import exceptions

from google.rpc import error_details_pb2
from google.protobuf.json_format import MessageToDict

load_dotenv()
project_root = os.environ.get("PROJECT_ROOT", ".")
dir_for_current_phase = Path(project_root) / os.environ.get("DIR_FOR_CURRENT_PHASE", "phase" + str(int(time()))) # directory containing CSV files for this phase of the project

MAX_RETRIES = 2  # Maximum number of retries for LLM requests

system_prompt = """
You are analyzing Java source code to extract memoization-relevant metadata for each method.

You must output a JSON array, where each element corresponds to one method in the input Java class. Each method object must contain the following fields:

- methodSignature (string): Method name and parameter list, e.g., "int compute(int x, String s)"
- className (string): Fully qualified class name (e.g., "android.app.Service")
- reasonAboutStateAccesses (string): Discuss what state the method accesses (read/write, primitive/object, internal/global)
- stateAccesses (array of objects): List of state access records, or [] if there are none. Each record includes:
    - name (string): Fully-qualified field name accessed (e.g., this.cache, Config.VALUE)
    - scope ("INTERNAL" or "GLOBAL"): Whether the field is part of the class or external
    - valueType ("PRIMITIVE" or "OBJECT"): Data type classification
    - accessType ("READ" or "WRITE"): Whether the field was read or written
    - idempotent (boolean or null): True if repeat writes do not change state after the first; null if accessType is READ

- reasonAboutSideEffects (string): Explain why this method has or lacks observable side effects (e.g., I/O, UI updates, logging, shared state mutation)
- hasSideEffects (boolean): True if the method performs any observable side effect
- reasonAboutNonDeterministicCalls (string): Discuss whether the method depends on non-deterministic behavior (e.g., time, randomness, system state)
- hasNonDeterministicCalls (boolean): True if the method calls time-based or random functions
- reasonAboutDependsOnArgumentsOnly (string): Explain whether the output depends purely on input parameters
- dependsOnArgumentsOnly (boolean): True if the method's return value is only determined by its arguments and constants
- purityInfo (object): Object containing purity-related fields. Each object must contain:
    - reasonAboutIsPureLLM (string): Reason whether the method is pure and suitable for memoization
    - isPureLLM (boolean): True if the method is pure and suitable for memoization

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

def add_derived_fields(llm_output, is_success):
    print("Adding derived fields to LLM output...")
    if not is_success:
        # if the llm output process was not successful, we don't need to add derived fields
        return llm_output
    
    # Add derived fields based on the existing fields
    # by this point, llm_output should be a list of dictionaries
    for item in llm_output:
        if "purityInfo" not in item:
            item["purityInfo"] = {}

        try:
            item["purityInfo"]["isPureStrict"] = (
                not item["hasSideEffects"] 
                and not item["hasNonDeterministicCalls"] 
                and item["dependsOnArgumentsOnly"] 
                and len(item["stateAccesses"]) == 0
            )
            # note, len(stateAccesses) == 0 is somewhat redundant because dependsOnArgumentsOnly == True implies no read accesses and hasSideEffects == False implies no write accesses. However, we keep it for robustness since analysis from LLMs is error-prone.
        except KeyError as e:
            print(f"KeyError: {e} in item {item}. Skipping this item.")
            item["purityInfo"]["isPureStrict"] = None

        # Add isPureWithReads attribute
        try:        
            item["purityInfo"]["isPureWithReads"] = (
                not item["hasSideEffects"] 
                and not item["hasNonDeterministicCalls"] 
                and all(access["accessType"] == "READ" for access in item["stateAccesses"]) # True if all accesses are reads OR if stateAccesses is empty
            )
        except KeyError as e:
            print(f"KeyError: {e} in item {item}. Skipping this item.")
            item["purityInfo"]["isPureWithReads"] = None
        
    print("Derived fields added successfully.")
    return llm_output

def create_output_file_path(run_name, file_name, base_dir='.',  ext="java"):
    """
    Converts a dotted Java-style package name into a file path,
    creates the directory structure if needed,
    and returns the full path to the final file (not created).
    
    Example:
        android.app.Service → ./android/app/Service.java
    """
    *dirs, class_name = file_name.split('.')
    dir_path = Path(base_dir) / run_name / Path(*dirs)
    
    # create dirs if they don't already exist
    dir_path.mkdir(parents=True, exist_ok=True)

    file_path = dir_path / f"{class_name}.{ext}"
    return file_path

def write_llm_output_to_file(llm_output, is_success, model_name, run_name, time_taken_by_llm, file_name, source_type, url, source_code_file_path):
    """
    Creates appropriate heirarchical directories based on the file name,
    and writes the LLM output to a file.
    """
    write_file_path = create_output_file_path(run_name, file_name, base_dir=Path(dir_for_current_phase) / "java_llm_analysis_files", ext="json")

    # preprend metadata to llm_output
    final_write_object = {
        "file_name" : file_name,
        "source_type" : source_type,
        "url" : url,
        "source_code_file_path" : source_code_file_path,
        "is_success" : is_success,
        "llm_model_name" : model_name,
        "llm_analysis_timestamp" : int(time()), # current timestamp in seconds, since models tend to change over time
        "run_name" : run_name,
        "llm_response_time_seconds" : time_taken_by_llm, # in seconds
        "llm_analysis" : llm_output # this is either a dictionary obj or a string, conditional on is_success
    }

    print("Writing LLM analysis to file...")
    try:
        with open(write_file_path, 'w') as f:
            json.dump(final_write_object, f, indent=2)

        print(f"Successfully wrote llm analysis from {file_name} to {write_file_path}.")
    except (OSError, IOError) as e:
        print(f"Error while writing llm analysis to file: {e}")
        print(f"File Details: {file_name}, {source_type}, {url}, {source_code_file_path}")
        print("Moving onto next line.")

def fetch_code_from_path(file_path):
    """
    Fetches Java source code from a file path that is either relative to the dir_for_current_phase or absolute.
    """
    file_path = Path(file_path)
    if not file_path.is_absolute():
        file_path = Path(dir_for_current_phase) / file_path
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r") as f:
        return f.read()

def label_code_with_gemini(model, source_code, file_name, retry_count=0):
    """
    Labels the source code using the LLM. Is called once per file/source code.
    Returns:
        - final_response: The LLM's response, formatted as JSON if successful else raw text.
        - is_success: True if the response was valid JSON, False otherwise.
    """
    user_prompt = build_user_prompt(source_code, file_name)

    try:
        response = model.generate_content(
            user_prompt,
            request_options={'timeout': 900}
        )
        if not response:
            print("ERROR: LLM response is empty.")
            return "ERROR: LLM response is empty.", False

        trimmed_response = trim_llm_json_output(response.text)
        # Attempt to parse the JSON to validate it
        parsed_json = json.loads(trimmed_response)
        print("SUCCESS: LLM output was valid JSON.")
        # Pretty-print the validated JSON
        # final_response = json.dumps(parsed_json, indent=2)
        # print(final_response) # print debugging
        # return final_response, True
        return parsed_json, True

    except (JSONDecodeError, ValueError) as e:
        print(f"ERROR processing LLM response: {e}")
        raw_output = response.text
        return raw_output, False
    
    except exceptions.ResourceExhausted as e: 
        # GenerateContentInputTokensPerModelPerMinute-FreeTier
        # GenerateRequestsPerDayPerProjectPerModel-FreeTier
        print(f"Rate limit exceeded.")    

        for detail in e._details:
            print("Type of detail:", type(detail))

            # Case 1: Already a parsed QuotaFailure object
            if isinstance(detail, error_details_pb2.QuotaFailure):
                for violation in detail.violations:
                    # print("quota_metric:", violation.quota_metric)
                    print("quota_id:", violation.quota_id)

                    if violation.quota_id == "GenerateRequestsPerDayPerProjectPerModel-FreeTier": # Check if it's a daily quota limit
                        # TODO handle this case by using backup API defined in the .env file or some other solution, idk yet
                        print("Daily quota exceeded. Skipping this request.")
                        return f"ERROR: Daily quota exceeded", False
                    
                    elif violation.quota_id == "GenerateContentInputTokensPerModelPerMinute-FreeTier":        
                        if retry_count >= MAX_RETRIES:
                            print("Max retries reached. Skipping this request.")
                            return f"ERROR: Rate limit exceeded - max retries reached", False
                        
                        retry_delay = 60 # hardcoded for now, can be improved later
                        # the following is incorrect way to access the retry_delay value, look up proto_buf. e.retry_delay.seconds
                        print(f"Retrying after {retry_delay} seconds...")
                        sleep(retry_delay)
                        return label_code_with_gemini(model, source_code, file_name, retry_count+1)  # Retry the request

    except exceptions.DeadlineExceeded as e:
        print(f"Request timed out.")

        if retry_count >= MAX_RETRIES:
            print("Max retries reached. Skipping this request.")
            return f"ERROR: Request timeout - LLM took too long to repond", False
        
        print("Retrying...")
        sleep(10) 
        return label_code_with_gemini(model, source_code, file_name, retry_count+1)

    except Exception as e:
        print(f"An unexpected error occurred while processing LLM response: {e}")
        print("Returning raw output for debugging.")
        return response.text, False

def setup_model_gemini(model_name="gemini-2.5-flash"):
    try:
        # Configure the client with your API key
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    except KeyError:
        print("Error: The GEMINI_API_KEY environment variable is not set.")
        print("Please set your API key as an environment variable.")
        sys.exit(1)
    
    try:
        model = genai.GenerativeModel(model_name=model_name, system_instruction=system_prompt)
    except Exception as e:
        print(f"Error setting up Gemini model: {e}")
        print("Possible Reason: Invalid model_name provided Try 'gemini-2.5-flash'.")
        sys.exit(1)

    return model

def main():
    parser = argparse.ArgumentParser(
        description="Label source code using LLM for memoization analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python label_llm.py                                          # Use all defaults
  python label_llm.py --csv-file custom_file.csv               # Use custom CSV file
  python label_llm.py --model-name gemini-2.5-flash            # Default CSV, custom model
  python label_llm.py --csv-file custom.csv --run-name my_experiment # Custom CSV and run name
  python label_llm.py --csv-file custom.csv --model-name gemini-2.5-flash --run-name my_experiment

CSV file format: file_name,source_type,url,file_path
File paths should be relative to DIR_FOR_CURRENT_PHASE or absolute paths.
Also ensure PROJECT_ROOT and DIR_FOR_CURRENT_PHASE are set in the .env file.
Currently supported options for model_name: gemini-2.5-flash only.
""")
    
    parser.add_argument("--csv-file", default=dir_for_current_phase / "csv_files" / "java_filepaths.csv", 
                       help=f"Path to CSV file containing Java source code paths (default: {dir_for_current_phase / 'csv_files' / 'java_filepaths.csv'})")
    parser.add_argument("--model-name", default="gemini-2.5-flash", 
                       help="LLM model name (default: gemini-2.5-flash)")
    parser.add_argument("--run-name", default=f"run_{int(time())}", 
                       help="Run name for this analysis (default: run_<timestamp>)")
    
    args = parser.parse_args()

    path_to_csv_file = Path(args.csv_file)
    print(f"Processing CSV file: {path_to_csv_file}")
    if not path_to_csv_file.exists():
        print(f"Error: The specified CSV file does not exist: {path_to_csv_file}")
        sys.exit(1)

    model_name = args.model_name
    print(f"Using LLM model: {model_name}")

    run_name = args.run_name
    print(f"Run name: {run_name}")

    if model_name.startswith("gemini"):
        model = setup_model_gemini(model_name)
    else:
        print(f"Unsupported LLM model: {model_name}. Currently only 'gemini-2.5-flash' is supported.")
        sys.exit(1)

    # Track failed lines for output
    failed_lines = []
    
    with open(path_to_csv_file, "r") as f:
        print(f"Beginning processing of CSV file: {path_to_csv_file}")
        print("="*50)
        for line in f:
            # line := file_name,source_type,url,file_path_relative_to_DIR_FOR_CURRENT_PHASE
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            if len(parts) != 4:
                print(f"Skipping malformed line: {line}")
                failed_lines.append(line)
                print("="*50)
                continue

            print(f"Processing line: {line}")
            # fetch code from the file path
            print("Fetching source code from file path...")
            try:
                source_code = fetch_code_from_path(parts[3])
            except Exception as e:
                print(e)
                print(f"Fetching source code failed. Skipping this line: {line}")
                failed_lines.append(line)
                print("="*50)
                continue

            if len(source_code) > 0: # in casse the source code is empty
                print("Fetched Java source code successfully.")
                
                start_time = time()
                print("Feeding source code to LLM for analysis...")
                # feed the source code to LLM
                if model_name.startswith("gemini"):
                    curr_model = model
                    curr_model_name = model_name

                    # Get input token count of the user_prompt for logging purposes
                    input_token_count = model.count_tokens(source_code).total_tokens
                    print(f"Input token count for user_prompt: {input_token_count}")

                    # if input_token_count > 249000:
                    #     # switch to another model with larger context window
                    #     curr_model_name = "gemini-2.5-flash"
                    #     print(f"Input token count exceeds 248500. Switching to {curr_model_name} model.")
                    #     curr_model = setup_model_gemini(curr_model_name)
                        
                    llm_output, is_success = label_code_with_gemini(curr_model, source_code, parts[0])
                    
                    time_taken_by_llm = round(time() - start_time, 3)  # Round to 3 decimal places (millisecond precision)
                    llm_output = add_derived_fields(llm_output, is_success)

                    write_llm_output_to_file(llm_output, is_success, curr_model_name, run_name, time_taken_by_llm, parts[0], parts[1], parts[2], parts[3])

                #=== currently only gemini is supported ===
                # elif model_name.startswith("gpt"):
                #     print("GPT model support is not implemented yet.")
                #     sys.exit(1)

                if not is_success:
                    failed_lines.append(line)
            else:
                print(f"Fetching code failed. Skipping line: {line}.")
                failed_lines.append(line)
            print("="*50)
            
        print("All filepaths/lines in the CSV file have been processed (with or without success) by the LLM.")
        
        # Write failed lines to CSV file
        if failed_lines:
            failed_csv_path = Path(dir_for_current_phase) / f"java_filepaths_failed_{run_name}.csv"
            print(f"\nWriting {len(failed_lines)} failed lines to: {failed_csv_path}")
            try:
                with open(failed_csv_path, 'w') as f:
                    for failed_line in failed_lines:
                        f.write(f"{failed_line}\n")
                print(f"Successfully wrote failed lines to {failed_csv_path}")
            except (OSError, IOError) as e:
                print(f"Error writing failed lines to file: {e}")
        else:
            print("\nNo failed lines to write - all processing was successful!")

if __name__ == "__main__":
    main()

# Task List:
# - [ ] if LLM provider rejects because of token limit, fall back to another version 2.0 flash 
# - [ ] Split large files into smaller chunks and process them separately. Use Rui's solution for this.
