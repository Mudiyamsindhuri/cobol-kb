from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda
from neo4j import GraphDatabase
import requests

# =============================
# NEO4J CONNECTION
# =============================
driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "password")
)

def run_query(cypher):
    with driver.session() as session:
        result = session.run(cypher)
        return [r.data() for r in result]

# =============================
# LLM CALL (OLLAMA)
# =============================
def call_llm(prompt):
    res = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "gemma3:4b",
            "prompt": prompt,
            "stream": False
        }
    )
    return res.json()["response"]

# =============================
# STEP 1: UNDERSTAND QUESTION
# =============================
def understand(state):
    question = state["question"]

    prompt = f"""
You are a Neo4j expert.

Your job: Convert user question into Cypher query.

DATABASE STRUCTURE:
- All nodes use label: Entity
- Node property:
    - name
    - type (PROGRAM, COPYBOOK, FILE, PARAGRAPH)
    - description

STRICT RULES:
- ALWAYS use: MATCH (n:Entity)
- NEVER use labels like PROGRAM, FILE, etc.
- ALWAYS filter using:
    WHERE toLower(n.type) = '<type>'
- ALWAYS return:
    RETURN n.name, n.description
- NO markdown
- NO explanation
- ONLY Cypher

User Question:
{question}

Examples:

List all programs
MATCH (n:Entity)
WHERE toLower(n.type) = 'program'
RETURN n.name, n.description

List all files
MATCH (n:Entity)
WHERE toLower(n.type) = 'file'
RETURN n.name, n.description
"""

    cypher = call_llm(prompt).strip()

    # SAFETY FIX (auto-correct if LLM fails)
    if "MATCH (p:PROGRAM)" in cypher or "MATCH (p:" in cypher:
        cypher = """
MATCH (n:Entity)
WHERE toLower(n.type) = 'program'
RETURN n.name, n.description
"""

    return {
        "cypher": cypher,
        "question": question
    }
# =============================
# STEP 2: RUN QUERY
# =============================
def clean_cypher(text):
    text = text.replace("```cypher", "").replace("```", "").strip()

    # Keep only from MATCH onwards
    if "MATCH" in text:
        text = text[text.index("MATCH"):]

    return text.strip()

def query_db(state):
    cypher = clean_cypher(state["cypher"])
    print("\nGenerated Cypher:\n", cypher)

    try:
        records = run_query(cypher)

        if not records:
            result = "No data found."
        else:
            result = "\n".join(
                f"{r.get('n.name') or r.get('name')} : {r.get('n.description','')}"
                for r in records
            )

    except Exception as e:
        result = f"Error: {str(e)}"

    return {
        "result": result,
        "question": state["question"]   
    }
# =============================
# STEP 3: FORMAT ANSWER
# =============================
def format_answer(state):
    prompt = f"""
User Question:
{state['question']}

Database Result:
{state['result']}

Explain in simple English.
"""

    answer = call_llm(prompt)
    return {"answer": answer}

# =============================
# BUILD GRAPH
# =============================
builder = StateGraph(dict)

builder.add_node("understand", understand)
builder.add_node("query", query_db)
builder.add_node("format", format_answer)

builder.set_entry_point("understand")

builder.add_edge("understand", "query")
builder.add_edge("query", "format")
builder.add_edge("format", END)

graph = builder.compile()

# =============================
# RUN AGENT
# =============================
if __name__ == "__main__":
    while True:
        q = input("Ask: ")
        result = graph.invoke({"question": q})
        print("\nAnswer:", result["answer"])