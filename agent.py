from neo4j import GraphDatabase
import requests
import numpy as np
import re

# =============================
# CONFIG
# =============================
NEO4J_URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "password"

OLLAMA_URL = "http://localhost:11434/api/generate"
EMBED_URL = "http://localhost:11434/api/embeddings"

MODEL = "gemma4:e2b"   
EMBED_MODEL = "nomic-embed-text:latest"

driver = GraphDatabase.driver(NEO4J_URI, auth=(USER, PASSWORD))


# =============================
# EMBEDDINGS
# =============================
def get_embedding(text):
    try:
        res = requests.post(
            EMBED_URL,
            json={"model": EMBED_MODEL, "prompt": text}
        )

        data = res.json()
        emb = data.get("embedding", [])

        if not emb:
            print(f"⚠️ Empty embedding for: {text}")

        return emb

    except Exception as e:
        print(" Embedding error:", e)
        return []


# =============================
# COSINE SIMILARITY
# =============================
def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)

    if len(a) == 0 or len(b) == 0:
        return 0.0

    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# =============================
# VECTOR SEARCH (RAG)
# =============================
def search_similar(query):

    q_emb = get_embedding(query)

    if not q_emb:
        print(" Skipping vector search (no embedding)")
        return []

    cypher = """
    MATCH (e:Entity)
    WHERE e.embedding IS NOT NULL AND size(e.embedding) > 0
    RETURN e.name AS name, e.type AS type, e.embedding AS embedding
    """

    with driver.session() as session:
        rows = session.run(cypher).data()

    scored = []

    for r in rows:
        score = cosine_similarity(q_emb, r["embedding"])
        scored.append({
            "name": r["name"],
            "type": r["type"],
            "score": score
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    return scored[:10]


# =============================
# CONTEXT BUILDER
# =============================
def build_context(results):

    if not results:
        return None
    context = "\n".join(
        f"- {r['name']} ({r['type']})"
        for r in results
    )

    return context


# =============================
# CLEAN OUTPUT (STRICT FORMAT)
# =============================
def clean_output(text):

    
    text = re.sub(r"\b\d{4,}\b", "", text)

    
    text = re.sub(r"(,\s*)?\d{3,}", "", text)

    text = re.sub(r"\*{2,}", "", text)
    text = re.sub(r"#{2,}", "", text)

    
    text = re.sub(r"As a senior.*?:", "", text, flags=re.IGNORECASE)

    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r"\s+", " ", text).strip()

    
    if "Purpose:" not in text:
        return "Improper format returned. Try again."

    return text


# =============================
# LLM CALL
# =============================
def call_llm(prompt):

    try:
        res = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 1024
                }
            }
        )

        data = res.json()

        output = data.get("response") or data.get("message", {}).get("content", "")

        if not output:
            return "Empty response from model"

        return clean_output(output)

    except Exception as e:
        return f"LLM Error: {e}"


# =============================
# AGENT LOGIC (WITH FALLBACK)
# =============================
def answer_question(question):

    print("\n🔍 Running RAG pipeline...")

    results = search_similar(question)
    context = build_context(results)

  
    if not context:
        print(" No context found → switching to LLM-only mode")

        prompt = f"""
You are a senior COBOL system architect.

STRICT RULES:
- DO NOT add introduction sentences
- DO NOT add markdown or symbols
- ONLY return structured output

Question:
{question}

OUTPUT FORMAT:

Purpose:
<clear explanation>

How it works:
<step-by-step explanation>

Where it is used:
<specific usage>

Impact on system:
<system-level impact>
"""
        return call_llm(prompt)

    # RAG MODE
    prompt = f"""
You are a senior COBOL system architect.

STRICT RULES:
- DO NOT add introduction sentences
- DO NOT add markdown or symbols
- ONLY use given context
- ONLY return structured output

Context:
{context}

Question:
{question}

OUTPUT FORMAT:

Purpose:
<clear explanation>

How it works:
<step-by-step explanation>

Where it is used:
<specific usage>

Impact on system:
<system-level impact>
"""

    return call_llm(prompt)


# =============================
# MAIN LOOP
# =============================
if __name__ == "__main__":

    print(" COBOL GraphRAG Agent Ready (Structured + Robust)")

    while True:
        q = input("\nAsk COBOL system: ")

        if q.lower() in ["exit", "quit"]:
            break

        ans = answer_question(q)
        print("\n Answer:\n", ans)