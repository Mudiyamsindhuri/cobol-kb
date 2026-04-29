import json
import time

KB_FILE = "kb.json"

def load_kb():
    while True:
        try:
            with open(KB_FILE, "r") as f:
                return json.load(f)
        except:
            print("Waiting for KB file...")
            time.sleep(1)

def search_kb(question, kb):
    question = question.lower()
    results = []

    for item in kb:
        text = (
            str(item.get("program_name", "")) + " " +
            str(item.get("purpose", "")) + " " +
            str(item.get("business_logic", ""))
        ).lower()

        if question in text:
            results.append(item)

    return results


def main():
    print("COBOL KB Query System Ready")

    while True:
        query = input("\nAsk something (type 'exit'): ")

        if query.lower() == "exit":
            break

        kb = load_kb()

        results = search_kb(query, kb)

        if not results:
            print("No match found")
        else:
            for r in results[:3]:
                print("\n--- RESULT ---")
                print("Program:", r.get("program_name"))
                print("Purpose:", r.get("purpose"))
                print("Logic:", r.get("business_logic"))


if __name__ == "__main__":
    main()