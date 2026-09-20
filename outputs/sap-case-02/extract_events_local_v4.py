import json
import re
from pathlib import Path

import requests


# ==================================================
# 기본 설정
# ==================================================

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen3:4b-instruct"


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
    / "events-v4-result.json"
)


# ==================================================
# JSON Schema
# Ollama 출력 형식을 최대한 고정
# ==================================================

EVENT_SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": ["string", "null"]
                    },
                    "actor": {
                        "type": ["string", "null"]
                    },
                    "related_people": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string"
                                },
                                "role": {
                                    "type": ["string", "null"]
                                }
                            },
                            "required": [
                                "name",
                                "role"
                            ]
                        }
                    },
                    "action": {
                        "type": ["string", "null"]
                    },
                    "recipient": {
                        "type": ["string", "null"]
                    },
                    "event_type": {
                        "type": "string",
                        "enum": [
                            "request",
                            "plan",
                            "progress",
                            "completion",
                            "status",
                            "question",
                            "decision"
                        ]
                    },
                    "status": {
                        "type": ["string", "null"]
                    }
                },
                "required": [
                    "subject",
                    "actor",
                    "related_people",
                    "action",
                    "recipient",
                    "event_type",
                    "status"
                ]
            }
        }
    },
    "required": [
        "events"
    ]
}


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

            # 단순 json보다 schema를 직접 사용
            "format": EVENT_SCHEMA,

            "stream": False,

            "options": {
                "temperature": 0
            }
        },
        timeout=180
    )

    response.raise_for_status()

    content = response.json()[
        "message"
    ]["content"]

    return json.loads(content)


# ==================================================
# speaker_label 파싱
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

    return (
        speaker_label.strip(),
        None
    )


# ==================================================
# STEP 1
# 문장 분리
#
# LLM 사용 X
# 원문 문자열 그대로 유지
# ==================================================

def split_sentences(body):

    matches = re.findall(
        r'[^.!?]+[.!?]?',
        body
    )

    results = []

    for item in matches:

        text = item.strip()

        if text:
            results.append(text)

    return results


# ==================================================
# 행동 연결어가 있는 쉼표만 분리
#
# 예:
# MIGO 올리고, 제출하겠습니다
#
# → MIGO 올리고
# → 제출하겠습니다
#
# 하지만
#
# WP1는 이휘태 매니저님,
# WP2는 정상환...
#
# 은 분리하지 않음
# ==================================================

def split_action_clauses(sentence):

    comma_positions = [
        m.start()
        for m in re.finditer(
            ",",
            sentence
        )
    ]

    if not comma_positions:

        return [sentence]

    split_positions = []

    for position in comma_positions:

        left = sentence[:position].rstrip()

        action_endings = (
            "고",
            "하고",
            "올리고",
            "처리하고",
            "확인하고",
            "수정하고",
            "저장하고",
            "완료하고",
            "보내고",
            "전달하고",
            "하며",
            "하면서",
            "해서",
            "하여",
        )

        if left.endswith(
            action_endings
        ):
            split_positions.append(
                position
            )

    if not split_positions:

        return [sentence]

    clauses = []

    start = 0

    for position in split_positions:

        clause = sentence[
            start:position
        ].strip()

        if clause:
            clauses.append(
                clause
            )

        start = position + 1

    last_clause = sentence[
        start:
    ].strip()

    if last_clause:
        clauses.append(
            last_clause
        )

    return clauses


# ==================================================
# Candidate 생성
#
# 핵심:
# LLM이 evidence를 만들지 못하게 함
# ==================================================

def build_candidates(body):

    sentences = split_sentences(
        body
    )

    candidates = []

    for sentence in sentences:

        clauses = split_action_clauses(
            sentence
        )

        for clause in clauses:

            clause = clause.strip()

            if not clause:
                continue

            candidates.append(
                {
                    "candidate_id":
                        f"C{len(candidates) + 1:02d}",

                    "text":
                        clause
                }
            )

    return candidates


# ==================================================
# STEP 2
# Candidate 하나씩 Ollama 분석
# ==================================================

def analyze_candidate(
    speaker,
    conversation_partner,
    candidate_text
):

    prompt = f"""
너는 한국어 회사 업무 대화에서
업무 사건(Event)을 구조화하는 분석기다.

이번에는 메시지 전체가 아니라
하나의 짧은 원문 조각만 분석한다.

이 원문 조각 안에 의미 있는 업무 사건이 없으면
events를 빈 배열 [] 로 출력한다.

한 조각 안에 여러 업무 상태가 있다면
여러 Event를 생성할 수 있다.


================================
현재 대화 정보
================================

speaker:
{speaker}

conversation_partner:
{conversation_partner}

원문:
{candidate_text}


================================
필드 정의
================================

subject:
업무의 대상

예:
WP1 승인
WP2 승인
PR
PO번호
MIGO
서류 제출


actor:
실제로 업무 행동을 수행했거나,
수행할 예정이거나,
요청받은 사람.

단순히 상태를 말한 사람은 actor가 아니다.


related_people:
업무와 관련된 사람이지만
actor 또는 recipient라고 볼 수 없는 사람.

예:

승인 대기 중인 승인자라면

[
  {{
    "name": "이휘태",
    "role": "approver"
  }}
]


action:
실제 업무 행동 또는 상태.

"말했다"
"보고했다"

같은 대화 행위로 바꾸지 않는다.


recipient:
결과물이나 문서를
실제로 전달받는 사람.

명확하지 않으면 null.


event_type:

request
plan
progress
completion
status
question
decision


status:
현재 업무 상태가 명확하면 기록.

예:

승인 대기
승인 완료
PR 생성 완료

없으면 null.


================================
판단 규칙
================================

1.

speaker는 단순히 메시지를 말한 사람이다.

speaker라는 이유만으로
actor로 지정하지 않는다.


2.

질문하는 문장은

event_type = question

질문한 speaker를 actor로 지정하지 않는다.


3.

"하겠습니다"
"할게요"
"드릴게요"
"보내겠습니다"

는 아직 실행되지 않은 미래 행동이다.

event_type = plan


4.

미래 행동의 주어가 생략되어 있고
다른 실행자가 명시되지 않았다면

speaker가 actor다.

예:

speaker = 원이정

"오늘 제출하겠습니다."

actor = 원이정


5.

"했습니다"
"보냈어요"
"완료했습니다"

처럼 실행 완료가 명확하면

event_type = completion

주어가 생략돼 있고
다른 실행자가 없다면
speaker가 actor일 수 있다.


6.

"생성되어 있습니다"
"승인 대기 중"
"승인 났네요"

처럼 업무 상태를 설명하는 경우

event_type = status

상태를 말한 speaker를
actor로 넣으면 안 된다.


7.

승인 상태에서 등장하는 승인자는
related_people에 넣는다.

예:

"WP1은 이휘태 승인 대기 중"

subject = WP1 승인
actor = null

related_people = [
  {{
    "name": "이휘태",
    "role": "approver"
  }}
]

status = 승인 대기


8.

여러 사람의 승인 상태가 동시에 나오면
각 업무를 별도 Event로 만들 수 있다.


9.

"해주세요"
"부탁드립니다"
"부탁드려요"

처럼 상대방에게 행동을 요청하는 경우

event_type = request

다른 수행 대상이 명시되지 않았다면
conversation_partner를 actor로 본다.


10.

"A에게 제출하겠습니다"
"A에게 보내겠습니다"
"A에게 메일 드릴게요"

처럼 전달 대상이 명확할 때만

recipient = A


11.

conversation_partner라는 이유만으로
recipient로 지정하면 안 된다.


12.

"조금 기다려보시죠"

처럼 누군가에게 결과물을 전달하는 뜻이 아니라
그 사람의 승인이나 응답을 더 기다리자는 의미라면

recipient = null

event_type = decision

action = 조금 더 기다림

으로 해석할 수 있다.


13.

"PR까지만 생성되어 있습니다"

는 미래 계획이 아니다.

현재 PR이 생성되어 있다는 상태다.

event_type = status
status = PR 생성 완료


14.

"MIGO 올리고"

처럼 뒤 문장과 연결된 미래 행동이면

speaker의 plan으로 판단한다.


15.

단순 인사나 감사만 있는 문장은
업무 Event로 만들지 않는다.

events = []


16.

원문에 없는 사람,
날짜,
행동,
수신자,
완료 사실을 만들지 않는다.


17.

알 수 없는 값은 null로 둔다.


================================
출력
================================

설명하지 말고
지정된 JSON 형식만 출력한다.
"""

    result = call_ollama(
        prompt
    )

    return result.get(
        "events",
        []
    )


# ==================================================
# STEP 3
# 명확한 규칙만 Python으로 보정
# ==================================================

def apply_rules(
    event,
    speaker,
    partner,
    evidence
):

    corrections = []

    event_type = event.get(
        "event_type"
    )

    actor = event.get(
        "actor"
    )

    # ----------------------------------------------
    # question
    # 질문한 사람은 actor가 아님
    # ----------------------------------------------

    if (
        event_type == "question"
        and actor == speaker
    ):

        event["actor"] = None

        corrections.append(
            "question_speaker_removed"
        )

    # ----------------------------------------------
    # request
    # 다른 대상이 없고 상대에게 부탁
    # ----------------------------------------------

    request_markers = (
        "부탁드려요",
        "부탁드립니다",
        "해주세요",
        "해 주세요",
    )

    if (
        event_type == "request"
        and partner
        and any(
            marker in evidence
            for marker in request_markers
        )
        and actor in (
            None,
            speaker
        )
    ):

        event["actor"] = partner

        corrections.append(
            "request_actor_to_partner"
        )

    # ----------------------------------------------
    # 승인 상태 보고
    # speaker를 actor로 두지 않음
    # ----------------------------------------------

    approval_status = (
        "승인" in evidence
        and (
            "대기" in evidence
            or "났" in evidence
            or "완료" in evidence
        )
    )

    if (
        event_type == "status"
        and approval_status
        and event.get("actor")
        == speaker
    ):

        event["actor"] = None

        corrections.append(
            "approval_status_actor_removed"
        )

    # ----------------------------------------------
    # "~되어 있습니다"
    # 보고자가 실행자라는 근거 없음
    # ----------------------------------------------

    passive_markers = (
        "되어 있습니다",
        "되어 있어요",
    )

    if (
        event_type == "status"
        and any(
            marker in evidence
            for marker in passive_markers
        )
        and event.get("actor")
        == speaker
    ):

        event["actor"] = None

        corrections.append(
            "passive_status_actor_removed"
        )

    event[
        "rule_corrections"
    ] = corrections

    return event


# ==================================================
# 타입 및 결과 검증
# ==================================================

def validate_event(
    event
):

    errors = []

    if not isinstance(
        event.get(
            "related_people"
        ),
        list
    ):

        errors.append(
            "related_people_not_list"
        )

    if event.get(
        "event_type"
    ) not in {
        "request",
        "plan",
        "progress",
        "completion",
        "status",
        "question",
        "decision",
    }:

        errors.append(
            "invalid_event_type"
        )

    return errors


# ==================================================
# 중복 Event 제거
# ==================================================

def deduplicate_events(
    events
):

    output = []
    seen = set()

    for event in events:

        related_people = event.get(
            "related_people",
            []
        )

        related_names = tuple(
            sorted(
                item.get(
                    "name",
                    ""
                )
                for item
                in related_people
            )
        )

        key = (
            event.get("subject"),
            event.get("actor"),
            event.get("action"),
            event.get("recipient"),
            event.get("event_type"),
            event.get("status"),
            related_names,
            event.get("evidence"),
        )

        if key in seen:
            continue

        seen.add(key)

        output.append(
            event
        )

    return output


# ==================================================
# 메인
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

        source_data = json.load(
            f
        )

    all_results = []

    for record in source_data[
        "records"
    ]:

        source_id = record[
            "source_id"
        ]

        body = record[
            "body"
        ]

        speaker, partner = (
            parse_speaker_label(
                record[
                    "speaker_label"
                ]
            )
        )

        print()
        print("=" * 60)

        print(
            source_id
        )

        print(
            "speaker:",
            speaker
        )

        print(
            "partner:",
            partner
        )

        print(
            "body:",
            body
        )

        # ==========================================
        # Candidate 생성
        # ==========================================

        candidates = build_candidates(
            body
        )

        processed_events = []

        for candidate in candidates:

            candidate_id = candidate[
                "candidate_id"
            ]

            evidence = candidate[
                "text"
            ]

            print()
            print(
                candidate_id,
                ":",
                evidence
            )

            # ======================================
            # Candidate 하나씩 Ollama 분석
            # ======================================

            events = analyze_candidate(
                speaker=speaker,
                conversation_partner=partner,
                candidate_text=evidence
            )

            for event in events:

                event = apply_rules(
                    event=event,
                    speaker=speaker,
                    partner=partner,
                    evidence=evidence
                )

                validation_errors = (
                    validate_event(
                        event
                    )
                )

                processed_event = {
                    "source_id":
                        source_id,

                    "candidate_id":
                        candidate_id,

                    "record_header":
                        record[
                            "record_header"
                        ],

                    "slack_ts":
                        record[
                            "slack_ts"
                        ],

                    "speaker":
                        speaker,

                    "conversation_partner":
                        partner,

                    # evidence는 Python 원문 그대로
                    "evidence":
                        evidence,

                    "subject":
                        event.get(
                            "subject"
                        ),

                    "actor":
                        event.get(
                            "actor"
                        ),

                    "related_people":
                        event.get(
                            "related_people",
                            []
                        ),

                    "action":
                        event.get(
                            "action"
                        ),

                    "recipient":
                        event.get(
                            "recipient"
                        ),

                    "event_type":
                        event.get(
                            "event_type"
                        ),

                    "status":
                        event.get(
                            "status"
                        ),

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

        # ==========================================
        # 중복 제거
        # ==========================================

        processed_events = (
            deduplicate_events(
                processed_events
            )
        )

        # event_id는 중복 제거 후 다시 부여
        for index, event in enumerate(
            processed_events,
            start=1
        ):

            event["event_id"] = (
                f"{source_id}-E{index:02d}"
            )

            print()
            print(
                json.dumps(
                    event,
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

                "candidates":
                    candidates,

                "events":
                    processed_events
            }
        )

    # ==============================================
    # 저장
    # ==============================================

    RESULT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    final_output = {
        "version":
            "event-extraction-v4",

        "model":
            MODEL,

        "source_file":
            str(
                SOURCE_PATH
            ),

        "message_count":
            len(
                source_data[
                    "records"
                ]
            ),

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