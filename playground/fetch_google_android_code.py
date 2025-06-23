from time import time
import requests
import base64
import json
from dotenv import load_dotenv
import os
import google.generativeai as genai

load_dotenv()

def get_raw_android_source(url):
    """
    Fetches and decodes raw Java source from android.googlesource.com.
    """
    if '?format=TEXT' not in url:
        url += '?format=TEXT'

    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch source: {response.status_code}")

    decoded = base64.b64decode(response.text).decode("utf-8")
    return decoded

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

# Example usage
raw_url = "https://android.googlesource.com/platform/frameworks/base/+/master/core/java/android/app/Service.java"
java_code = get_raw_android_source(raw_url)

# Sample Java code with a single method class for testing purposes
# java_code = """
# public abstract class Service extends ContextWrapper implements ComponentCallbacks2,
#         ContentCaptureManager.ContentCaptureClient {
#     private static final String TAG = "Service";
#     /**
#      * Selector for {@link #stopForeground(int)}:  equivalent to passing {@code false}
#      * to the legacy API {@link #stopForeground(boolean)}.
#      *
#      * @deprecated Use {@link #STOP_FOREGROUND_DETACH} instead.  The legacy
#      * behavior was inconsistent, leading to bugs around unpredictable results.
#      */
#     @Deprecated
#     public static final int STOP_FOREGROUND_LEGACY = 0;
#     /**
#      * Selector for {@link #stopForeground(int)}: if supplied, the notification previously
#      * supplied to {@link #startForeground} will be cancelled and removed from display.
#      */
#     public static final int STOP_FOREGROUND_REMOVE = 1<<0;
#     /**
#      * Selector for {@link #stopForeground(int)}: if set, the notification previously supplied
#      * to {@link #startForeground} will be detached from the service's lifecycle.  The notification
#      * will remain shown even after the service is stopped and destroyed.
#      */
#     public static final int STOP_FOREGROUND_DETACH = 1<<1;
#     /** @hide */
#     @IntDef(flag = false, prefix = { "STOP_FOREGROUND_" }, value = {
#             STOP_FOREGROUND_LEGACY,
#             STOP_FOREGROUND_REMOVE,
#             STOP_FOREGROUND_DETACH
#     })
#     @Retention(RetentionPolicy.SOURCE)
#     public @interface StopForegroundSelector {}
#     public Service() {
#         super(null);
#     }
#     /** Return the application that owns this service. */
#     public final Application getApplication() {
#         return mApplication;
#     }
# }
# """

# Print the first few lines to verify
# print("\n".join(java_code.splitlines()[:1000]))
print("Fetched Java source code successfully." if len(java_code) > 0 else "No code fetched.")

try:
    # Configure the client with your API key
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except AttributeError:
    print("Error: The GOOGLE_API_KEY environment variable is not set.")
    print("Please set your API key as an environment variable.")
    exit()

system_prompt = """
You are analyzing Java source code to extract memoization-relevant metadata for each method.

You must output a JSON array, where each element corresponds to one method in the input Java class. Each method object must contain the following fields:

- methodSignature (string): Method name and parameter list, e.g., "int compute(int x, String s)"
- className (string): Fully qualified class name (e.g., "android.app.Service")
- reasonAboutStateAccesses (string): Discuss what state the method accesses (read/write, primitive/object, internal/global)
- stateAccesses (array of objects): List of state access records, or [] if there are none. Each record includes:
    - name (string): Fully-qualified field name accessed (e.g., this.cache, Config.VALUE)
    - scope ("INTERNAL" or "GLOBAL"): Whether the field is part of the class or external
    - type ("PRIMITIVE" or "OBJECT"): Data type classification
    - mode ("READ" or "WRITE"): Whether the field was read or written
    - idempotent (boolean or null): Set to null if mode is READ; true/false if WRITE

- reasonAboutSideEffects (string): Explain why this method has or lacks observable side effects (e.g., I/O, UI updates, logging, shared state mutation)
- hasSideEffects (boolean): True if the method performs any observable side effect
- reasonAboutNonDeterministicCalls (string): Discuss whether the method depends on non-deterministic behavior (e.g., time, randomness, system state)
- hasNonDeterministicCalls (boolean): True if the method calls time-based or random functions
- reasonAboutDependsOnArgumentsOnly (string): Explain whether the output depends purely on input parameters
- dependsOnArgumentsOnly (boolean): True if the method's return value is only determined by its arguments and constants

IMPORTANT: All fields are required.
IMPORTANT: If the method does not access any state, return stateAccesses as an empty array [].
IMPORTANT: Ignore static blocks. Ignore constructors.
VERY IMPORTANT: Output must be valid JSON. Ignore abstract methods and unimplemented interface methods. Only include methods that have a concrete implementation.
"""

user_prompt = f"""
Here is the source code for the file you have to analyse according to the schema shared.
Extract metadata for each method in the file based on the schema. Follow all schema constraints strictly. 

FILE SOURCE CODE:
{java_code}
"""

model = genai.GenerativeModel(model_name="gemini-2.5-flash", system_instruction=system_prompt)

response = model.generate_content(user_prompt)

print("#" * 20)
print("#" * 20)
print("Response from Gemini:")

try:
    # Attempt to parse the JSON to validate it
    # Pretty-print the validated JSON
    trimmed_response = clean_llm_json_output(response.text)
    parsed_json = json.loads(trimmed_response)
    print("\nSUCCESS: Gemini output was valid JSON.")
    final_response = json.dumps(parsed_json, indent=2)
    print(final_response)

except (json.JSONDecodeError, ValueError) as e:
    print(f"ERROR: Gemini output was not valid JSON. Reason: {e}")
    print("\n--- Raw Gemini Output ---")
    print(response.text)
    final_response = response.text

write_file = f"gemini_output_{time()}.json"
with open(write_file, "w") as f:
    f.write(final_response)