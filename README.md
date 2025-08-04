# memo-packages-database

## Dependencies
- Infer from Meta: I downloaded using the following command. Change as required for your system. For help, see [Infer Getting Started Guide](https://fbinfer.com/docs/getting-started)
```
VERSION=1.2.0
curl -sSL \  "https://github.com/facebook/infer/releases/download/v$VERSION/infer-osx-arm64-v$VERSION.tar.xz" | sudo tar -C /usr/local -xJ
sudo ln -sf "/usr/local/infer-osx-arm64-v$VERSION/bin/infer" /usr/local/bin/infer
```

### usage
cd playground
python fetch_code.py csv path_to_csv_file
python label_llm.py path_to_csv_file [--model-name <model-name> --run-name <run-name>]

### for example
cd playground
python fetch_code.py csv ../java_source_code_urls.csv
python label_llm.py temp.csv --model-name gemini-2.5-flash --run-name gemini-2.5-flash-run3