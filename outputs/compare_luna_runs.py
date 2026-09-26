"""Compare two GPT-5.6 Luna event extraction runs.

Usage:
python outputs/compare_luna_runs.py isolated.json context.json
"""

import argparse
import json
from pathlib import Path


CORE_FIELDS = [
    "subject",
    "actor",
    "action",
    "recipient",
    "event_type",
    "status",
    "time_scope",
    "deadline_text",
    "prerequisite",
    "constraint",
    "certainty",
]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def flatten(run):
    rows = {}

    for message in run.get("results", []):
        for event in message.get("events", []):
            key = (
                event.get("source_id"),
                event.get("candidate_id"),
                event.get("evidence"),
                event.get("action"),
            )
            rows[key] = event

    return rows


def summarize(run):
    messages = run.get("results", [])
    events = [e for m in messages for e in m.get("events", [])]
    invalid = [e for e in events if e.get("validation_errors")]
    corrected = [e for e in events if e.get("rule_corrections")]

    return {
        "messages": len(messages),
        "events": len(events),
        "invalid_events": len(invalid),
        "rule_corrected_events": len(corrected),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("isolated")
    parser.add_argument("context")
    args = parser.parse_args()

    isolated = load(args.isolated)
    context = load(args.context)

    left = flatten(isolated)
    right = flatten(context)

    all_keys = sorted(set(left) | set(right))

    print("=== RUN SUMMARY ===")
    print("isolated:", json.dumps(summarize(isolated), ensure_ascii=False))
    print("context :", json.dumps(summarize(context), ensure_ascii=False))
    print()

    changed = 0

    for key in all_keys:
        a = left.get(key)
        b = right.get(key)

        if a is None:
            changed += 1
            print("[ONLY CONTEXT]", key[:3])
            print(json.dumps({f: b.get(f) for f in CORE_FIELDS}, ensure_ascii=False, indent=2))
            print()
            continue

        if b is None:
            changed += 1
            print("[ONLY ISOLATED]", key[:3])
            print(json.dumps({f: a.get(f) for f in CORE_FIELDS}, ensure_ascii=False, indent=2))
            print()
            continue

        diffs = {
            field: {"isolated": a.get(field), "context": b.get(field)}
            for field in CORE_FIELDS
            if a.get(field) != b.get(field)
        }

        if diffs:
            changed += 1
            print("[DIFF]", key[:3])
            print(json.dumps(diffs, ensure_ascii=False, indent=2))
            print()

    print(f"Changed/unique event rows: {changed}")


if __name__ == "__main__":
    main()
