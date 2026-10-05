"""Run THREAD case: Slack -> Event -> Task -> Work -> Gold evaluation."""
import argparse
import json
import re
import sys
import statistics
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
                "required": ["source_id","subject","actor","related_people","action","recipient","event_type","status","time_scope","deadline","prerequisite","constraint","note","certainty","evidence"],
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
                    "note": {"type":["string","null"]},
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
                "note": e.get("note"),
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

def _msg_order(source_id):
    if not source_id:
        return -1
    m = re.search(r"(\d+)$", source_id)
    return int(m.group(1)) if m else -1

def derive_strong_work_links(tasks, event_context):
    """Derive only high-confidence Task links from existing Event evidence.

    This is deterministic and uses no extra LLM/API call. The goal is to
    stabilize Work grouping with explicit handoff/prerequisite evidence.
    """
    task_by_id = {t["task_id"]: t for t in tasks}
    ctx_by_id = {c["task_id"]: c for c in event_context}
    titles = {
        t["task_id"]: (t.get("title") or "").strip()
        for t in tasks
        if (t.get("title") or "").strip()
    }

    task_actor_ids = {}
    task_first_order = {}
    for task_id, ctx in ctx_by_id.items():
        actors = set()
        orders = []
        for e in ctx.get("events", []):
            actor = e.get("actor") or {}
            if actor.get("slack_id"):
                actors.add(actor["slack_id"])
            order = _msg_order(e.get("source_id"))
            if order >= 0:
                orders.append(order)
        task_actor_ids[task_id] = actors
        task_first_order[task_id] = min(orders) if orders else 10**9

    links = []
    seen = set()

    def add_link(source, target, reason, evidence):
        if not source or not target or source == target:
            return
        key = (source, target, reason, evidence)
        if key in seen:
            return
        seen.add(key)
        links.append({
            "source_task_id": source,
            "target_task_id": target,
            "reason": reason,
            "evidence": evidence
        })

    # 1) Exact Task-title reference in prerequisite/evidence/next_action.
    for source_id, ctx in ctx_by_id.items():
        texts = []
        next_action = (task_by_id[source_id].get("next_action") or "").strip()
        if next_action:
            texts.append(("next_action", next_action))
        for e in ctx.get("events", []):
            for field in ("prerequisite", "evidence", "action"):
                value = (e.get(field) or "").strip()
                if value:
                    texts.append((field, value))
        for field, text in texts:
            for target_id, title in titles.items():
                if target_id != source_id and len(title) >= 4 and title in text:
                    # If current Task explicitly cites another Task title as a
                    # prerequisite/context, they are strongly linked.
                    add_link(target_id, source_id, f"explicit_{field}_task_reference", text)

    # 2) Explicit execution handoff only.
    # Generic delivery/reference is not enough for a deterministic must-link.
    strong_assignment_terms = ("다음 업무", "후속 업무", "후속 작업", "이어가", "이어서 진행", "정리본 기준으로 이어")
    generic_next_terms = ("다음 단계",)
    for source_id, ctx in ctx_by_id.items():
        for e in ctx.get("events", []):
            action = str(e.get("action") or "").strip()
            evidence = str(e.get("evidence") or "").strip()

            is_strong_assignment = any(term in action for term in strong_assignment_terms)
            is_generic_next = any(term in action for term in generic_next_terms)
            if not is_strong_assignment and not is_generic_next:
                continue

            recipient = e.get("recipient") or {}
            rid = recipient.get("slack_id")
            if not rid:
                continue

            event_order = _msg_order(e.get("source_id"))
            candidates = [
                target_id for target_id, actors in task_actor_ids.items()
                if target_id != source_id
                and rid in actors
                and task_first_order.get(target_id, 10**9) > event_order
            ]
            if not candidates:
                continue

            target_id = min(candidates, key=lambda x: task_first_order[x])

            if is_generic_next and not is_strong_assignment:
                source_text = " ".join([
                    str(task_by_id[source_id].get("title") or ""),
                    str(task_by_id[source_id].get("subject") or ""),
                ])
                target_text = " ".join([
                    str(task_by_id[target_id].get("title") or ""),
                    str(task_by_id[target_id].get("subject") or ""),
                ])
                source_tokens = {tok for tok in re.findall(r"[가-힣A-Za-z0-9]+", source_text) if len(tok) >= 2}
                target_tokens = {tok for tok in re.findall(r"[가-힣A-Za-z0-9]+", target_text) if len(tok) >= 2}
                if not (source_tokens & target_tokens):
                    continue

            add_link(
                source_id,
                target_id,
                "explicit_assignment_to_later_actor",
                evidence or action
            )

    return links

def build_must_link_clusters(tasks, links):
    """Union connected Tasks into deterministic must-link Work candidates."""
    parent = {t["task_id"]: t["task_id"] for t in tasks}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for link in links:
        a = link["source_task_id"]
        b = link["target_task_id"]
        if a in parent and b in parent:
            union(a, b)

    groups = {}
    for task_id in parent:
        groups.setdefault(find(task_id), []).append(task_id)

    return [
        sorted(group)
        for group in groups.values()
        if len(group) > 1
    ]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="THREAD-00005")
    ap.add_argument("--save-upstream", action="store_true",
                    help="Save Event+Task output for controlled Work experiments.")
    ap.add_argument("--reuse-upstream", action="store_true",
                    help="Reuse previously saved Event+Task output; skip Event/Task API calls.")
    ap.add_argument("--repeat", type=int, default=1,
                    help="Repeat only the Work stage N times on the same upstream and report mean/std.")
    args = ap.parse_args()
    if args.repeat < 1:
        raise ValueError("--repeat must be >= 1")

    case_path = ROOT / "evaluation" / "cases" / f"{args.case}.json"
    gold_path = ROOT / "evaluation" / "cases" / f"{args.case}.gold.json"
    out_dir = ROOT / "evaluation" / "predictions"
    out_dir.mkdir(parents=True, exist_ok=True)

    src = read_json(case_path)
    people = src["people"]
    upstream_path = out_dir / f"{args.case}.upstream.json"

    if args.reuse_upstream:
        if not upstream_path.exists():
            raise FileNotFoundError(
                f"Saved upstream not found: {upstream_path}. "
                "Run once with --save-upstream first."
            )
        upstream = read_json(upstream_path)
        events = upstream["events"]
        tasks = upstream["tasks"]
        print(f"Reused upstream: {upstream_path}")
        print(f"Upstream counts: events={len(events)}, tasks={len(tasks)}")
    else:
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
            result, _ = call_structured(
                system_prompt=prompt("event_extraction.md"),
                user_payload=payload,
                json_schema=EVENT_SCHEMA
            )
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

        if args.save_upstream:
            can_save = True
            if gold_path.exists():
                gold_for_check = read_json(gold_path)
                expected_tasks = len(gold_for_check.get("tasks", []))
                if len(tasks) != expected_tasks:
                    can_save = False
                    print(
                        f"Upstream NOT saved: predicted tasks={len(tasks)}, "
                        f"gold tasks={expected_tasks}. Run again until the controlled "
                        "upstream has the expected Task count."
                    )
            if can_save:
                upstream_path.write_text(
                    json.dumps(
                        {"case_id": args.case, "events": events, "tasks": tasks},
                        ensure_ascii=False,
                        indent=2
                    ),
                    encoding="utf-8"
                )
                print(f"Saved upstream: {upstream_path}")

    work_event_context = build_work_event_context(tasks, events)
    derived_work_links = derive_strong_work_links(tasks, work_event_context)
    must_link_clusters = build_must_link_clusters(tasks, derived_work_links)
    print(f"Derived strong Work links: {len(derived_work_links)}")
    print(f"Must-link clusters: {must_link_clusters}")

    gold = read_json(gold_path) if gold_path.exists() else None
    run_results = []

    for run_idx in range(1, args.repeat + 1):
        work_result, _ = call_structured(
            system_prompt=prompt("task_to_work.md"),
            user_payload={
                "tasks": tasks,
                "event_context": work_event_context,
                "derived_strong_links": derived_work_links,
                "must_link_clusters": must_link_clusters,
                "existing_works": []
            },
            json_schema=WORK_SCHEMA,
            max_output_tokens=5000
        )
        works = work_result["works"]
        assign_ids(works, "work_id", "PWORK")

        pred = {
            "case_id": args.case,
            "reused_upstream": args.reuse_upstream,
            "events": events,
            "tasks": tasks,
            "derived_strong_links": derived_work_links,
            "must_link_clusters": must_link_clusters,
            "works": works
        }

        metrics = evaluate_grouping(gold, pred) if gold else None
        if metrics is not None:
            metrics["event_count"] = {"gold": len(gold.get("events", [])), "pred": len(events)}
        run_results.append({"run": run_idx, "prediction": pred, "metrics": metrics})
        if metrics is not None:
            wf1 = metrics["task_to_work_pairwise"]["f1"]
            print(f"Run {run_idx}/{args.repeat}: works={len(works)}, work_f1={wf1:.4f}")
        else:
            print(f"Run {run_idx}/{args.repeat}: works={len(works)}")

    # Save only the final prediction for inspection, not every repeated run.
    pred = run_results[-1]["prediction"]
    works = pred["works"]
    pred_path = out_dir / f"{args.case}.prediction.json"
    pred_path.write_text(json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {pred_path}")
    print(f"Counts: events={len(events)}, tasks={len(tasks)}, works={len(works)}")

    if gold is not None:
        metrics = run_results[-1]["metrics"]
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

        work_f1_values = [
            x["metrics"]["task_to_work_pairwise"]["f1"]
            for x in run_results if x["metrics"] is not None
        ]
        work_counts = [len(x["prediction"]["works"]) for x in run_results]
        repeat_summary = {
            "runs": args.repeat,
            "work_f1_mean": statistics.mean(work_f1_values),
            "work_f1_std": statistics.pstdev(work_f1_values) if len(work_f1_values) > 1 else 0.0,
            "work_f1_values": work_f1_values,
            "work_count_values": work_counts
        }

        record = {
            "run_at_utc": datetime.now(timezone.utc).isoformat(),
            "case_id": args.case,
            "model": "gpt-6-luna",
            "experiment": {
                "work_input": "tasks_plus_event_context_plus_deterministic_links",
                "reuse_upstream": args.reuse_upstream,
                "repeat": args.repeat
            },
            "scores": {
                "event_to_task_pairwise": metrics["event_to_task_pairwise"],
                "task_to_work_pairwise_last_run": metrics["task_to_work_pairwise"],
                "task_to_work_repeat_summary": repeat_summary
            },
            "counts": {
                **metrics["counts"],
                "gold_events": gold_events,
                "pred_events": pred_events
            },
            "issues": issues
        }

        history_path = ROOT / "evaluation" / "experiment_history.jsonl"
        previous = None
        if history_path.exists():
            lines = [line for line in history_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                previous = json.loads(lines[-1])

        meaningful = previous is None
        reasons = []
        if previous is not None:
            prev_exp = previous.get("experiment", {})
            prev_scores = previous.get("scores", {})
            prev_counts = previous.get("counts", {})
            prev_summary = prev_scores.get("task_to_work_repeat_summary", {})
            prev_mean = prev_summary.get(
                "work_f1_mean",
                prev_scores.get("task_to_work_pairwise", {}).get("f1",
                prev_scores.get("task_to_work_pairwise_last_run", {}).get("f1"))
            )
            cur_mean = repeat_summary["work_f1_mean"]

            if prev_exp.get("work_input") != record["experiment"]["work_input"]:
                meaningful = True
                reasons.append("work input changed")
            if prev_counts.get("pred_tasks") != record["counts"]["pred_tasks"]:
                meaningful = True
                reasons.append("Task count changed")
            if prev_counts.get("pred_works") != record["counts"]["pred_works"]:
                meaningful = True
                reasons.append("Work count changed")
            if prev_mean is None or abs(cur_mean - prev_mean) >= 0.05:
                meaningful = True
                reasons.append("Work F1 mean changed by >= 0.05")
            prev_issue_types = {x.get("type") for x in previous.get("issues", [])}
            cur_issue_types = {x.get("type") for x in issues}
            if prev_issue_types != cur_issue_types:
                meaningful = True
                reasons.append("issue types changed")

        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        print("\nRepeat summary:")
        print(json.dumps(repeat_summary, ensure_ascii=False, indent=2))
        print("\nIssues:")
        if issues:
            for issue in issues:
                print(f"- {issue['detail']}")
        else:
            print("- 감지된 주요 문제 없음")
        print(f"Saved: {metrics_path}")

        if meaningful:
            record["change_reasons"] = reasons or ["first recorded experiment"]
            with history_path.open("a", encoding="utf-8") as hf:
                hf.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"Logged meaningful change: {history_path}")
        else:
            print("Not logged: no meaningful process/result change.")

if __name__ == "__main__":
    main()
