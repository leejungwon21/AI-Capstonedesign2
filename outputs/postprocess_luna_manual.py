"""Post-process manually collected GPT-5.6 Luna Event JSON.

This is for the no-API experiment:
1) Run the isolated prompt in ChatGPT/Luna.
2) Save the returned JSON.
3) Apply deterministic Python guardrails from extract_events_general.py.

The raw evidence text is never rewritten.
"""

import argparse
import copy
import json
import re
from pathlib import Path

from extract_events_general import (
    apply_rules,
    detect_sentence_time_scope,
    get_participants,
    normalize_question_events,
    validate_event,
)


ROOT = Path(__file__).resolve().parent


def resolve_path(value):
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def source_record_for_block(block_name, block_data, records):
    events = block_data.get("events", [])

    source_id = None
    for event in events:
        if event.get("source_id"):
            source_id = event["source_id"]
            break

    if source_id:
        for record in records:
            if record.get("source_id") == source_id:
                return record

    if block_name.startswith("block_"):
        try:
            index = int(block_name.split("_", 1)[1]) - 1
        except (TypeError, ValueError):
            index = -1

        if 0 <= index < len(records):
            return records[index]

    raise ValueError(f"Cannot map {block_name} to a source record.")


def postprocess_event(raw_event, *, record, participants):
    event = copy.deepcopy(raw_event)
    source_id = record["source_id"]
    speaker = record["speaker_label"].strip()
    body = record["body"]

    evidence = event.get("evidence")
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError(f"{source_id}: event has no usable evidence.")

    # Hard evidence check: the LLM evidence must be a verbatim substring.
    evidence_in_source = evidence in body

    # Manual isolated experiment intentionally does not use the other
    # participant as semantic context. Task integration can resolve that later.
    partner = None

    normalized = normalize_question_events([event], evidence)
    if not normalized:
        return None

    event = apply_rules(
        event=normalized[0],
        speaker=speaker,
        partner=partner,
        participants=participants,
        evidence=evidence,
        context_time_scope=detect_sentence_time_scope(evidence),
    )

    errors = validate_event(event)
    if not evidence_in_source:
        errors.append("evidence_not_verbatim_in_source")

    return {
        "source_id": source_id,
        "speaker": speaker,
        "evidence": evidence,
        "subject": event.get("subject"),
        "actor": event.get("actor"),
        "related_people": event.get("related_people", []),
        "action": event.get("action"),
        "recipient": event.get("recipient"),
        "event_type": event.get("event_type"),
        "status": event.get("status"),
        "time_scope": event.get("time_scope"),
        "deadline_text": event.get("deadline_text"),
        "prerequisite": event.get("prerequisite"),
        "constraint": event.get("constraint"),
        "certainty": event.get("certainty"),
        "rule_corrections": event.get("rule_corrections", []),
        "validation_errors": errors,
    }


def link_intra_message_dependencies(events, body):
    """Add only dependencies directly supported by the same source message."""
    has_submission_plan = any(
        event.get("event_type") == "plan"
        and event.get("action") == "제출"
        for event in events
    )

    # Example: "승인되면 제가 제출하고 접수 여부까지 확인할게요"
    # The receipt check happens after the submission in the same sentence.
    if has_submission_plan and "제출하고" in body:
        for event in events:
            subject = event.get("subject") or ""
            action = event.get("action") or ""

            if (
                event.get("event_type") == "plan"
                and ("접수" in subject or "접수" in event.get("evidence", ""))
                and "확인" in action
                and not event.get("prerequisite")
            ):
                event["prerequisite"] = "제출 완료"
                event.setdefault("rule_corrections", []).append(
                    "receipt_check_requires_submission"
                )

    return events


def add_missing_uncertain_impact_event(events, *, record):
    """Recover a directly stated uncertain schedule-impact event if Luna omitted it."""
    body = record["body"]
    source_id = record["source_id"]
    speaker = record["speaker_label"].strip()

    already_has_impact = any(
        "차질" in (event.get("evidence") or "")
        for event in events
    )

    if already_has_impact:
        return events

    match = re.search(
        r"([^,\n]*(?:되면|된다면|할 경우)[^,\n]*차질[^,\n]*것 같[^,\n]*)",
        body,
    )

    if not match:
        return events

    evidence = match.group(1).strip()
    subject = (
        "캠페인 진행 일정"
        if "캠페인 진행 일정" in evidence
        else "업무 일정"
    )

    event = {
        "source_id": source_id,
        "speaker": speaker,
        "evidence": evidence,
        "subject": subject,
        "actor": None,
        "related_people": [],
        "action": None,
        "recipient": None,
        "event_type": "status",
        "status": "차질이 있을 가능성",
        "time_scope": "future",
        "deadline_text": None,
        "prerequisite": None,
        "constraint": None,
        "certainty": "uncertain",
        "rule_corrections": [
            "missing_uncertain_schedule_impact_added"
        ],
        "validation_errors": [],
    }

    event["validation_errors"] = validate_event(event)

    return [event] + events


def split_compound_plan_events(events):
    """Split clearly distinct sequential plan actions into atomic Events."""
    result = []

    for event in events:
        evidence = event.get("evidence") or ""
        action = event.get("action") or ""

        should_split = (
            event.get("event_type") == "plan"
            and "작성" in action
            and "전달" in action
            and (
                "작성해서" in evidence
                or "작성하여" in evidence
                or "작성 후" in evidence
            )
        )

        if not should_split:
            result.append(event)
            continue

        write_event = copy.deepcopy(event)
        send_event = copy.deepcopy(event)

        write_event["action"] = "작성"
        send_event["action"] = "전달"

        write_event.setdefault("rule_corrections", []).append(
            "compound_plan_split_write"
        )
        send_event.setdefault("rule_corrections", []).append(
            "compound_plan_split_send"
        )

        write_event["validation_errors"] = validate_event(write_event)
        send_event["validation_errors"] = validate_event(send_event)

        result.extend([write_event, send_event])

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        required=True,
        help="Manual Luna JSON, relative to outputs/ or absolute.",
    )
    parser.add_argument(
        "--source",
        default="approval-case-04/source.json",
        help="Source JSON, relative to outputs/ or absolute.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output path. Default: <input>-validated.json",
    )
    args = parser.parse_args()

    input_path = resolve_path(args.input)
    source_path = resolve_path(args.source)

    raw = load_json(input_path)
    source = load_json(source_path)
    records = source["records"]
    participants = get_participants(records)

    output_blocks = {}
    total_events = 0
    total_errors = 0
    total_corrections = 0

    for block_name, block_data in raw.items():
        if not isinstance(block_data, dict):
            continue

        record = source_record_for_block(block_name, block_data, records)
        processed = []

        for raw_event in block_data.get("events", []):
            event = postprocess_event(
                raw_event,
                record=record,
                participants=participants,
            )
            if event is None:
                continue

            processed.append(event)

        processed = link_intra_message_dependencies(
            processed,
            record["body"],
        )

        processed = add_missing_uncertain_impact_event(
            processed,
            record=record,
        )

        processed = split_compound_plan_events(
            processed
        )

        for index, event in enumerate(processed, start=1):
            event["event_id"] = (
                f"{record['source_id']}-E{index:02d}"
            )

        total_events += len(processed)
        total_errors += sum(
            len(event["validation_errors"])
            for event in processed
        )
        total_corrections += sum(
            len(event["rule_corrections"])
            for event in processed
        )

        output_blocks[block_name] = {
            "source_id": record["source_id"],
            "events": processed,
        }

    result = {
        "version": "manual-luna-isolated-postprocess-v1",
        "source_file": str(source_path),
        "input_file": str(input_path),
        "event_count": total_events,
        "validation_error_count": total_errors,
        "rule_correction_count": total_corrections,
        "blocks": output_blocks,
    }

    if args.output:
        output_path = resolve_path(args.output)
    else:
        output_path = input_path.with_name(
            input_path.stem + "-validated.json"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    print("events:", total_events)
    print("rule corrections:", total_corrections)
    print("validation errors:", total_errors)
    print("saved:", output_path)


if __name__ == "__main__":
    main()
