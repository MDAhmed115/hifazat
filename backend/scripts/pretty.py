#!/usr/bin/env python3
# backend/scripts/pretty.py — compact printers for curl JSON output.
# Usage: curl ... | python3 scripts/pretty.py [queue|audit|count|raw]
import json
import sys

mode = sys.argv[1] if len(sys.argv) > 1 else "raw"
data = json.load(sys.stdin)

if mode == "queue":
    for c in data:
        ld = c.get("latest_decision")
        conf = ld["confidence"] if ld else None
        print(f"case {c['id']}: priority={c['priority']} status={c['status']} conf={conf}")
elif mode == "audit":
    for r in data:
        print(f"{r['id']:3} {r['actor_role']:8} {r['action']:22} {r['entity']}#{r['entity_id']}")
elif mode == "count":
    print(f"{len(data)} case(s):", [c["id"] for c in data])
else:
    print(json.dumps(data, indent=2, ensure_ascii=False))
