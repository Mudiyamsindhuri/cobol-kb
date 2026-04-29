import os
import json
import requests
import re

# =============================
# CONFIG
# =============================
MODEL = "gemma3:4b"
OLLAMA_URL = "http://localhost:11434/api/generate"

INPUT_PATH = r"C:\Users\asiqs\Desktop\cobol-kb\cobol"
OUTPUT_FILE = "kb.json"

# =============================
# PROMPT BUILDER
# =============================
def build_prompt(code):
    return f"""
You are a COBOL expert.

STRICT RULES:
- Return COMPLETE JSON
- Do NOT cut response
- Always include ALL fields
- Always include at least 2 relationships

JSON FORMAT:
{{
  "program": "<program name>",
  "summary": "<short explanation>",
  "nodes": [
    {{"name": "<entity>", "type": "<PROGRAM|COPYBOOK|FILE|PARAGRAPH>"}}
  ],
  "relationships": [
    {{"source": "<entity>", "target": "<entity>", "relation": "<CALLS|USES|READS|WRITES>"}}
  ]
}}

IMPORTANT:
- Do NOT truncate
- If unsure → still return best guess
- ALWAYS return valid JSON

COBOL CODE:
{code}
"""

# =============================
# CALL OLLAMA
# =============================
def call_ollama(prompt):
    try:
        print("Calling LLM...")
        response = requests.post(
    OLLAMA_URL,
    json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 4096   
        }
    },
    timeout=600
)

        if response.status_code != 200:
            print("LLM Error:", response.text)
            return ""

        return response.json().get("response", "")

    except Exception as e:
        print("Ollama Error:", e)
        return ""

# =============================
# SAFE JSON EXTRACTOR
# =============================
def clean_json(text):
    text = text.replace("```json", "").replace("```", "").strip()

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except:
        return None


# =============================
# FALLBACK PARSER (Regex Based)
# =============================
def fallback_parser(code, filename):
    program_name = os.path.splitext(filename)[0]

    calls = list(set(re.findall(r"CALL\s+'(\w+)'", code, re.IGNORECASE)))
    copybooks = list(set(re.findall(r"COPY\s+(\w+)", code, re.IGNORECASE)))
    files = list(set(re.findall(r"SELECT\s+(\w+)", code, re.IGNORECASE)))

    nodes = [{"name": program_name, "type": "PROGRAM"}]
    relationships = []

    for cb in copybooks:
        nodes.append({"name": cb, "type": "COPYBOOK"})
        relationships.append({
            "source": program_name,
            "target": cb,
            "relation": "USES"
        })

    for f in files:
        nodes.append({"name": f, "type": "FILE"})
        relationships.append({
            "source": program_name,
            "target": f,
            "relation": "REFERS"
        })

    for c in calls:
        nodes.append({"name": c, "type": "PROGRAM"})
        relationships.append({
            "source": program_name,
            "target": c,
            "relation": "CALLS"
        })

    return {
        "nodes": nodes,
        "relationships": relationships,
        "summary": "Basic extraction using regex fallback"
    }

# =============================
# PROCESS FILE
# =============================
def process_file(filepath):
    print(f"\nProcessing: {filepath}")

    filename = os.path.basename(filepath)

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        code = f.read()

    prompt = build_prompt(code[:1200])
    output = call_ollama(prompt)

    print("\n--- RAW OUTPUT ---\n")
    print(output[:300])

    data = clean_json(output)

    if not data:
        print("Using fallback parser")
        data = fallback_parser(code, filename)

    return data, filename

# =============================
# MAIN
# =============================
def main():
    all_nodes = []
    all_relationships = []
    summaries = []

    if not os.path.exists(INPUT_PATH):
        print("Invalid path")
        return

    for file in os.listdir(INPUT_PATH):
        if file.lower().endswith((".cob", ".cbl", ".cobol")):
            filepath = os.path.join(INPUT_PATH, file)

            data, filename = process_file(filepath)

            # Collect graph data
            all_nodes.extend(data.get("nodes", []))
            all_relationships.extend(data.get("relationships", []))

            summaries.append({
                "file": filename,
                "summary": data.get("summary", "")
            })

    # Remove duplicate nodes
    unique_nodes = { (n["name"], n["type"]): n for n in all_nodes }
    unique_nodes = list(unique_nodes.values())

    # Remove duplicate relationships
    unique_rels = { 
        (r["source"], r["target"], r["relation"]): r 
        for r in all_relationships 
    }
    unique_rels = list(unique_rels.values())

    final_output = {
        "nodes": unique_nodes,
        "relationships": unique_rels,
        "summaries": summaries
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(final_output, f, indent=2)

    print("\nKnowledge Graph JSON created:", OUTPUT_FILE)

# =============================
# RUN
# =============================
if __name__ == "__main__":
    main()