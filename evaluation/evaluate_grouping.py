"""Evaluate Event->Task and Task->Work grouping with pairwise P/R/F1."""
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


def source_by_event(data):
    return {e["event_id"]: e.get("source_id") for e in data.get("events", [])}


def sources_for_task(task, source_map):
    return {
        source_map[event_id]
        for event_id in task_event_ids(task)
        if event_id in source_map and source_map[event_id] is not None
    }


def align_pred_tasks(gold, pred):
    """Align generated Task IDs to Gold Task IDs by Slack source-message overlap."""
    gold_map = source_by_event(gold)
    pred_map = source_by_event(pred)
    candidates = []

    for pred_task in pred.get("tasks", []):
        pred_sources = sources_for_task(pred_task, pred_map)
        for gold_task in gold.get("tasks", []):
            gold_sources = sources_for_task(gold_task, gold_map)
            intersection = pred_sources & gold_sources
            union = pred_sources | gold_sources
            if not intersection or not union:
                continue
            candidates.append((
                len(intersection) / len(union),
                len(intersection),
                pred_task["task_id"],
                gold_task["task_id"],
            ))

    candidates.sort(reverse=True)
    mapping = {}
    used_gold = set()

    for _, _, pred_id, gold_id in candidates:
        if pred_id in mapping or gold_id in used_gold:
            continue
        mapping[pred_id] = gold_id
        used_gold.add(gold_id)

    return mapping


def mapped_work_members(work, mapping):
    return [mapping.get(task_id, "UNMAPPED:" + task_id) for task_id in work_task_ids(work)]


def evaluate(gold, pred):
    gold_task_pairs = cluster_pairs(gold.get("tasks", []), task_event_ids)
    pred_task_pairs = cluster_pairs(pred.get("tasks", []), task_event_ids)

    alignment = align_pred_tasks(gold, pred)
    gold_work_pairs = cluster_pairs(gold.get("works", []), work_task_ids)
    pred_work_pairs = cluster_pairs(
        pred.get("works", []),
        lambda work: mapped_work_members(work, alignment),
    )

    return {
        "event_to_task_pairwise": score(gold_task_pairs, pred_task_pairs),
        "task_to_work_pairwise": score(gold_work_pairs, pred_work_pairs),
        "task_id_alignment": alignment,
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
