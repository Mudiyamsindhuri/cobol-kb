import os
import json
import requests
import re
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_PATH = os.path.join(BASE_DIR, "cobol")
OUTPUT_FILE = os.path.join(BASE_DIR, "kb", "kb.json")

MODEL = "gemma3:4b"
OLLAMA_URL = "http://localhost:11434/api/generate"

# PROMPT
def build_prompt(code):
    return f"""
You are a COBOL expert.

STRICT RULES:
- Return COMPLETE JSON
- No explanation
- No markdown
- Always valid JSON

FORMAT:
{{
  "program": "<program name>",
  "summary": "<what this file does>",
  "nodes": [
    {{"name": "<entity>", "type": "<PROGRAM|COPYBOOK|FILE>"}}
  ],
  "relationships": [
    {{"source": "<entity>", "target": "<entity>", "relation": "<CALLS|USES|READS|WRITES>"}}
  ]
}}

COBOL CODE:
{code}
"""
# CALL LLM
def call_ollama(prompt):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 2048}
            },
            timeout=300
        )

        return response.json().get("response", "")

    except Exception as e:
        print("Ollama Error:", e)
        return ""
def clean_json(text):
    text = text.replace("```json", "").replace("```", "").strip()

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except:
        return None


# FALLBACK PARSER (BASIC REGEX)

def fallback_parser(code, filename):

    program = os.path.splitext(filename)[0]

    calls = re.findall(r"CALL\s+'(\w+)'", code, re.IGNORECASE)
    copybooks = re.findall(r"COPY\s+(\w+)", code, re.IGNORECASE)
    files = re.findall(r"SELECT\s+(\w+)", code, re.IGNORECASE)

    nodes = [{"name": program, "type": "PROGRAM"}]
    rels = []

    for c in calls:
        nodes.append({"name": c, "type": "PROGRAM"})
        rels.append({"source": program, "target": c, "relation": "CALLS"})

    for cb in copybooks:
        nodes.append({"name": cb, "type": "COPYBOOK"})
        rels.append({"source": program, "target": cb, "relation": "USES"})

    for f in files:
        nodes.append({"name": f, "type": "FILE"})
        rels.append({"source": program, "target": f, "relation": "REFERS"})

    return {
        "program": program,
        "summary": "Auto-generated summary (fallback)",
        "nodes": nodes,
        "relationships": rels
    }
def process_file(path):

    file = os.path.basename(path)

    with open(path, "r", errors="ignore") as f:
        code = f.read()

    print("📄 Processing:", file)

    output = call_ollama(build_prompt(code[:1500]))

    data = clean_json(output)

    if not data:
        print(" Using fallback for", file)
        data = fallback_parser(code, file)

    return data

# =============================
# MAIN
# =============================
def main():

    all_nodes = []
    all_rels = []
    summaries = []

    for file in os.listdir(INPUT_PATH):

        if file.endswith(".cbl"):

            path = os.path.join(INPUT_PATH, file)

            data = process_file(path)

            all_nodes.extend(data.get("nodes", []))
            all_rels.extend(data.get("relationships", []))

            summaries.append({
                "file": file,
                "summary": data.get("summary", "")
            })

    # REMOVE DUPLICATES
    nodes = list({(n["name"], n["type"]): n for n in all_nodes}.values())
    rels = list({(r["source"], r["target"], r["relation"]): r for r in all_rels}.values())

    final = {
        "nodes": nodes,
        "relationships": rels,
        "summaries": summaries
    }

    os.makedirs(os.path.join(BASE_DIR, "kb"), exist_ok=True)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(final, f, indent=2)

    print("\n KB Generated at:", OUTPUT_FILE)


if __name__ == "__main__":
    main()