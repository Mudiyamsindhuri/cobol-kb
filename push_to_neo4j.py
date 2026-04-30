from neo4j import GraphDatabase
import json
import os
import requests

# =============================
# CONFIG
# =============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_FILE = os.path.join(BASE_DIR, "kb", "kb.json")

NEO4J_URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "password"

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

driver = GraphDatabase.driver(NEO4J_URI, auth=(USER, PASSWORD))


# =============================
# EMBEDDINGS
# =============================
def get_embedding(text):
    try:
        res = requests.post(
            OLLAMA_EMBED_URL,
            json={"model": EMBED_MODEL, "prompt": text}
        )
        return res.json().get("embedding", [])
    except Exception as e:
        print("Embedding error:", e)
        return []


# =============================
# NORMALIZE RELATION
# =============================
def normalize_relation(rel):
    return rel.replace(" ", "_").upper()


# =============================
# BUILD GRAPH
# =============================
def create_graph(tx, data):

    # NODES
    for n in data.get("nodes", []):
        name = n["name"]
        ntype = n["type"]

        embedding = get_embedding(f"{name} {ntype}")

        tx.run("""
            MERGE (e:Entity {name:$name})
            SET e.type = $type,
                e.embedding = $embedding
        """, name=name, type=ntype, embedding=embedding)

    # RELATIONSHIPS
    for r in data.get("relationships", []):

        relation = normalize_relation(r["relation"])

        tx.run(f"""
            MATCH (a:Entity {{name:$s}})
            MATCH (b:Entity {{name:$t}})
            MERGE (a)-[r:{relation}]->(b)
        """, s=r["source"], t=r["target"])


# =============================
# MAIN
# =============================
def main():
    with open(KB_FILE) as f:
        data = json.load(f)

    with driver.session() as session:
        session.execute_write(create_graph, data)

    print(" Neo4j Graph + Embeddings Loaded Successfully")


if __name__ == "__main__":
    main()