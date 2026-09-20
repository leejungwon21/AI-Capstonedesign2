import json
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
    / "events-v2-result.json"
)


# ==================================================
# Ollama 호출
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
# 예: "원이정 → 이혜정"
# ==================================================

def parse_speaker_label(speaker_label):
    if "→" in speaker_label:
        speaker, partner = speaker_label.split("→", 1)

        return (
            speaker.strip(),
            partner.strip()
        )

    return speaker_label.strip(), None


# ==================================================
# STEP 1
# 메시지 → 최소 업무 단위
# ==================================================

def split_into_units(
    message_id,
    speaker,
    conversation_partner,
    body
):

    prompt = f"""
너는 한국어 회사 업무 메시지를 분석한다.

현재 단계의 목적은 업무 역할을 판단하는 것이 아니라,
메시지 안의 서로 다른 업무 사건을 먼저 분리하는 것이다.

한 메시지에 여러 행동이나 상태가 있으면
각각 별개의 unit으로 분리한다.

예를 들어:

"MIGO 올리고, 마충렬 매니저님께 제출하겠습니다."

에는 서로 다른 행동이 두 개 있다.

1. MIGO 처리
2. 마충렬에게 제출

따라서 두 unit으로 분리해야 한다.

또한:

"WP1, WP2 승인이 완료됐고 PO번호를 보냈습니다."

에는

1. WP1 승인 상태
2. WP2 승인 상태
3. PO번호 발송

처럼 여러 사건이 존재할 수 있다.


중요 규칙:

1. 단순 인사나 감사는 제외한다.

2. 질문도 업무 상태 확인에 필요하면 하나의 unit이다.

3. 서로 다른 업무 대상이나 행동을 하나로 합치지 않는다.

4. 같은 문장을 근거로 여러 사건을 만들 수 있다.

5. evidence는 반드시 입력 body에 실제로 존재하는
   원문 일부를 그대로 사용한다.

6. 없는 내용을 만들지 않는다.

7. focus는 해당 unit이 무엇에 관한 것인지
   짧게 표현한다.


message_id:
{message_id}

speaker:
{speaker}

conversation_partner:
{conversation_partner}

body:
{body}


설명하지 말고 다음 JSON 형식으로만 출력한다.

{{
  "units": [
    {{
      "focus": "업무 사건을 짧게 표현",
      "evidence": "입력 body의 정확한 일부"
    }}
  ]
}}
"""

    result = call_ollama(prompt)

    return result.get("units", [])


# ==================================================
# STEP 2
# 업무 단위 하나 → Event 하나
# ==================================================

def extract_event(
    message_id,
    speaker,
    conversation_partner,
    body,
    focus,
    evidence
):

    prompt = f"""
너는 한국어 회사 업무 사건을 구조화하는 분석기다.

이번에는 이미 분리된 업무 사건 하나만 분석한다.


--------------------------------
필드 정의
--------------------------------

actor:
실제 행동을 수행했거나,
수행할 예정이거나,
수행 요청을 받은 사람

work_object:
업무의 대상

action:
구체적인 행동

recipient:
결과물이나 문서를 전달받는 사람

event_type:
아래 중 하나만 사용

request
plan
progress
completion
status
question
other

status:
현재 상태가 명확한 경우 기록
그렇지 않으면 null


--------------------------------
매우 중요한 규칙
--------------------------------

1.
"하겠습니다"
"할게요"
"드릴게요"
"보내겠습니다"

는 앞으로 할 행동이다.

반드시 plan으로 판단한다.


2.
"했습니다"
"보냈어요"
"완료했습니다"

처럼 이미 실행했다고 명확히 말한 경우에만
completion이다.


3.
"생성되어 있습니다"
"승인 대기 중입니다"
"승인 났네요"

처럼 현재 상태를 설명하면
status로 판단할 수 있다.


4.
한국어에서 speaker가

"제가 하겠습니다"
"하겠습니다"
"드릴게요"

라고 말하고 다른 실행자가 명시되지 않으면
speaker가 actor다.


5.
누군가에게

"해주세요"
"부탁드립니다"
"부탁드려요"

라고 요청하는 경우,
요청받은 사람이 actor다.

대화 상대가 요청을 받는 구조이고
다른 사람이 명시되지 않았다면
conversation_partner가 actor가 될 수 있다.


6.
conversation_partner라는 이유만으로
actor나 recipient로 지정하지 않는다.


7.
"A에게 제출"
"A에게 전달"
"A에게 메일"

처럼 실제 전달 대상이 명확한 경우만
A를 recipient로 지정한다.


8.
업무 상태를 보고한 사람과
실제 업무 수행자를 혼동하지 않는다.


예:

이혜정:
"이휘태 매니저님 승인이 났네요."

이혜정은 상태를 말한 사람이지
승인을 수행한 사람이라고 볼 수 없다.


9.
질문을 말한 사람을
업무 실행자로 자동 지정하지 않는다.


10.
없는 사람이나 행동,
날짜, 완료 사실을 만들지 않는다.

알 수 없으면 null로 둔다.


--------------------------------
현재 분석 대상
--------------------------------

message_id:
{message_id}

speaker:
{speaker}

conversation_partner:
{conversation_partner}

전체 메시지:
{body}

이번 업무 단위:
{focus}

근거:
{evidence}


설명하지 말고 JSON 객체 하나만 출력한다.

{{
  "actor": null,
  "work_object": null,
  "action": null,
  "recipient": null,
  "event_type": "other",
  "status": null
}}
"""

    return call_ollama(prompt)


# ==================================================
# STEP 3
# 규칙 기반 검증 및 명확한 보정
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

    # ------------------------------
    # 질문의 speaker를 실행자로 두지 않음
    # ------------------------------

    if event_type == "question":
        if actor == speaker:
            event["actor"] = None

            corrections.append(
                "question_actor_removed"
            )

    # ------------------------------
    # 부탁/요청인데 speaker를 actor로 잡은 경우
    # ------------------------------

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

    # ------------------------------
    # 완료/상태 표현을 plan으로 오인한 경우
    # ------------------------------

    state_markers = [
        "되어 있습니다",
        "되어 있어요",
        "대기 중",
        "승인 났",
    ]

    if event_type == "plan":

        if any(
            marker in evidence
            for marker in state_markers
        ):
            event["event_type"] = "status"

            corrections.append(
                "plan_changed_to_status"
            )

    # ------------------------------
    # 완료 표현
    # ------------------------------

    completion_markers = [
        "보냈어요",
        "보냈습니다",
        "완료했습니다",
        "완료됐습니다",
    ]

    if any(
        marker in evidence
        for marker in completion_markers
    ):
        if event.get("event_type") == "plan":

            event["event_type"] = "completion"

            corrections.append(
                "plan_changed_to_completion"
            )

    event["rule_corrections"] = corrections

    return event


# ==================================================
# 검증
# ==================================================

def validate_event(event, body):

    errors = []

    if (
        event.get("event_type")
        not in ALLOWED_EVENT_TYPES
    ):
        errors.append(
            "invalid event_type"
        )

    evidence = event.get("evidence")

    if not evidence:
        errors.append(
            "evidence is empty"
        )

    elif evidence not in body:
        errors.append(
            "evidence is not exact substring of body"
        )

    return errors


# ==================================================
# 실행
# ==================================================

def main():

    print("SAP source:", SOURCE_PATH)

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
        # STEP 1
        # ------------------------------------------

        units = split_into_units(
            message_id=source_id,
            speaker=speaker,
            conversation_partner=partner,
            body=body
        )

        processed_events = []

        # ------------------------------------------
        # STEP 2
        # ------------------------------------------

        for index, unit in enumerate(
            units,
            start=1
        ):

            focus = unit.get("focus")
            evidence = unit.get("evidence")

            # evidence가 원문에 없는 경우는
            # LLM 환각 가능성이 있으므로 건너뜀
            if (
                not evidence
                or evidence not in body
            ):
                print(
                    "SKIP invalid evidence:",
                    evidence
                )
                continue

            event = extract_event(
                message_id=source_id,
                speaker=speaker,
                conversation_partner=partner,
                body=body,
                focus=focus,
                evidence=evidence
            )

            event["evidence"] = evidence

            # --------------------------------------
            # STEP 3
            # --------------------------------------

            event = apply_rules(
                event=event,
                speaker=speaker,
                conversation_partner=partner,
                evidence=evidence
            )

            event_id = (
                f"{source_id}-E{index:02d}"
            )

            processed_event = {
                "event_id": event_id,
                "source_id": source_id,

                # 원본에서 복사
                "record_header":
                    record["record_header"],

                "slack_ts":
                    record["slack_ts"],

                "speaker":
                    speaker,

                "conversation_partner":
                    partner,

                # unit 정보
                "focus":
                    focus,

                # 추출 결과
                "actor":
                    event.get("actor"),

                "work_object":
                    event.get("work_object"),

                "action":
                    event.get("action"),

                "recipient":
                    event.get("recipient"),

                "event_type":
                    event.get("event_type"),

                "status":
                    event.get("status"),

                "evidence":
                    evidence,

                "rule_corrections":
                    event.get(
                        "rule_corrections",
                        []
                    )
            }

            processed_event[
                "validation_errors"
            ] = validate_event(
                processed_event,
                body
            )

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

                "events":
                    processed_events
            }
        )

    # ==================================================
    # 결과 저장
    # ==================================================

    RESULT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    final_output = {
        "version": "event-extraction-v2",
        "model": MODEL,
        "source_file": str(SOURCE_PATH),
        "message_count": len(
            source_data["records"]
        ),
        "results": all_results
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