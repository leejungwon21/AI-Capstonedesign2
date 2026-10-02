"""Run THREAD case: Slack -> Event -> Task -> Work -> Gold evaluation."""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.luna_api import call_structured
from evaluation.evaluate_grouping import evaluate as evaluate_grouping

EVENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["events"],
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source_id","subject","actor","related_people","action","recipient","event_type","status","time_scope","deadline","prerequisite","constraint","certainty","evidence"],
                "properties": {
                    "source_id": {"type": "string"},
                    "subject": {"type": ["string","null"]},
                    "actor": {"type": ["object","null"], "additionalProperties": False, "properties": {"slack_id":{"type":["string","null"]},"name":{"type":"string"}}, "required":["slack_id","name"]},
                    "related_people": {"type":"array","items":{"type":"object","additionalProperties":False,"required":["slack_id","name","role","certainty"],"properties":{"slack_id":{"type":["string","null"]},"name":{"type":"string"},"role":{"type":["string","null"]},"certainty":{"type":"string","enum":["confirmed","uncertain"]}}}},
                    "action": {"type": ["string","null"]},
                    "recipient": {"type": ["object","null"], "additionalProperties": False, "properties": {"slack_id":{"type":["string","null"]},"name":{"type":"string"}}, "required":["slack_id","name"]},
                    "event_type": {"type":"string","enum":["request","requirement","plan","progress","completion","status","question","decision"]},
                    "status": {"type":["string","null"]},
                    "time_scope": {"type":"string","enum":["past","current","future","unknown"]},
                    "deadline": {"type":"object","additionalProperties":False,"required":["text","at"],"properties":{"text":{"type":["string","null"]},"at":{"type":["string","null"]}}},
                    "prerequisite": {"type":["string","null"]},
                    "constraint": {"type":["string","null"]},
                    "certainty": {"type":"string","enum":["confirmed","uncertain"]},
                    "evidence": {"type":"string"}
                }
            }
        }
    }
}

TASK_SCHEMA = {
    "type":"object","additionalProperties":False,"required":["tasks"],
    "properties":{"tasks":{"type":"array","items":{
        "type":"object","additionalProperties":False,
        "required":["task_id","title","subject","status","status_history","deadline","next_action","participants","events","task_links","certainty"],
        "properties":{
            "task_id":{"type":["string","null"]},"title":{"type":"string"},"subject":{"type":["string","null"]},
            "status":{"type":"string","enum":["planned","in_progress","waiting","blocked","completed","unknown"]},
            "status_history":{"type":"array","items":{}},
            "deadline":{"type":"object","additionalProperties":False,"required":["text","at"],"properties":{"text":{"type":["string","null"]},"at":{"type":["string","null"]}}},
            "next_action":{"type":["string","null"]},
            "participants":{"type":"array","items":{"type":"object","additionalProperties":False,"required":["slack_id","name","roles","event_ids"],"properties":{"slack_id":{"type":["string","null"]},"name":{"type":"string"},"roles":{"type":"array","items":{"type":"string"}},"event_ids":{"type":"array","items":{"type":"string"}}}}},
            "events":{"type":"array","items":{"type":"object","additionalProperties":False,"required":["event_id","role"],"properties":{"event_id":{"type":"string"},"role":{"type":"string"}}}},
            "task_links":{"type":"array","items":{}},
            "certainty":{"type":"string","enum":["confirmed","uncertain"]}
        }
    }}}
}

WORK_SCHEMA = {
    "type":"object","additionalProperties":False,"required":["works"],
    "properties":{"works":{"type":"array","items":{
        "type":"object","additionalProperties":False,
        "required":["work_id","title","tasks","certainty"],
        "properties":{
            "work_id":{"type":["string","null"]},"title":{"type":"string"},
            "tasks":{"type":"array","items":{"type":"object","additionalProperties":False,"required":["task_id","role"],"properties":{"task_id":{"type":"string"},"role":{"type":"string"}}}},
            "certainty":{"type":"string","enum":["confirmed","uncertain"]}
        }
    }}}
}

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def prompt(name):
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")

def safe_text(text):
    return re.sub(r"https://demo\.bmw-handoff\.local/WORK-[^\s]+", "[LINK]", text)

def assign_event_ids(events):
    seen = {}
    for e in events:
        sid = e["source_id"]
        seen[sid] = seen.get(sid, 0) + 1
        n = sid.split("-")[-1]
        e["event_id"] = f"EVENT-{n}-{seen[sid]:02d}"

def assign_ids(items, key, prefix):
    for i, x in enumerate(items, 1):
        if not x.get(key):
            x[key] = f"{prefix}-{i:05d}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="THREAD-00005")
    args = ap.parse_args()

    case_path = ROOT / "evaluation" / "cases" / f"{args.case}.json"
    gold_path = ROOT / "evaluation" / "cases" / f"{args.case}.gold.json"
    out_dir = ROOT / "evaluation" / "predictions"
    out_dir.mkdir(parents=True, exist_ok=True)

    src = read_json(case_path)
    people = src["people"]
    events = []

    for m in src["messages"]:
        payload = {
            "message": {
                "source_id": m["id"],
                "slack_id": m["author_id"],
                "timestamp": m["timestamp"],
                "channel": m["channel"],
                "text": safe_text(m["text"])
            },
            "people": people
        }
        result, _ = call_structured(system_prompt=prompt("event_extraction.md"), user_payload=payload, json_schema=EVENT_SCHEMA)
        extracted = result["events"]
        for e in extracted:
            e["source_id"] = m["id"]
        events.extend(extracted)
        print(f'{m["id"]}: {len(extracted)} event(s)')

    assign_event_ids(events)

    task_result, _ = call_structured(
        system_prompt=prompt("event_to_task.md"),
        user_payload={"new_events": events, "existing_tasks": [], "people": people},
        json_schema=TASK_SCHEMA,
        max_output_tokens=8000
    )
    tasks = task_result["tasks"]
    assign_ids(tasks, "task_id", "PTASK")

    work_result, _ = call_structured(
        system_prompt=prompt("task_to_work.md"),
        user_payload={"tasks": tasks, "existing_works": []},
        json_schema=WORK_SCHEMA,
        max_output_tokens=5000
    )
    works = work_result["works"]
    assign_ids(works, "work_id", "PWORK")

    pred = {"case_id": args.case, "events": events, "tasks": tasks, "works": works}
    pred_path = out_dir / f"{args.case}.prediction.json"
    pred_path.write_text(json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {pred_path}")
    print(f"Counts: events={len(events)}, tasks={len(tasks)}, works={len(works)}")

    if gold_path.exists():
        gold = read_json(gold_path)
        metrics = evaluate_grouping(gold, pred)
        metrics["event_count"] = {"gold": len(gold.get("events", [])), "pred": len(events)}
        metrics_path = out_dir / f"{args.case}.metrics.json"
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        print(f"Saved: {metrics_path}")

if __name__ == "__main__":
    main()
