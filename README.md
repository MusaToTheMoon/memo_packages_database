# memo-packages-database

This project analyzes Java source code to determine method purity for memoization suitability using LLMs.

## Project Structure

### `phase1/`

This directory contains all the data related to the first phase of analysis.

-   **`java_source_code_files/`**: Contains the raw Java source code files that are being analyzed.
-   **`csv_files/`**: Holds CSV files that drive the analysis pipeline, such as `java_filepaths.csv` which lists the source code filepaths to be processed.
-   **`java_llm_analysis_files/`**: Stores the raw JSON output from each individual pass of the LLM analysis. Each sub-directory (e.g., `gemini-2.5-pro-pass-1`) corresponds to a single run.
-   **`aggregated_purity_analyses/`**: Contains the final, aggregated analysis results. The JSON files here are created by combining the results from the multiple passes in `java_llm_analysis_files`. [gemini-2.5-pro-three-passes](phase1/aggregated_purity_analyses/gemini-2.5-pro-three-passes) is based on [gemini-2.5-pro-pass-1](phase1/java_llm_analysis_files/gemini-2.5-pro-pass-1), [gemini-2.5-pro-pass-2](phase1/java_llm_analysis_files/gemini-2.5-pro-pass-2), [gemini-2.5-pro-pass-3](phase1/java_llm_analysis_files/gemini-2.5-pro-pass-3).

### `playground/`

This directory contains all the Python scripts used to run the analysis pipeline.

-   **[`fetch_code.py`](playground/fetch_code.py)**: Fetches Java source code from URLs provided either individually or in a CSV file and saves them into the `phase1/java_source_code_files/` directory, ready for analysis.
-   **[`create_filepaths_csv.py`](playground/create_filepaths_csv.py)**: A utility script to generate a CSV file of file paths from a list of source code URLs. This CSV is used as input for the labeling script.
-   **[`label_llm.py`](playground/label_llm.py)**: This is the main script for LLM analysis. It reads Java files specified in a CSV, sends the code to an LLM for purity analysis, and saves the results as structured JSON files in the `phase1/java_llm_analysis_files/` directory.
-   **[`aggregate_purity_results.py`](playground/aggregate_purity_results.py)**: This script aggregates the results from multiple LLM analysis passes. It combines the JSON outputs for each file, calculates a consensus on method purity (pure, impure, or mixed), and saves the final aggregated JSON in the `phase1/aggregated_purity_analyses/` directory.
-   The remaining scripts are to experiment with logic before adding new functionality to the scripts above. Ignore these.

## License

MIT License

Copyright (c) 2025 Muhammad Musa Khan. Attribution required, no warranty provided.