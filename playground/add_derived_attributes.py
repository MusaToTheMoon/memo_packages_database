"""
This script adds a derived attribute "isPure" to each dictionary in a JSON list.
The attribute is calculated based on three existing keys:
- hasSideEffects
- hasNonDeterministicCalls
- dependsOnArgumentsOnly   
"""
import json
import os

def hasReadAccessesOnly(stateAccesses):
    """
    Check if there are any read accesses in the stateAccesses list.
    """
    return 

input_file = "llm_analysis_files/java/lang/Service.json"

with open(input_file, "r") as f:
    data = json.load(f)

# Assuming the data is a list of dictionaries
for item in data:
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

base, ext = os.path.splitext(input_file)
output_file = f"{base}_with_derived_attributes{ext}"

with open(output_file, "w") as f:
    json.dump(data, f, indent=2)

print(f"Derived attributes added and saved to {output_file}")
