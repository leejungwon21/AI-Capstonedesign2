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


# --------------------------------------------------
# 경로
# --------------------------------------------------

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
    / "events-v1-result.json"
)


# --------------------------------------------------
# speaker_label 분리
# 예: "원이정 → 이혜정"
# --------------------------------------------------

def parse_speaker_label(speaker_label):
    if "→" in speaker_label:
        speaker, partner = speaker_label.split("→", 1)

        return (
            speaker.strip(),
            partner.strip()
        )

    return speaker_label.strip(), None


# --------------------------------------------------
# 한 메시지에서 Event 추출
# --------------------------------------------------

def extract_events(
    message_id,
    speaker,
    conversation_partner,
    body
):
    prompt = f"""
너는 한국어 회사 업무 메시지에서
업무 사건(Event)을 추출하는 분석기다.

한 메시지에는 사건이 없을 수도 있고,
하나 또는 여러 개 있을 수도 있다.

메시지 안에 서로 다른 업무 행동이나 상태가 있다면
반드시 별개의 Event로 분리한다.

--------------------------------
필드 정의
--------------------------------

speaker:
메시지를 실제로 말한 사람

conversation_partner:
현재 Slack 대화 상대
단, 이 사람을 업무 actor나 recipient로
자동 판단하면 안 된다.

actor:
실제 행동을 수행했거나,
수행 중이거나,
수행할 예정이거나,
수행 요청을 받은 사람

work_object:
행동 또는 상태의 대상
예: WP1 승인, WP2 승인, MIGO, PO번호, 서류

action:
구체적으로 발생했거나 발생할 행동

recipient:
결과물이나 문서를 실제로 전달받는 사람
명시되지 않으면 null

event_type:
다음 중 하나만 사용한다.

request
plan
progress
completion
status
question
other

status:
메시지에서 명확하게 확인되는 상태
예:
"승인 대기"
"승인 완료"
"PR 생성 완료"

명확하지 않으면 null

evidence:
해당 Event의 판단 근거가 되는
원문의 정확한 일부 문장

--------------------------------
중요 규칙
--------------------------------

1.
"하겠습니다"
"할게요"
"드릴게요"
"보내겠습니다"

처럼 앞으로 할 행동은 plan이다.

완료로 분류하면 안 된다.

2.
"했습니다"
"완료했습니다"
"보냈어요"
"승인 났네요"

처럼 이미 끝났다고 명확하게 표현한 경우만
completion 또는 완료 상태로 판단한다.

3.
한국어에서 주어가 생략된 상태로

"하겠습니다"
"할게요"
"드리겠습니다"

라고 speaker가 말하면,
다른 실행자가 명시되지 않는 한
speaker를 actor로 본다.

4.
누군가에게

"해 주세요"
"부탁드립니다"
"확인해 주세요"

라고 요청하면
요청받은 사람이 actor다.

5.
conversation_partner라는 이유만으로
그 사람을 actor나 recipient로 지정하지 않는다.

6.
"A에게 제출한다"
"A에게 보낸다"

라고 명확히 쓰인 경우에만
A를 recipient로 지정한다.

7.
업무 승인자와
업무 내용을 말한 사람을 혼동하지 않는다.

8.
업무 상태에 등장한 사람을
메시지 speaker라는 이유로 실행자로 지정하지 않는다.

9.
메시지에 없는 사람,
날짜,
업무,
완료 사실을 만들지 않는다.

10.
정보가 없으면 null을 사용한다.

11.
하나의 메시지에 서로 다른 행동이 있으면
Event를 여러 개 생성한다.

12.
단순 인사나 감사 표현은
별도 Event로 생성하지 않는다.


--------------------------------
예시
--------------------------------

speaker: 김민지
conversation_partner: 이대리

body:
자료 수정해서 오후에 박대리님께 보내겠습니다.

결과:

[
  {{
    "actor": "김민지",
    "work_object": "자료",
    "action": "자료를 수정한 뒤 전달",
    "recipient": "박대리",
    "event_type": "plan",
    "status": null,
    "evidence": "자료 수정해서 오후에 박대리님께 보내겠습니다."
  }}
]


--------------------------------
분석 대상
--------------------------------

message_id: {message_id}

speaker: {speaker}

conversation_partner: {conversation_partner}

body:
{body}


설명문은 출력하지 않는다.

반드시 다음 형식의 JSON 객체 하나만 출력한다.

{{
  "events": [
    {{
      "actor": null,
      "work_object": null,
      "action": null,
      "recipient": null,
      "event_type": "other",
      "status": null,
      "evidence": ""
    }}
  ]
}}
"""

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
        timeout=120
    )

    response.raise_for_status()

    content = response.json()["message"]["content"]

    parsed = json.loads(content)

    return parsed.get("events", [])


# --------------------------------------------------
# 간단한 검증
# --------------------------------------------------

def validate_event(event, body):
    errors = []

    event_type = event.get("event_type")

    if event_type not in ALLOWED_EVENT_TYPES:
        errors.append(
            f"invalid event_type: {event_type}"
        )

    evidence = event.get("evidence")

    if evidence:
        if evidence not in body:
            errors.append(
                "evidence is not an exact substring of body"
            )
    else:
        errors.append(
            "evidence is empty"
        )

    return errors


# --------------------------------------------------
# SAP 전체 메시지 처리
# --------------------------------------------------

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

        events = extract_events(
            message_id=source_id,
            speaker=speaker,
            conversation_partner=partner,
            body=body
        )

        processed_events = []

        for index, event in enumerate(
            events,
            start=1
        ):
            event_id = (
                f"{source_id}-E{index:02d}"
            )

            validation_errors = validate_event(
                event,
                body
            )

            processed_event = {
                "event_id": event_id,
                "source_id": source_id,

                # 원본에서 프로그램이 복사
                "record_header": record[
                    "record_header"
                ],
                "slack_ts": record[
                    "slack_ts"
                ],

                "speaker": speaker,
                "conversation_partner": partner,

                # LLM 추출
                "actor": event.get(
                    "actor"
                ),
                "work_object": event.get(
                    "work_object"
                ),
                "action": event.get(
                    "action"
                ),
                "recipient": event.get(
                    "recipient"
                ),
                "event_type": event.get(
                    "event_type"
                ),
                "status": event.get(
                    "status"
                ),
                "evidence": event.get(
                    "evidence"
                ),

                # 프로그램 검증
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
                "source_id": source_id,
                "body": body,
                "events": processed_events
            }
        )

    RESULT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    final_output = {
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