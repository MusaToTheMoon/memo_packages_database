#!/usr/bin/env python3
"""
Script to fetch code from either a single url or a csv of urls
    a CSV file    : fetch_code.py csv path_to_csv_file                # csv file should contain the file_name,source_type,url triples
    a single URL  : fetch_code.py url file_name source_type url       # handles a single url, must also provide file_name and source_type

Format for file_name, source_type:
    file_name := full file name e.g. android.app.Service
    source_type := android.googlesource | github
"""

import argparse
import requests
import base64
import sys
import os
from dotenv import load_dotenv

load_dotenv()
project_root = os.environ.get("PROJECT_ROOT", ".")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Handle a single URL or a list of URLs in a CSV file.")
    sub = parser.add_subparsers(dest="mode", required=True, help="Choose input mode")

    # url mode
    url_p = sub.add_parser("url", help="Process one URL")
    url_p.add_argument("file_name", type=str, help="file_name - used to name the output file")
    # url_p.add_argument("package_name", type=str, help="Package the file belongs to")
    url_p.add_argument("source_type", type=str, help="source of the java code, options: 'android.googlesource', 'github'")
    url_p.add_argument("url", type=str, help="Provide URL to process")

    # csv mode
    csv_p = sub.add_parser("csv", help="Process a CSV file of URLs")
    csv_p.add_argument("path_to_csv_file", type=str, help="Path to the CSV file containing URLs")

    return parser

def write_code_to_file(source_code, file_name, source_type, url):
    file_path = create_output_file_path(file_name, base_dir=os.path.join(project_root, "java_source_code_files"))

    try:
        with open(file_path, 'w') as f:
            # preprend metadata
            metadata = (
                f"// file_name   : {file_name}\n"
                f"// source_type : {source_type}\n"
                f"// url         : {url}\n\n"
            )
            
            f.write(metadata + source_code)

        print(f"Successfully wrote source code from {file_name} to {file_path}.")
    except (OSError, IOError) as e:
        print(f"Error while writing source code to file: {e}")
        print(f"File Details: {file_name}, {source_type}, {url}")
        print("Moving onto next URL.")

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

def fetch_code_from_single_url(file_name, source_type, url):
    """
    Fetches code from a given URL based on the source type.
    """
    print(f"Processing single URL: {url}")
    print(f"File Details: {file_name}, {source_type}")

    if source_type == "android.googlesource":
        source_code = fetch_code_from_android_googlesource(url)
    elif source_type == "github":
        source_code = fetch_code_from_github(url)
    else:
        raise ValueError(f"Unsupported source type: {source_type}")
    
    return source_code

def fetch_code_from_android_googlesource(url):
    """
    Fetches and decodes raw Java source from android.googlesource.com.
    """
    if '?format=TEXT' not in url:
        url += '?format=TEXT'

    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch source: {response.status_code}")

    decoded = base64.b64decode(response.text).decode("utf-8")
    return decoded

def fetch_code_from_github(url):
    """
    Fetches and decodes raw Java source from GitHub. Converts regular GitHub URLs to raw URLs if needed.
    """
    if "github.com" in url and "raw.githubusercontent.com" not in url:
        url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch source: {response.status_code}")

    return response.text

def main():
    args = build_parser().parse_args()

    if args.mode == "url":
        source_code = fetch_code_from_single_url(args.file_name, args.source_type, args.url)
        if len(source_code) > 0:
            print("Fetched Java source code successfully.")
            write_code_to_file(source_code, args.file_name, args.source_type, args.url)

        else:
            print("Error. No code fetched. Exiting.")
            sys.exit(1)

    elif args.mode == "csv":
        print(f"Processing CSV file: {args.path_to_csv_file}")
        if not os.path.exists(args.path_to_csv_file):
            print(f"Error: The specified CSV file does not exist: {args.path_to_csv_file}")
            sys.exit(1)
        with open(args.path_to_csv_file, "r") as f:
            for line in f:
                # line := file_name,source_type,url
                line = line.strip()
                if not line:
                    continue
                parts = line.split(',')
                if len(parts) != 3:
                    print(f"Skipping malformed line: {line}")
                    print("="*50)
                    continue

                try:
                    source_code = fetch_code_from_single_url(*parts)
                except Exception as e:
                    print(e)
                    print(f"Skipping this line: {line}")
                    print("="*50)
                    continue

                if len(source_code) > 0: # in casse the source code is empty
                    print("Fetched Java source code successfully.")
                    write_code_to_file(source_code, parts[0], parts[1], parts[2])

                else:
                    print(f"Fetching code failed.\nSkipping line: {line}.")
                print("="*50)
                
            print("Code has been fetched from all URLs in the CSV file.")

if __name__ == "__main__":
    main()

### Task List:
# - [ ] Update to work with the new phase based directory structure
# - [ ] Automatically write failed URLs to a separate CSV file along with the file_name, source_type
    # like done in label_llm.py