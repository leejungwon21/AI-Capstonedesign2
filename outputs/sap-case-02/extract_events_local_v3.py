import json
import re
from pathlib import Path

import requests


OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen3:4b-instruct"

ALLOWED_EVENT_TYPES = {
    "request",
    "plan",
    "progress",
    "completion",
    "status",
    "question",
    "decision",
    "other",
}


# ==================================================
# 경로
# ==================================================

CURRENT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = CURRENT_DIR.parent

SOURCE_PATH = (
    OUTPUTS_DIR
    / "slack-mcp"
    / "collected"
    / "sap.json"
)

RESULT_PATH = (
    CURRENT_DIR
    / "local-results"
    / "events-v3-result.json"
)


# ==================================================
# Ollama
# ==================================================

def call_ollama(prompt):

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0
            }
        },
        timeout=180
    )

    response.raise_for_status()

    content = response.json()["message"]["content"]

    return json.loads(content)


# ==================================================
# speaker_label 분리
# ==================================================

def parse_speaker_label(speaker_label):

    if "→" in speaker_label:

        speaker, partner = speaker_label.split(
            "→",
            1
        )

        return (
            speaker.strip(),
            partner.strip()
        )

    return speaker_label.strip(), None


# ==================================================
# STEP 1
# Python이 원문 그대로 후보 span 생성
# LLM에게 문장을 다시 쓰게 하지 않음
# ==================================================

def build_candidate_spans(body):

    spans = []
    seen = set()

    def add_span(text):

        text = text.strip()

        if not text:
            return

        if text in seen:
            return

        seen.add(text)

        spans.append({
            "evidence_id": f"C{len(spans) + 1:02d}",
            "text": text
        })

    # ----------------------------------------------
    # 문장 단위
    # ----------------------------------------------

    sentence_matches = re.findall(
        r'[^.!?]+[.!?]?',
        body
    )

    for sentence in sentence_matches:

        sentence = sentence.strip()

        if not sentence:
            continue

        add_span(sentence)

        # ------------------------------------------
        # 쉼표 단위도 추가
        # 단, 원문은 그대로 유지
        # ------------------------------------------

        comma_parts = sentence.split(",")

        if len(comma_parts) > 1:

            for index, part in enumerate(
                comma_parts
            ):

                part = part.strip()

                if not part:
                    continue

                # 원래 쉼표가 뒤에 있었으면 보존
                if index < len(comma_parts) - 1:
                    part = part + ","

                add_span(part)

    # body가 특수한 형태라 아무것도 안 생기면
    # 원문 전체 사용
    if not spans:
        add_span(body)

    return spans


# ==================================================
# STEP 2
# 후보 span 중 무엇을 근거로 어떤 Event인지 판단
# ==================================================

def extract_events(
    message_id,
    speaker,
    conversation_partner,
    body,
    candidate_spans
):

    candidate_text = "\n".join(
        [
            f'{item["evidence_id"]}: {item["text"]}'
            for item in candidate_spans
        ]
    )

    prompt = f"""
너는 한국어 회사 업무 대화에서
업무 사건(Event)을 구조화한다.

매우 중요하다.

너는 evidence 문장을 직접 작성하지 않는다.

Python이 원문에서 그대로 만든
candidate evidence 중 하나를 선택해서
evidence_id만 출력해야 한다.


================================
필드 정의
================================

subject:
이 사건의 업무 대상.

예:
WP1 승인
WP2 승인
PR
MIGO
PO번호
서류 제출


actor:
실제로 행동을 수행했거나
수행할 예정이거나
수행 요청을 받은 사람.

단순히 상태를 말한 사람은 actor가 아니다.


related_person:
업무 상태와 관련된 사람이지만
actor나 recipient라고 확정할 수 없는 사람.

예:
승인 대기 중인 승인자


related_role:
related_person의 역할.

예:
approver
requester
reviewer

알 수 없으면 null.


action:
실제 업무 행동 또는 상태.

"보고한다", "말한다" 같은
대화 행위로 바꾸지 않는다.

예:
승인 대기
PR 생성 완료
메일 발송
MIGO 처리
서류 제출


recipient:
결과물이나 업무를 실제로 전달받는 사람.

명시되지 않으면 null.


event_type:

request
plan
progress
completion
status
question
decision
other


status:
업무의 현재 상태가 명확하면 기록한다.

예:
승인 대기
승인 완료
PR 생성 완료

그렇지 않으면 null.


evidence_id:
아래 candidate evidence 중
이 Event의 근거가 되는 ID 하나만 선택한다.


================================
중요 규칙
================================

1.

speaker는 메시지를 말한 사람일 뿐이다.

speaker라는 이유만으로
actor로 지정하지 않는다.


2.

질문한 사람을
업무 actor로 지정하지 않는다.


3.

"하겠습니다"
"할게요"
"드릴게요"
"보내겠습니다"

는 아직 완료되지 않은 미래 행동이다.

event_type = plan


4.

"했습니다"
"보냈어요"
"완료했습니다"

처럼 실제 완료가 명확할 때만

event_type = completion


5.

"생성되어 있습니다"
"승인 대기 중"
"승인 났네요"

처럼 현재 상태를 설명하면

event_type = status


6.

승인 상태에서

"이휘태 매니저 승인 대기"
"정상환 이사 승인 완료"

처럼 사람이 승인과 연결돼 있다면,

그 사람을 related_person으로 두고
related_role = "approver"로 표현할 수 있다.

상태를 보고한 speaker를
actor로 지정하지 않는다.


7.

"부탁드려요"
"해주세요"

처럼 conversation_partner에게
업무를 요청하는 문장이고
다른 요청 대상이 명시되지 않았다면,

conversation_partner가 actor다.


8.

"A에게 제출하겠습니다"
"A에게 보내겠습니다"

처럼 전달 대상이 명확한 경우만

recipient = A


9.

"조금 기다려보시죠"

처럼 특정 사람에게 무언가를
전달하라는 의미가 아니라

업무를 조금 더 기다리자는 판단이면

그 사람을 recipient로 지정하지 않는다.

event_type = decision 으로 표현할 수 있다.


10.

한 문장에 서로 다른 업무가 여러 개면
Event를 여러 개 생성한다.


11.

예를 들어

"MIGO 올리고, 마충렬 매니저님께 제출하겠습니다."

에는

- MIGO 처리 계획
- 마충렬에게 제출 계획

이라는 서로 다른 두 Event가 있다.


12.

두 명의 승인 상태가 동시에 나오면
각 승인 상태를 별도 Event로 만들 수 있다.


13.

같은 Event를 중복 생성하지 않는다.


14.

가능하면 해당 Event를 완전히 뒷받침하는
가장 작은 candidate evidence를 선택한다.


15.

candidate evidence의 텍스트를
수정하거나 다시 작성하면 안 된다.

반드시 evidence_id만 선택한다.


================================
메시지
================================

message_id:
{message_id}

speaker:
{speaker}

conversation_partner:
{conversation_partner}

전체 body:
{body}


================================
candidate evidence
================================

{candidate_text}


================================
출력
================================

설명문은 출력하지 않는다.

반드시 JSON 객체 하나만 출력한다.

{{
  "events": [
    {{
      "evidence_id": "C01",
      "subject": null,
      "actor": null,
      "related_person": null,
      "related_role": null,
      "action": null,
      "recipient": null,
      "event_type": "other",
      "status": null
    }}
  ]
}}
"""

    result = call_ollama(prompt)

    return result.get("events", [])


# ==================================================
# STEP 3
# 규칙 기반 보정
# ==================================================

def apply_rules(
    event,
    speaker,
    conversation_partner,
    evidence
):

    corrections = []

    event_type = event.get("event_type")
    actor = event.get("actor")

    # ----------------------------------------------
    # 질문한 speaker를 actor로 두지 않음
    # ----------------------------------------------

    if event_type == "question":

        if actor == speaker:

            event["actor"] = None

            corrections.append(
                "question_speaker_removed_from_actor"
            )

    # ----------------------------------------------
    # 부탁 → conversation partner가 수행자
    # ----------------------------------------------

    request_markers = [
        "부탁드려요",
        "부탁드립니다",
        "해주세요",
        "해 주세요",
    ]

    if event_type == "request":

        has_request_marker = any(
            marker in evidence
            for marker in request_markers
        )

        if (
            has_request_marker
            and conversation_partner
            and actor in (None, speaker)
        ):

            event["actor"] = conversation_partner

            corrections.append(
                "request_actor_changed_to_partner"
            )

    # ----------------------------------------------
    # 승인 상태에서 speaker를 actor로 잡으면 제거
    # ----------------------------------------------

    approval_state = (
        "승인" in evidence
        and (
            "대기" in evidence
            or "났" in evidence
            or "완료" in evidence
        )
    )

    if (
        event_type == "status"
        and approval_state
        and event.get("actor") == speaker
    ):

        event["actor"] = None

        corrections.append(
            "approval_status_speaker_removed_from_actor"
        )

    # ----------------------------------------------
    # 수동태 상태 → speaker가 actor가 아님
    # ----------------------------------------------

    passive_state_markers = [
        "생성되어 있습니다",
        "생성되어 있어요",
    ]

    if (
        event_type == "status"
        and any(
            marker in evidence
            for marker in passive_state_markers
        )
        and event.get("actor") == speaker
    ):

        event["actor"] = None

        corrections.append(
            "passive_status_speaker_removed_from_actor"
        )

    event["rule_corrections"] = corrections

    return event


# ==================================================
# STEP 4
# 검증
# ==================================================

def validate_event(
    event,
    span_map
):

    errors = []

    event_type = event.get(
        "event_type"
    )

    if event_type not in ALLOWED_EVENT_TYPES:

        errors.append(
            f"invalid event_type: {event_type}"
        )

    evidence_id = event.get(
        "evidence_id"
    )

    if evidence_id not in span_map:

        errors.append(
            f"invalid evidence_id: {evidence_id}"
        )

    return errors


# ==================================================
# 실행
# ==================================================

def main():

    print(
        "SAP source:",
        SOURCE_PATH
    )

    with open(
        SOURCE_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        source_data = json.load(f)

    all_results = []

    for record in source_data["records"]:

        source_id = record["source_id"]
        speaker_label = record["speaker_label"]
        body = record["body"]

        speaker, partner = parse_speaker_label(
            speaker_label
        )

        print()
        print("=" * 60)
        print(source_id)
        print("speaker:", speaker)
        print("partner:", partner)
        print("body:", body)

        # ------------------------------------------
        # Python이 원문 candidate 생성
        # ------------------------------------------

        candidate_spans = build_candidate_spans(
            body
        )

        span_map = {
            item["evidence_id"]: item["text"]
            for item in candidate_spans
        }

        print()
        print("candidate evidence")

        for candidate in candidate_spans:

            print(
                candidate["evidence_id"],
                ":",
                candidate["text"]
            )

        # ------------------------------------------
        # Ollama Event 분석
        # ------------------------------------------

        events = extract_events(
            message_id=source_id,
            speaker=speaker,
            conversation_partner=partner,
            body=body,
            candidate_spans=candidate_spans
        )

        processed_events = []

        for index, event in enumerate(
            events,
            start=1
        ):

            evidence_id = event.get(
                "evidence_id"
            )

            validation_errors = validate_event(
                event,
                span_map
            )

            # 존재하지 않는 evidence ID면
            # Event 자체를 신뢰하지 않음
            if evidence_id not in span_map:

                evidence = None

            else:

                # 여기서 Python이 원문 그대로 복사
                evidence = span_map[
                    evidence_id
                ]

            if evidence is not None:

                event = apply_rules(
                    event=event,
                    speaker=speaker,
                    conversation_partner=partner,
                    evidence=evidence
                )

            else:

                event["rule_corrections"] = []

            event_id = (
                f"{source_id}-E{index:02d}"
            )

            processed_event = {
                "event_id":
                    event_id,

                "source_id":
                    source_id,

                "record_header":
                    record["record_header"],

                "slack_ts":
                    record["slack_ts"],

                "speaker":
                    speaker,

                "conversation_partner":
                    partner,

                # LLM은 ID만 선택
                "evidence_id":
                    evidence_id,

                # Python이 원문 복사
                "evidence":
                    evidence,

                "subject":
                    event.get("subject"),

                "actor":
                    event.get("actor"),

                "related_person":
                    event.get("related_person"),

                "related_role":
                    event.get("related_role"),

                "action":
                    event.get("action"),

                "recipient":
                    event.get("recipient"),

                "event_type":
                    event.get("event_type"),

                "status":
                    event.get("status"),

                "rule_corrections":
                    event.get(
                        "rule_corrections",
                        []
                    ),

                "validation_errors":
                    validation_errors
            }

            processed_events.append(
                processed_event
            )

            print()
            print(
                json.dumps(
                    processed_event,
                    ensure_ascii=False,
                    indent=2
                )
            )

        all_results.append(
            {
                "source_id":
                    source_id,

                "body":
                    body,

                "candidate_spans":
                    candidate_spans,

                "events":
                    processed_events
            }
        )

    # ==================================================
    # 저장
    # ==================================================

    RESULT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    final_output = {
        "version":
            "event-extraction-v3",

        "model":
            MODEL,

        "source_file":
            str(SOURCE_PATH),

        "message_count":
            len(source_data["records"]),

        "results":
            all_results
    }

    with open(
        RESULT_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            final_output,
            f,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("=" * 60)
    print("완료")

    print(
        "결과 저장:",
        RESULT_PATH
    )


if __name__ == "__main__":
    main()