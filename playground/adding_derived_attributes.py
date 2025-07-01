"""
This script adds a derived attribute "isPure" to each dictionary in a JSON list.
The attribute is calculated based on three existing keys:
- hasSideEffects
- hasNonDeterministicCalls
- dependsOnArgumentsOnly   
"""
import json
import os

input_file = "playground/gemini_output_1750715916.544393.json"

with open(input_file, "r") as f:
    data = json.load(f)

# Assuming the data is a list of dictionaries
for item in data:
    try:
        item["isPure"] = (
            not item["hasSideEffects"] 
            and not item["hasNonDeterministicCalls"] 
            and item["dependsOnArgumentsOnly"]
        )
    except KeyError as e:
        print(f"KeyError: {e} in item {item}. Skipping this item.")
        item["isPure"] = None

base, ext = os.path.splitext(input_file)
output_file = f"{base}_with_derived_attributes{ext}"

with open(output_file, "w") as f:
    json.dump(data, f, indent=2)

print(f"Derived attributes added and saved to {output_file}")
