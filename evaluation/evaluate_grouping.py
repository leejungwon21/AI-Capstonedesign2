"""Evaluate Event->Task and Task->Work grouping with pairwise P/R/F1.

IDs are not used as the only correctness signal. Two predicted clusters can be
matched correctly even if their generated numeric IDs differ.
"""
import argparse
import itertools
import json


def f1(p, r):
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def pairs(items):
    return {tuple(sorted(x)) for x in itertools.combinations(sorted(set(items)), 2)}


def task_event_ids(task):
    if "event_ids" in task:
        return task["event_ids"]
    return [x["event_id"] for x in task.get("events", [])]


def work_task_ids(work):
    if "task_ids" in work:
        return work["task_ids"]
    return [x["task_id"] for x in work.get("tasks", [])]


def cluster_pairs(clusters, member_fn):
    out = set()
    for cluster in clusters:
        out |= pairs(member_fn(cluster))
    return out


def score(gold_pairs, pred_pairs):
    tp = len(gold_pairs & pred_pairs)
    fp = len(pred_pairs - gold_pairs)
    fn = len(gold_pairs - pred_pairs)
    precision = 0.0 if tp + fp == 0 else tp / (tp + fp)
    recall = 0.0 if tp + fn == 0 else tp / (tp + fn)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1(precision, recall),
    }


def evaluate(gold, pred):
    gold_task_pairs = cluster_pairs(gold.get("tasks", []), task_event_ids)
    pred_task_pairs = cluster_pairs(pred.get("tasks", []), task_event_ids)
    gold_work_pairs = cluster_pairs(gold.get("works", []), work_task_ids)
    pred_work_pairs = cluster_pairs(pred.get("works", []), work_task_ids)

    return {
        "event_to_task_pairwise": score(gold_task_pairs, pred_task_pairs),
        "task_to_work_pairwise": score(gold_work_pairs, pred_work_pairs),
        "counts": {
            "gold_tasks": len(gold.get("tasks", [])),
            "pred_tasks": len(pred.get("tasks", [])),
            "gold_works": len(gold.get("works", [])),
            "pred_works": len(pred.get("works", [])),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("gold")
    parser.add_argument("prediction")
    args = parser.parse_args()

    with open(args.gold, encoding="utf-8") as f:
        gold = json.load(f)
    with open(args.prediction, encoding="utf-8") as f:
        pred = json.load(f)

    print(json.dumps(evaluate(gold, pred), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
