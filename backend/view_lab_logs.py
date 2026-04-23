import sys
import os
import json

def view_logs(sid="default"):
    path = f"logs/lab/{sid}_lab.jsonl"
    if not os.path.exists(path):
        print(f"No logs found for session: {sid}")
        return

    print(f"\n--- SESSION LAB LOGS: {sid} ---")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            print(f"\n[{data['timestamp']}]")
            print(f"USER: {data['input']}")
            print(f"EXTRACTED: {data['extracted']}")
            print(f"AI: {data['response']}")
            if data['audit']:
                tax = data['audit']['new_regime']['total_tax']
                print(f"AUDIT TAX (NEW): ₹{tax:,.0f}")
    print("\n--- END OF LOGS ---")

if __name__ == "__main__":
    sid = sys.argv[1] if len(sys.argv) > 1 else "default"
    view_logs(sid)
