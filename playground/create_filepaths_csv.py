"""
This script reads two csv files and essentially carries out a subtraction/set difference operation by removing any entries in the first file that are present in the second file.
Input files contain rows of the format: file_name,source_type,url
Example:
    java.lang.Service,github,https://github.com/openjdk/jdk/blob/master/src/java.base/share/classes/java/lang/Service.java


It then adds a file_path column to the output file, which is generated as "java_source_code_files/<file_name>.java" where <file_name> is the full Java-style package name (android.app.Service -> java_source_code_files/android/app/Service.java)
Example:
    java.lang.Service,github,https://github.com/openjdk/jdk/blob/master/src/java.base/share/classes/java/lang/Service.java,java_source_code_files/android/app/Service.java


Details:
    - Update 'dir_containing_code' variable to change the directory where the source code files live.
    - Update 'dir_for_defaults' variable to change the directory where the default input, output, and subtract CSV files are located.
    - Scroll down to the main() function for usage examples. 
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
project_root = os.environ.get("PROJECT_ROOT", ".")
dir_for_current_phase = os.environ.get("DIR_FOR_CURRENT_PHASE", project_root)  # Default to project root if not set
dir_containing_code = "java_source_code_files" # change to "kotlin_source_code_files" if you want to create Kotlin file paths

def create_output_file_path(file_name, ext="java"):
    """
    Converts a dotted Java-style package name into a file path
    """
    *dirs, class_name = file_name.split('.')
    return os.path.join(dir_containing_code, *dirs, f"{class_name}.{ext}")

def read_csv_rows_ordered(file_path):
    """
    Read CSV file and return list of rows preserving order
    """
    rows = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:  # Skip empty lines
                rows.append(line)
    return rows

def read_csv_rows_set(file_path):
    """
    Read CSV file and return set of rows for fast lookup
    """
    rows = set()
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:  # Skip empty lines
                rows.add(line)
    return rows

def process_csv_files(input_file, output_file, subtract_file=None):
    """
    Process CSV files: subtract entries from subtract_file (if provided) and add file_path column
    """
    print(f"Processing input file: {input_file}")
    
    # Read the main input file as ordered list
    input_rows = read_csv_rows_ordered(input_file)
    print(f"Read {len(input_rows)} rows from input file")
    
    # Read the subtract file if provided
    if subtract_file:
        print(f"Processing subtract file: {subtract_file}")
        subtract_rows = read_csv_rows_set(subtract_file)  # Use set for 2nd CSV file for faster lookup later
        print(f"Read {len(subtract_rows)} rows from subtract file")
        
        # Filter out rows that are in subtract_file, preserving order
        result_rows = [row for row in input_rows if row not in subtract_rows]
        print(f"After subtraction: {len(result_rows)} rows remaining")
    else:
        print("No subtract file provided, keeping all rows")
        result_rows = input_rows
    
    # Before writing to output, ensure the output directory exists
    output_path = Path(output_file)
    os.makedirs(output_path.parent, exist_ok=True)

    # Write output file with file_path column added
    print(f"Writing output to: {output_file}")
    with open(output_file, 'w') as f:
        for row in result_rows:  # Now preserves original order
            parts = row.split(',')
            if len(parts) >= 3:  # Ensure we have at least file_name,source_type,url
                file_name = parts[0]
                file_path = create_output_file_path(file_name)
                # Write original row + file_path
                f.write(f"{row},{file_path}\n")
            else:
                print(f"Skipping malformed row: {row}")
    
    print(f"Successfully wrote {len(result_rows)} rows to {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description="Process CSV files: subtract entries and add file_path column",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_filepaths_csv.py                                    # Use all defaults (with subtract)
  python create_filepaths_csv.py --no-subtract                      # Use defaults but no subtraction
  python create_filepaths_csv.py --input custom.csv                 # Custom input, default subtract
  python create_filepaths_csv.py --input custom.csv --no-subtract   # Custom input, no subtraction
  python create_filepaths_csv.py --subtract custom_failed.csv       # Custom subtract file
  python create_filepaths_csv.py --output custom_output.csv         # Custom output file
  
Input CSV format: file_name,source_type,url
Output CSV format: file_name,source_type,url,file_path
        """
    )

    dir_for_defaults = Path(dir_for_current_phase) / "csv_files" # note phase 1 refers to the first phase of collecting java source code URLs, and then getting them labelled by LLMs. In other places, you will see 'round one' which refers to the 

    parser.add_argument("--input", default=dir_for_defaults / "java_source_code_urls.csv", help="Input CSV file to process")
    parser.add_argument("--subtract", default=None, help=f"CSV file with entries to subtract from input file (default: {dir_for_defaults / 'java_source_code_urls_failed.csv'}, use --no-subtract to disable)")
    parser.add_argument("--no-subtract", action="store_true", help="Disable subtraction entirely")
    parser.add_argument("--output", default=dir_for_defaults / "java_filepaths.csv", help=f"Output CSV file to create (default: {dir_for_defaults / 'java_filepaths.csv'})")
    
    args = parser.parse_args()
    
    # Handle subtract logic: use default if not specified and not disabled
    if not args.no_subtract and args.subtract is None:
        args.subtract = dir_for_defaults / "java_source_code_urls_failed.csv"
    elif args.no_subtract:
        args.subtract = None
    
    # Validate input files exist
    if not Path(args.input).exists():
        print(f"Error: Input file does not exist: {args.input}")
        sys.exit(1)
    
    if args.subtract and not Path(args.subtract).exists():
        print(f"Error: Subtract file does not exist: {args.subtract}")
        sys.exit(1)

    # Process the files
    try:
        process_csv_files(args.input, args.output, args.subtract)
        print("Processing completed successfully!")
    except Exception as e:
        print(f"Error processing files: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

## Task List:
# - [DONE] Make it work with defaults
# - [DONE] Update to work with the new phase based directory structure
    # - [DONE] Test
