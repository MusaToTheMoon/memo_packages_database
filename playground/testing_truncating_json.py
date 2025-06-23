"""
This file is to test the truncation of JSON output from a GEMINI model response.
Result: Truncation logic is correct.
"""

import json
import time

def clean_llm_json_output(raw_text):
    for prefix in ("'''json", "```json"):
        if raw_text.startswith(prefix):
            # Remove opening block
            raw_text = raw_text[len(prefix):].strip()

    # Remove trailing code block if it exists
    for suffix in ("'''", "```"):
        if raw_text.endswith(suffix):
            raw_text = raw_text[:-3].strip()

    return raw_text

# simulate response from Gemini model
class Response:
    def __init__(self, text):
        self.text = text

with open("gemini_output_service_java.json", "r") as f:
    response = Response(f"""```json
{f.read()}
```""")

# print(response.text)

### LOGIC TO TEST    
try:
    # Attempt to parse the JSON to validate it
    # Pretty-print the validated JSON
    trimmed_response = clean_llm_json_output(response.text)
    parsed_json = json.loads(trimmed_response)
    print("SUCCESS: Gemini output was valid JSON.")
    final_response = json.dumps(parsed_json, indent=2)
    print(final_response)

except (json.JSONDecodeError, ValueError) as e:
    print(f"ERROR: Gemini output was not valid JSON. Reason: {e}")
    print("\n--- Raw Gemini Output ---")
    print(response.text)
    final_response = response.text

write_file = f"gemini_output_{time.time()}.json"
with open(write_file, "w") as f:
    f.write(final_response)