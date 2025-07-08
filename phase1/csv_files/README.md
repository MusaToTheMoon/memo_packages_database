This contains the csv files for round 1 of collecting java source code files from URLs and then labelling them using an LLM (gemini-2.5-flash or pro). It contains
    1. java_source_code_urls.csv: consumed by fetch_code.csv. Created manually.
    2. java_source_code_urls_failed.csv: contains rows from (1) that code could not be fetched from successfully
    3. java_filepaths.csv: consumed by label_llm.py. Created from (1) and (2) using 'create_filepaths_csv.py'.
    4. java_filepaths_failed: contains rows from (3) that could not be processed by the LLM successfully. Produced as output from 'label_llm.py'.