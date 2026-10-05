"""Run a global multi-thread case: mixed Slack messages -> Event -> Task -> Work -> merged Gold evaluation.

Unlike run_thread_case.py, this runner deliberately mixes multiple source cases before
Task integration. Component case IDs are evaluator-only and are never sent to the LLM.
"""
import argparse
from collections import Counter
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.luna_api import call_structured
from evaluation.evaluate_grouping import evaluate as evaluate_grouping
from evaluation.run_thread_case import (
    EVENT_SCHEMA,
    TASK_SCHEMA,
    WORK_SCHEMA,
    assign_event_ids,
    assign_ids,
    build_must_link_clusters,
    build_work_event_context,
    derive_strong_work_links,
    hydrate_event_source_context,
    prompt,
    read_json,
    safe_text,
)


def merge_people(sources):
    by_id = {}
    for src in sources:
        for person in src.get("people", []):
            key = person.get("slack_id") or person.get("id") or person.get("name")
            if key is not None:
                by_id[key] = person
    return list(by_id.values())


def merge_gold(case_ids):
    merged = {"case_id": None, "events": [], "tasks": [], "works": [], "gold_scope": None}
    for case_id in case_ids:
        gold_path = ROOT / "evaluation" / "cases" / f"{case_id}.gold.json"
        gold = read_json(gold_path)
        merged["events"].extend(gold.get("events", []))
        merged["tasks"].extend(gold.get("tasks", []))
        merged["works"].extend(gold.get("works", []))
        scope = gold.get("gold_scope")
        if merged["gold_scope"] is None:
            merged["gold_scope"] = scope
        elif scope != merged["gold_scope"]:
            merged["gold_scope"] = "mixed"
    return merged


def issue_list(gold, events, tasks, works, metrics):
    issues = []
    ge, pe = len(gold.get("events", [])), len(events)
    gt, pt = len(gold.get("tasks", [])), len(tasks)
    gw, pw = len(gold.get("works", [])), len(works)

    if gold.get("gold_scope") != "grouping_boundary_gold":
        if pe > ge:
            issues.append({"type": "event_over_extraction", "detail": f"Event 과추출: Gold {ge}, Pred {pe} (+{pe-ge})"})
        elif pe < ge:
            issues.append({"type": "event_under_extraction", "detail": f"Event 누락: Gold {ge}, Pred {pe} (-{ge-pe})"})

    if pt != gt:
        issues.append({"type": "task_count_mismatch", "detail": f"Task 개수 불일치: Gold {gt}, Pred {pt}"})
    if pw != gw:
        issues.append({"type": "work_count_mismatch", "detail": f"Work 개수 불일치: Gold {gw}, Pred {pw}"})

    task_score = metrics["source_to_task_pairwise"]
    if task_score["f1"] < 1.0:
        issues.append({
            "type": "source_to_task_mismatch",
            "detail": (
                f"Source→Task pairwise F1={task_score['f1']:.4f} "
                f"(P={task_score['precision']:.4f}, R={task_score['recall']:.4f}): "
                "메시지 기준 Task 경계 불일치"
            )
        })

    work_score = metrics["task_to_work_pairwise"]
    if work_score["f1"] < 1.0:
        issues.append({
            "type": "task_to_work_mismatch",
            "detail": f"Task→Work pairwise F1={work_score['f1']:.4f}: global Work 경계 불일치"
        })
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="GLOBAL-00001")
    ap.add_argument("--save-upstream", action="store_true")
    ap.add_argument("--reuse-upstream", action="store_true")
    ap.add_argument("--reuse-events", action="store_true")
    ap.add_argument("--repeat", type=int, default=1)
    args = ap.parse_args()
    if args.repeat < 1:
        raise ValueError("--repeat must be >= 1")

    manifest_path = ROOT / "evaluation" / "global_cases" / f"{args.case}.json"
    manifest = read_json(manifest_path)
    case_ids = manifest["component_cases"]

    sources = []
    all_messages = []
    for case_id in case_ids:
        src = read_json(ROOT / "evaluation" / "cases" / f"{case_id}.json")
        sources.append(src)
        for m in src.get("messages", []):
            item = dict(m)
            # evaluator/debug only; never included in LLM payload
            item["_origin_case"] = case_id
            all_messages.append(item)

    all_messages.sort(key=lambda x: (x.get("timestamp") or "", x.get("id") or ""))
    people = merge_people(sources)
    gold = merge_gold(case_ids)
    gold["case_id"] = args.case

    out_dir = ROOT / "evaluation" / "predictions"
    out_dir.mkdir(parents=True, exist_ok=True)
    upstream_path = out_dir / f"{args.case}.upstream.json"

    print(f"Global case: {args.case}")
    print(f"Components: {', '.join(case_ids)}")
    print(f"Mixed messages: {len(all_messages)}")
    print("Leakage control: component/thread case IDs are NOT sent to Event→Task or Task→Work.")

    if args.reuse_upstream:
        if not upstream_path.exists():
            raise FileNotFoundError(f"Saved upstream not found: {upstream_path}")
        upstream = read_json(upstream_path)
        events = upstream["events"]
        tasks = upstream["tasks"]
        hydrate_event_source_context(events, all_messages)
        print(f"Reused upstream: {upstream_path}")
    else:
        if args.reuse_events:
            if not upstream_path.exists():
                raise FileNotFoundError(f"Saved upstream not found: {upstream_path}")
            upstream = read_json(upstream_path)
            events = upstream["events"]
            hydrate_event_source_context(events, all_messages)
            print(f"Reused events only: {upstream_path}")
        else:
            events = []
            for m in all_messages:
                payload = {
                    "message": {
                        "source_id": m["id"],
                        "slack_id": m["author_id"],
                        "timestamp": m["timestamp"],
                        "channel": m["channel"],
                        "text": safe_text(m["text"]),
                    },
                    "people": people,
                }
                result, _ = call_structured(
                    system_prompt=prompt("event_extraction.md"),
                    user_payload=payload,
                    json_schema=EVENT_SCHEMA,
                )
                extracted = result["events"]
                for e in extracted:
                    e["source_id"] = m["id"]
                    e["source_channel"] = m.get("channel")
                    e["source_timestamp"] = m.get("timestamp")
                    e["source_thread_key"] = m.get("thread_key")
                events.extend(extracted)
                print(f'{m["id"]}: {len(extracted)} event(s)')

            assign_event_ids(events)

        task_result, _ = call_structured(
            system_prompt=prompt("event_to_task.md"),
            user_payload={"new_events": events, "existing_tasks": [], "people": people},
            json_schema=TASK_SCHEMA,
            max_output_tokens=16000,
        )
        tasks = task_result["tasks"]
        assign_ids(tasks, "task_id", "PTASK")

        if args.save_upstream:
            expected_tasks = len(gold.get("tasks", []))
            upstream_path.write_text(
                json.dumps({"case_id": args.case, "events": events, "tasks": tasks}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Saved upstream: {upstream_path}")
            if len(tasks) != expected_tasks:
                print(f"Warning: saved upstream has predicted tasks={len(tasks)}, gold tasks={expected_tasks}.")

    event_context = build_work_event_context(tasks, events)
    derived_links = derive_strong_work_links(tasks, event_context)
    clusters = build_must_link_clusters(tasks, derived_links)
    print(f"Derived strong Work links: {len(derived_links)}")
    print(f"Must-link clusters: {clusters}")

    runs = []
    for idx in range(1, args.repeat + 1):
        work_result, _ = call_structured(
            system_prompt=prompt("task_to_work.md"),
            user_payload={
                "tasks": tasks,
                "event_context": event_context,
                "derived_strong_links": derived_links,
                "must_link_clusters": clusters,
                "existing_works": [],
            },
            json_schema=WORK_SCHEMA,
            max_output_tokens=8000,
        )
        works = work_result["works"]
        assign_ids(works, "work_id", "PWORK")
        pred = {
            "case_id": args.case,
            "component_cases_hidden_from_llm": case_ids,
            "events": events,
            "tasks": tasks,
            "derived_strong_links": derived_links,
            "must_link_clusters": clusters,
            "works": works,
        }
        metrics = evaluate_grouping(gold, pred)
        if gold.get("gold_scope") == "grouping_boundary_gold":
            metrics["event_to_task_pairwise"] = {
                "scored": False,
                "reason": "Gold Events are source anchors for grouping boundaries, not full Event-fact annotations."
            }
            metrics["event_count"] = {
                "gold_anchors": len(gold["events"]),
                "pred": len(events),
                "scored": False
            }
        else:
            metrics["event_count"] = {"gold": len(gold["events"]), "pred": len(events), "scored": True}
        runs.append({"prediction": pred, "metrics": metrics})
        print(f"Run {idx}/{args.repeat}: tasks={len(tasks)}, works={len(works)}, work_f1={metrics['task_to_work_pairwise']['f1']:.4f}")

    pred = runs[-1]["prediction"]
    metrics = runs[-1]["metrics"]
    works = pred["works"]

    pred_path = out_dir / f"{args.case}.prediction.json"
    metrics_path = out_dir / f"{args.case}.metrics.json"
    pred_path.write_text(json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    work_f1_values = [x["metrics"]["task_to_work_pairwise"]["f1"] for x in runs]
    fp_counter = Counter()
    fn_counter = Counter()
    for run in runs:
        wm = run["metrics"]["task_to_work_pairwise"]
        for pair in wm.get("false_positive_pairs", []):
            fp_counter[tuple(pair)] += 1
        for pair in wm.get("false_negative_pairs", []):
            fn_counter[tuple(pair)] += 1

    def recurring_pairs(counter):
        return [
            {"pair": list(pair), "count": count, "rate": count / args.repeat}
            for pair, count in sorted(counter.items(), key=lambda x: (-x[1], x[0]))
            if count >= 2
        ]

    repeat_summary = {
        "runs": args.repeat,
        "work_f1_mean": statistics.mean(work_f1_values),
        "work_f1_std": statistics.pstdev(work_f1_values) if len(work_f1_values) > 1 else 0.0,
        "work_f1_values": work_f1_values,
        "work_count_values": [len(x["prediction"]["works"]) for x in runs],
        "recurring_false_positive_pairs": recurring_pairs(fp_counter),
        "recurring_false_negative_pairs": recurring_pairs(fn_counter),
    }

    repeat_path = out_dir / f"{args.case}.repeat.json"
    repeat_path.write_text(
        json.dumps(
            {
                "case_id": args.case,
                "repeat_summary": repeat_summary,
                "runs": [
                    {
                        "run": idx,
                        "works": run["prediction"]["works"],
                        "task_to_work_pairwise": run["metrics"]["task_to_work_pairwise"],
                    }
                    for idx, run in enumerate(runs, start=1)
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    issues = issue_list(gold, events, tasks, works, metrics)

    print(f"Saved: {pred_path}")
    print(f"Counts: events={len(events)}, tasks={len(tasks)}, works={len(works)}")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print("\nRepeat summary:")
    print(json.dumps(repeat_summary, ensure_ascii=False, indent=2))
    print(f"Saved repeat details: {repeat_path}")
    print("\nIssues:")
    if issues:
        for issue in issues:
            print(f"- {issue['detail']}")
    else:
        print("- 감지된 주요 문제 없음")

    record = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_id": args.case,
        "model": "gpt-6-luna",
        "experiment": {
            "type": "global_multi_thread_grouping",
            "component_cases": case_ids,
            "component_case_ids_exposed_to_llm": False,
            "repeat": args.repeat,
        },
        "scores": {
            "event_to_task_pairwise_legacy": metrics["event_to_task_pairwise"],
            "source_to_task_pairwise": metrics["source_to_task_pairwise"],
            "source_task_coverage": metrics["source_task_coverage"],
            "task_to_work_pairwise_last_run": metrics["task_to_work_pairwise"],
            "task_to_work_repeat_summary": repeat_summary,
        },
        "counts": {
            **metrics["counts"],
            "gold_events": len(gold["events"]),
            "pred_events": len(events),
        },
        "issues": issues,
        "diagnosis": (
            "첫 global grouping 기준선. 여러 thread의 Event를 하나의 Task 통합 입력으로 섞어 "
            "thread 경계 없이 Task/Work 경계를 찾는 능력을 측정한다."
        ),
    }
    history_path = ROOT / "evaluation" / "experiment_history.jsonl"
    with history_path.open("a", encoding="utf-8") as hf:
        hf.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Logged global experiment: {history_path}")


if __name__ == "__main__":
    main()
