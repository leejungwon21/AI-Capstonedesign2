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
from src.schemas import EVENT_SCHEMA, TASK_SCHEMA, WORK_SCHEMA
from src.pipeline_context import (build_work_event_context, _msg_order, derive_strong_work_links, build_must_link_clusters)
from evaluation.evaluate_grouping import evaluate as evaluate_grouping







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

def hydrate_event_source_context(events, messages):
    """Restore non-semantic Slack source context after reusing saved Event output."""
    by_id = {m.get("id"): m for m in messages}
    for e in events:
        m = by_id.get(e.get("source_id"))
        if not m:
            continue
        e["source_channel"] = m.get("channel")
        e["source_timestamp"] = m.get("timestamp")
        e["source_thread_key"] = m.get("thread_key")










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
        hydrate_event_source_context(events, src["messages"])
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
