"""Deterministic regression checks for Event guardrails.

These tests intentionally cover only rules that can be decided from the
current message/evidence without broader conversation reasoning.
"""

from extract_events_general import (
    apply_rules,
    normalize_question_events,
)
from postprocess_luna_manual import link_intra_message_dependencies


PARTICIPANTS = ["원이정", "홍길동"]


def corrected(event, evidence, speaker):
    normalized = normalize_question_events([dict(event)], evidence)
    assert normalized

    return apply_rules(
        event=normalized[0],
        speaker=speaker,
        partner=None,
        participants=PARTICIPANTS,
        evidence=evidence,
        context_time_scope=None,
    )


def test_deadline_does_not_invent_schedule():
    event = {
        "subject": "발주 요청서 제출",
        "actor": None,
        "related_people": [],
        "action": "제출",
        "recipient": None,
        "event_type": "status",
        "status": "오늘 오후 2시까지 제출할 예정",
        "time_scope": "future",
        "deadline_text": "오늘 오후 2시까지",
        "prerequisite": None,
        "constraint": None,
        "certainty": "confirmed",
    }

    result = corrected(
        event,
        "오늘 오후 2시까지 제출할 발주 요청서",
        "원이정",
    )

    assert result["event_type"] == "requirement"
    assert result["status"] is None
    assert result["actor"] is None
    assert result["deadline_text"] == "오늘 오후 2시까지"


def test_approver_role_uses_explicit_first_person_subject():
    event = {
        "subject": "이번 요청서",
        "actor": None,
        "related_people": [],
        "action": None,
        "recipient": None,
        "event_type": "status",
        "status": "홍길동이 승인자",
        "time_scope": "current",
        "deadline_text": None,
        "prerequisite": None,
        "constraint": None,
        "certainty": "confirmed",
    }

    result = corrected(
        event,
        "이번 요청서는 제가 승인자라서요",
        "홍길동",
    )

    assert result["event_type"] == "status"
    assert result["actor"] == "홍길동"
    assert result["status"] == "승인자"


def test_question_does_not_promote_hypothesis_to_prerequisite():
    event = {
        "subject": "ㅅ승인자 변경",
        "actor": None,
        "related_people": [],
        "action": "변경 가능 여부 확인",
        "recipient": None,
        "event_type": "question",
        "status": None,
        "time_scope": "future",
        "deadline_text": None,
        "prerequisite": "ㅅ승인자 변경 필요",
        "constraint": None,
        "certainty": "confirmed",
    }

    result = corrected(
        event,
        "혹시 ㅅ승인자 변경이 필요하면 제가 할 수 있을까요?",
        "원이정",
    )

    assert result["event_type"] == "question"
    assert result["actor"] is None
    assert result["prerequisite"] is None
    assert result["subject"] == "승인자 변경"


def test_uncertain_related_person_status_is_not_empty():
    event = {
        "subject": None,
        "actor": None,
        "related_people": [
            {
                "name": "연서영 매니저",
                "role": None,
                "certainty": "uncertain",
            }
        ],
        "action": None,
        "recipient": None,
        "event_type": "status",
        "status": None,
        "time_scope": "current",
        "deadline_text": None,
        "prerequisite": None,
        "constraint": None,
        "certainty": "uncertain",
    }

    result = corrected(
        event,
        "아마 연서영 매니저님일텐데",
        "홍길동",
    )

    assert result["status"] == "연서영 매니저 관련 가능성"
    assert result["certainty"] == "uncertain"


def test_receipt_check_requires_submission_in_same_message():
    events = [
        {
            "event_type": "plan",
            "action": "제출",
            "subject": None,
            "evidence": "만약 승인되면 제가 제출하고",
            "prerequisite": "승인 완료",
            "rule_corrections": [],
        },
        {
            "event_type": "plan",
            "action": "확인",
            "subject": "접수 여부",
            "evidence": "접수 여부까지 확인할게요",
            "prerequisite": None,
            "rule_corrections": [],
        },
    ]

    result = link_intra_message_dependencies(
        events,
        "네 알겠습니다. 만약 승인되면 제가 제출하고 접수 여부까지 확인할게요",
    )

    assert result[1]["prerequisite"] == "제출 완료"
    assert "receipt_check_requires_submission" in result[1]["rule_corrections"]


def main():
    tests = [
        test_deadline_does_not_invent_schedule,
        test_approver_role_uses_explicit_first_person_subject,
        test_question_does_not_promote_hypothesis_to_prerequisite,
        test_uncertain_related_person_status_is_not_empty,
        test_receipt_check_requires_submission_in_same_message,
    ]

    for test in tests:
        test()
        print("PASS", test.__name__)

    print(f"{len(tests)} tests passed")


if __name__ == "__main__":
    main()
