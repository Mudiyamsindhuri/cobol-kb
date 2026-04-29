from neo4j import GraphDatabase
import json
import re

URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "password"

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))


# =============================
# CLEAN RELATION TYPE
# =============================
def clean_relation(rel):
    if not rel:
        return "RELATED_TO"

    rel = rel.upper().strip()
    rel = re.sub(r"[^A-Z0-9_]", "_", rel)  # remove spaces/symbols
    return rel


# =============================
# CREATE GRAPH
# =============================
def create_graph(tx, item, summary_map):

    nodes = item.get("nodes", [])
    rels = item.get("relationships", [])

    if not nodes:
        return

    # 🔹 CREATE NODES
    for node in nodes:
        name = node.get("name")
        ntype = node.get("type", "UNKNOWN")

        if not name:
            continue

        # attach description if exists
        description = summary_map.get(name.upper(), "")

        tx.run("""
            MERGE (n:Entity {name: $name})
            SET n.type = $type,
                n.description = $desc
        """, name=name, type=ntype, desc=description)

    # CREATE RELATIONSHIPS
    for rel in rels:
        source = rel.get("source")
        target = rel.get("target")
        relation = clean_relation(rel.get("relation"))

        if not source or not target:
            continue

        query = f"""
            MATCH (a:Entity {{name: $source}})
            MATCH (b:Entity {{name: $target}})
            MERGE (a)-[r:{relation}]->(b)
        """

        tx.run(query, source=source, target=target)


# =============================
# BUILD SUMMARY MAP
# =============================
def build_summary_map(data):
    summary_map = {}

    if isinstance(data, dict) and "summaries" in data:
        for item in data["summaries"]:
            file = item.get("file", "")
            summary = item.get("summary", "")

            program_name = file.split(".")[0].upper()
            summary_map[program_name] = summary

    return summary_map


# =============================
# MAIN
# =============================
def main():

    with open("kb.json", encoding="utf-8") as f:
        data = json.load(f)

    # 🔹 BUILD SUMMARY MAP FIRST
    summary_map = build_summary_map(data)

    # 🔹 HANDLE SINGLE GRAPH FORMAT
    if isinstance(data, dict):
        print("Detected single graph format → converting")

        data = [{
            "program": "GLOBAL_GRAPH",
            "nodes": data.get("nodes", []),
            "relationships": data.get("relationships", [])
        }]

    elif not isinstance(data, list):
        print("Invalid kb.json format")
        return

    with driver.session() as session:

        for item in data:

            if not isinstance(item, dict):
                print("Skipping invalid item")
                continue

            if not item.get("nodes"):
                print("Skipping empty graph")
                continue

            print("Pushing:", item.get("program"))

            session.execute_write(create_graph, item, summary_map)

    driver.close()
    print("\n Data pushed to Neo4j successfully")


if __name__ == "__main__":
    main()