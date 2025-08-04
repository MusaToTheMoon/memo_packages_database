#!/usr/bin/env python3
"""
Script to aggregate purity analysis results from multiple LLM passes.
This script combines results from different passes (e.g., gemini-2.5-pro-pass-1, pass-2, pass-3)
and creates aggregated JSON files with consensus purity analysis.
"""

import json
import os
import csv
from time import time
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
from typing import Dict, List, Any, Tuple

# Load environment variables from .env file, overriding any existing ones
load_dotenv(override=True)

# Get project root and current phase directory from environment variables
project_root = os.environ.get("PROJECT_ROOT", ".")
DIR_FOR_CURRENT_PHASE = Path(project_root) / os.environ.get("DIR_FOR_CURRENT_PHASE", "phase" + str(int(time())))

def create_output_file_path(file_name: str, base_dir: str, ext: str = "json") -> str:
    """
    Converts a dotted Java-style package name into a file path and creates the directory structure.
    Example: 'android.app.Service' -> '<base_dir>/android/app/Service.json'
    """
    *dirs, class_name = file_name.split('.')
    dir_path = Path(base_dir).joinpath(*dirs)
    dir_path.mkdir(parents=True, exist_ok=True)
    return str(dir_path / f"{class_name}.{ext}")

def collect_json_files(analysis_dirs: List[str]) -> Dict[str, List[Tuple[str, Path]]]:
    """
    Scans analysis directories and collects all JSON file paths, grouping them by file name.
    """
    file_map = defaultdict(list)
    for analysis_dir in analysis_dirs:
        analysis_path = DIR_FOR_CURRENT_PHASE / analysis_dir
        if not analysis_path.exists():
            print(f"Warning: Analysis directory not found: {analysis_path}")
            continue
        
        for root, _, files in os.walk(analysis_path):
            for file in files:
                if file.endswith('.json'):
                    file_path = Path(root) / file
                    # Reconstruct file_name from path, e.g., android/app/Service.json -> android.app.Service
                    relative_path = file_path.relative_to(analysis_path)
                    file_name = '.'.join(relative_path.with_suffix('').parts)
                    file_map[file_name].append((analysis_dir, file_path))
    return file_map

def process_files(file_map: Dict[str, List[Tuple[str, Path]]], aggregation_name: str, output_base_dir: Path):
    """
    Processes each file, aggregates the data, and writes the output JSON or adds to skipped list.
    """
    skipped_files = []
    successful_aggregations = 0
    total_purity_counts = {"pure": 0, "impure": 0, "mixed": 0}

    for file_name, pass_files in file_map.items():
        all_analyses = []
        has_failure = False
        
        # Load all JSON passes for a given file
        for _, file_path in pass_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                if not data.get('is_success'):
                    has_failure = True
                    # Use snake_case keys here as it's from the source file
                    skipped_files.append({
                        'fileName': data.get('file_name', file_name),
                        'sourceType': data.get('source_type', 'N/A'),
                        'url': data.get('url', 'N/A'),
                        'sourceCodeFilePath': data.get('source_code_file_path', 'N/A')
                    })
                    break
                all_analyses.append(data)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Error reading or parsing {file_path}: {e}")
                has_failure = True
                break
        
        if has_failure:
            print(f"Skipping {file_name} due to failure in one of its passes.")
            continue

        # Aggregate the data if all passes were successful
        aggregated_data, purity_counts = aggregate_data(file_name, all_analyses)
        
        # Update total purity counts
        for key in total_purity_counts:
            total_purity_counts[key] += purity_counts[key]

        # Write the aggregated JSON file
        output_file_path = create_output_file_path(file_name, base_dir=str(output_base_dir))
        try:
            with open(output_file_path, 'w') as f:
                json.dump(aggregated_data, f, indent=2)
            successful_aggregations += 1
        except IOError as e:
            print(f"Error writing aggregated file {output_file_path}: {e}")

    return skipped_files, successful_aggregations, total_purity_counts

def aggregate_data(file_name: str, all_analyses: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """
    Performs the core aggregation logic for a single file's data from all passes.
    Returns the aggregated data and a dictionary of method purity counts.
    """
    base_info = all_analyses[0]
    
    # Aggregate pass-specific metadata into lists
    pass_metadata = {
        "llmModelName": [d.get('llm_model_name') for d in all_analyses],
        "llmAnalysisTimestamp": [d.get('llm_analysis_timestamp') for d in all_analyses],
        "runName": [d.get('run_name') for d in all_analyses],
        "llmResponseTimeSeconds": [d.get('llm_response_time_seconds') for d in all_analyses]
    }

    # Group methods by signature for aggregation
    methods_by_signature = defaultdict(list)
    for analysis in all_analyses:
        for method in analysis.get('llm_analysis', []):
            methods_by_signature[method['methodSignature']].append(method)

    # Aggregate purity info for each method
    aggregated_llm_analysis = []
    purity_counts = {"pure": 0, "impure": 0, "mixed": 0}
    for signature, methods in methods_by_signature.items():
        purity_results = [m.get('purityInfo', {}).get('isPureLLM', False) for m in methods]
        
        is_pure_llm = all(purity_results)
        is_impure_llm = not any(purity_results)
        
        if is_pure_llm:
            purity_counts["pure"] += 1
        elif is_impure_llm:
            purity_counts["impure"] += 1
        else:
            purity_counts["mixed"] += 1

        is_pure_strict = all(m.get('purityInfo', {}).get('isPureStrict', False) for m in methods)
        is_pure_with_reads = all(m.get('purityInfo', {}).get('isPureWithReads', False) for m in methods)
        
        aggregated_llm_analysis.append({
            "methodSignature": signature,
            "className": methods[0].get('className', 'N/A'),
            "aggregatedPurityInfo": {
                "aggregatedIsPureLLM": is_pure_llm,
                "aggregatedIsPureStrict": is_pure_strict,
                "aggregatedIsPureWithReads": is_pure_with_reads
            }
        })

    # Construct the final aggregated JSON object with camelCase keys
    final_data = {
        "fileName": base_info.get('file_name', file_name),
        "sourceType": base_info.get('source_type'),
        "url": base_info.get('url'),
        "sourceCodeFilePath": base_info.get('source_code_file_path'),
        "isSuccess": True,
        **pass_metadata,
        "llmAnalysis": aggregated_llm_analysis
    }
    return final_data, purity_counts

def write_skipped_files_csv(skipped_files: List[Dict[str, str]], aggregation_name: str):
    """
    Writes the list of skipped files to two CSV files.
    """
    if not skipped_files:
        print("No files were skipped.")
        return

    fieldnames = ['fileName', 'sourceType', 'url', 'sourceCodeFilePath']
    
    # Define both output paths for the CSV
    csv_path1 = DIR_FOR_CURRENT_PHASE / "csv_files" / f"llm_aggregation_skipped_filepaths_{aggregation_name}.csv"
    csv_path2 = DIR_FOR_CURRENT_PHASE / "aggregated_purity_analyses" / aggregation_name / f"llm_aggregation_skipped_filepaths_{aggregation_name}.csv"
    
    # Ensure directories exist
    csv_path1.parent.mkdir(exist_ok=True)
    csv_path2.parent.mkdir(parents=True, exist_ok=True)

    for path in [csv_path1, csv_path2]:
        try:
            with open(path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                # Remove duplicates before writing
                unique_skipped = [dict(t) for t in {tuple(d.items()) for d in skipped_files}]
                writer.writerows(unique_skipped)
            print(f"Wrote skipped files CSV to: {path}")
        except IOError as e:
            print(f"Error writing CSV to {path}: {e}")

def main():
    """
    Main function to drive the aggregation script.
    """
    aggregation_name = "gemini-2.5-pro-three-passes"
    
    analysis_directories = [
        "java_llm_analysis_files/gemini-2.5-pro-pass-1",
        "java_llm_analysis_files/gemini-2.5-pro-pass-2",
        "java_llm_analysis_files/gemini-2.5-pro-pass-3"
    ]
    
    output_base_dir = DIR_FOR_CURRENT_PHASE / "aggregated_purity_analyses" / aggregation_name / "analysis"
    output_base_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting aggregation: {aggregation_name}")
    
    # 1. Collect all JSON files from the passes
    file_map = collect_json_files(analysis_directories)
    print(f"Found {len(file_map)} unique files to process.")
    
    # 2. Process files: aggregate or add to skipped list
    skipped_files, successful_count, total_purity_counts = process_files(file_map, aggregation_name, output_base_dir)
    
    # 3. Write the CSV of skipped files
    write_skipped_files_csv(skipped_files, aggregation_name)

    print("\n--- Aggregation Summary ---")
    print(f"Successfully aggregated files: {successful_count}")
    print(f"Skipped files (if at least 1 pass had is_success set to false): {len(skipped_files)}")
    print(f"Total methods classified as Pure by LLM: {total_purity_counts['pure']}")
    print(f"Total methods classified as Impure by LLM: {total_purity_counts['impure']}")
    print(f"Total methods with Mixed LLM results: {total_purity_counts['mixed']}")
    print(f"Aggregated files written to: {output_base_dir}")
    print("---------------------------\n")

if __name__ == "__main__":
    main()
