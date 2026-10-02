"""Run THREAD case: Slack -> Event -> Task -> Work -> Gold evaluation."""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
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
            "status_history":{"type":"array","items":{"type":"object","additionalProperties":False,"required":["from","to","changed_at"],"properties":{"from":{"type":["string","null"]},"to":{"type":["string","null"]},"changed_at":{"type":["string","null"]}}}},
            "deadline":{"type":"object","additionalProperties":False,"required":["text","at"],"properties":{"text":{"type":["string","null"]},"at":{"type":["string","null"]}}},
            "next_action":{"type":["string","null"]},
            "participants":{"type":"array","items":{"type":"object","additionalProperties":False,"required":["slack_id","name","roles","event_ids"],"properties":{"slack_id":{"type":["string","null"]},"name":{"type":"string"},"roles":{"type":"array","items":{"type":"string"}},"event_ids":{"type":"array","items":{"type":"string"}}}}},
            "events":{"type":"array","items":{"type":"object","additionalProperties":False,"required":["event_id","role"],"properties":{"event_id":{"type":"string"},"role":{"type":"string"}}}},
            "task_links":{"type":"array","items":{"type":"object","additionalProperties":False,"required":["task_id","relation"],"properties":{"task_id":{"type":["string","null"]},"relation":{"type":["string","null"]}}}},
            "certainty":{"type":"string","enum":["confirmed","uncertain"]}
        }
    }}}
}

TASK_RELATION_SCHEMA = {
    "type":"object","additionalProperties":False,"required":["relations"],
    "properties":{"relations":{"type":"array","items":{
        "type":"object","additionalProperties":False,
        "required":["source_task_id","target_task_id","relation","evidence","certainty"],
        "properties":{
            "source_task_id":{"type":"string"},
            "target_task_id":{"type":"string"},
            "relation":{"type":"string","enum":["handoff_to","depends_on","blocks","follows","shares_output"]},
            "evidence":{"type":"array","items":{"type":"string"}},
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

def build_work_event_context(tasks, events):
    """Preserve source-grounded Event context for Task -> Work integration."""
    event_map = {e["event_id"]: e for e in events}
    context = []

    for task in tasks:
        task_event_ids = [x["event_id"] for x in task.get("events", [])]
        task_events = []

        for event_id in task_event_ids:
            e = event_map.get(event_id)
            if not e:
                continue
            task_events.append({
                "event_id": event_id,
                "source_id": e.get("source_id"),
                "subject": e.get("subject"),
                "action": e.get("action"),
                "event_type": e.get("event_type"),
                "status": e.get("status"),
                "prerequisite": e.get("prerequisite"),
                "constraint": e.get("constraint"),
                "actor": e.get("actor"),
                "recipient": e.get("recipient"),
                "related_people": e.get("related_people", []),
                "deadline": e.get("deadline"),
                "evidence": e.get("evidence")
            })

        context.append({
            "task_id": task["task_id"],
            "title": task.get("title"),
            "next_action": task.get("next_action"),
            "events": task_events
        })

    return context

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

    work_event_context = build_work_event_context(tasks, events)

    relation_result, _ = call_structured(
        system_prompt=prompt("task_relations.md"),
        user_payload={
            "tasks": tasks,
            "event_context": work_event_context
        },
        json_schema=TASK_RELATION_SCHEMA,
        max_output_tokens=4000
    )
    task_relations = relation_result["relations"]

    work_result, _ = call_structured(
        system_prompt=prompt("task_to_work.md"),
        user_payload={
            "tasks": tasks,
            "event_context": work_event_context,
            "task_relations": task_relations,
            "existing_works": []
        },
        json_schema=WORK_SCHEMA,
        max_output_tokens=5000
    )
    works = work_result["works"]
    assign_ids(works, "work_id", "PWORK")

    pred = {"case_id": args.case, "events": events, "tasks": tasks, "task_relations": task_relations, "works": works}
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

        issues = []
        gold_events = len(gold.get("events", []))
        pred_events = len(events)
        if pred_events > gold_events:
            issues.append({
                "type": "event_over_extraction",
                "detail": f"Event 과추출: Gold {gold_events}, Pred {pred_events} (+{pred_events - gold_events})"
            })
        elif pred_events < gold_events:
            issues.append({
                "type": "event_under_extraction",
                "detail": f"Event 누락: Gold {gold_events}, Pred {pred_events} ({pred_events - gold_events})"
            })

        counts = metrics["counts"]
        if counts["pred_tasks"] != counts["gold_tasks"]:
            issues.append({
                "type": "task_count_mismatch",
                "detail": f"Task 개수 불일치: Gold {counts['gold_tasks']}, Pred {counts['pred_tasks']}"
            })

        if counts["pred_works"] > counts["gold_works"]:
            issues.append({
                "type": "work_over_split",
                "detail": f"Work 단위 통합 실패/과분리: Gold {counts['gold_works']}, Pred {counts['pred_works']}"
            })
        elif counts["pred_works"] < counts["gold_works"]:
            issues.append({
                "type": "work_over_merge",
                "detail": f"Work 과통합: Gold {counts['gold_works']}, Pred {counts['pred_works']}"
            })

        work_score = metrics["task_to_work_pairwise"]
        if work_score["f1"] == 0 and counts["gold_works"] > 0:
            issues.append({
                "type": "work_integration_failure",
                "detail": "Task→Work pairwise F1=0.0: Work 단위 통합에 실패"
            })

        task_score = metrics["event_to_task_pairwise"]
        if task_score["recall"] == 1.0 and task_score["precision"] < 1.0:
            issues.append({
                "type": "event_to_task_false_positives",
                "detail": f"Event→Task Recall=1.0, Precision={task_score['precision']:.4f}: 누락은 없지만 불필요한 pair가 발생"
            })

        record = {
            "run_at_utc": datetime.now(timezone.utc).isoformat(),
            "case_id": args.case,
            "model": "gpt-6-luna",
            "experiment": {
                "work_input": "tasks_plus_event_context_plus_task_relations"
            },
            "scores": {
                "event_to_task_pairwise": metrics["event_to_task_pairwise"],
                "task_to_work_pairwise": metrics["task_to_work_pairwise"]
            },
            "counts": {
                **metrics["counts"],
                "gold_events": gold_events,
                "pred_events": pred_events
            },
            "issues": issues
        }

        history_path = ROOT / "evaluation" / "experiment_history.jsonl"
        with history_path.open("a", encoding="utf-8") as hf:
            hf.write(json.dumps(record, ensure_ascii=False) + "\n")

        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        print("\nIssues:")
        if issues:
            for issue in issues:
                print(f"- {issue['detail']}")
        else:
            print("- 감지된 주요 문제 없음")
        print(f"Saved: {metrics_path}")
        print(f"Logged: {history_path}")

if __name__ == "__main__":
    main()
