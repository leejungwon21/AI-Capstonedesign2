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

# 현재 테스트 사례: 사례 ④ 발주 요청서
CASE_DIR = CURRENT_DIR / "approval-case-04"

SOURCE_PATH = CASE_DIR / "source.json"

RESULT_PATH = (
    CASE_DIR
    / "local-results"
    / "events-v4-4-general-result.json"
)


# ==================================================
# Ollama JSON Schema
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
                                },
                                "certainty": {
                                    "type": "string",
                                    "enum": [
                                        "confirmed",
                                        "uncertain"
                                    ]
                                }
                            },
                            "required": [
                                "name",
                                "role",
                                "certainty"
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
                            "requirement",
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
                    },
                    "time_scope": {
                        "type": "string",
                        "enum": [
                            "past",
                            "current",
                            "future",
                            "unknown"
                        ]
                    },
                    "deadline_text": {
                        "type": ["string", "null"]
                    },
                    "prerequisite": {
                        "type": ["string", "null"]
                    },
                    "constraint": {
                        "type": ["string", "null"]
                    },
                    "certainty": {
                        "type": "string",
                        "enum": [
                            "confirmed",
                            "uncertain"
                        ]
                    }
                },
                "required": [
                    "subject",
                    "actor",
                    "related_people",
                    "action",
                    "recipient",
                    "event_type",
                    "status",
                    "time_scope",
                    "deadline_text",
                    "prerequisite",
                    "constraint",
                    "certainty"
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
# 참여자 추출
# ==================================================

def get_participants(records):

    participants = []

    for record in records:

        speaker = record[
            "speaker_label"
        ].strip()

        if speaker not in participants:
            participants.append(speaker)

    return participants


# ==================================================
# 2인 DM 상대 추론
# ==================================================

def infer_partner(
    speaker,
    participants
):

    others = [
        person
        for person in participants
        if person != speaker
    ]

    if len(others) == 1:
        return others[0]

    return None


# ==================================================
# 문장 분리
#
# ?, !, . 만 문장 종료 후보
#
# !!, ???, ?!, !? 는 하나의 종료부호로 처리
#
# 이모지 / ㅋㅋ / ㅠㅠ / ~ / 괄호 / slash 등은
# 분리하지 않는다.
#
# .xlsx, .pdf, 3.5 같은 내부 점도
# 문장 종료로 판단하지 않는다.
# ==================================================

def split_sentences(body):

    sentences = []

    current = []
    inside_backtick = False

    i = 0

    while i < len(body):

        char = body[i]

        # ------------------------------------------
        # backtick
        # ------------------------------------------

        if char == "`":

            inside_backtick = not inside_backtick

            current.append(char)

            i += 1
            continue

        # ------------------------------------------
        # 줄바꿈
        # ------------------------------------------

        if (
            char == "\n"
            and not inside_backtick
        ):

            sentence = "".join(
                current
            ).strip()

            if sentence:
                sentences.append(
                    sentence
                )

            current = []

            i += 1
            continue

        # ------------------------------------------
        # ? / !
        #
        # 연속된 !!! ??? ?! 등을 하나로 유지
        # ------------------------------------------

        if (
            char in ("?", "!")
            and not inside_backtick
        ):

            current.append(char)

            i += 1

            while (
                i < len(body)
                and body[i] in ("?", "!")
            ):

                current.append(
                    body[i]
                )

                i += 1

            sentence = "".join(
                current
            ).strip()

            if sentence:
                sentences.append(
                    sentence
                )

            current = []

            continue

        # ------------------------------------------
        # 마침표
        # ------------------------------------------

        if (
            char == "."
            and not inside_backtick
        ):

            prev_char = (
                body[i - 1]
                if i > 0
                else ""
            )

            next_char = (
                body[i + 1]
                if i + 1 < len(body)
                else ""
            )

            # .xlsx
            # 3.5
            # abc.def
            is_internal_dot = (
                prev_char.isalnum()
                and next_char.isalnum()
            )

            current.append(char)

            if not is_internal_dot:

                i += 1

                # ... 처리
                while (
                    i < len(body)
                    and body[i] == "."
                ):

                    current.append(
                        body[i]
                    )

                    i += 1

                sentence = "".join(
                    current
                ).strip()

                if sentence:
                    sentences.append(
                        sentence
                    )

                current = []

                continue

            i += 1
            continue

        # ------------------------------------------
        # 나머지 문자
        # emoji 등 모두 그대로 유지
        # ------------------------------------------

        current.append(char)

        i += 1

    remaining = "".join(
        current
    ).strip()

    if remaining:
        sentences.append(
            remaining
        )

    return sentences


# ==================================================
# 시간 범위 탐지
# ==================================================

def detect_sentence_time_scope(sentence):

    past_markers = (
        "지난주",
        "지난 달",
        "지난달",
        "어제",
        "지난번",
        "지난 번",
        "저번주",
        "저번 주",
    )

    current_markers = (
        "이번 주",
        "이번주",
        "오늘",
        "현재",
        "지금",
        "방금",
    )

    future_markers = (
        "다음 주",
        "다음주",
        "내일",
        "모레",
    )

    if any(
        marker in sentence
        for marker in past_markers
    ):
        return "past"

    if any(
        marker in sentence
        for marker in future_markers
    ):
        return "future"

    if any(
        marker in sentence
        for marker in current_markers
    ):
        return "current"

    return None


# ==================================================
# 행동 연결 쉼표 분리
#
# MIGO 올리고, 제출하겠습니다
# 등은 분리
#
# 단순 명사 나열은 분리하지 않음
# ==================================================

def split_action_clauses(sentence):

    comma_positions = [
        match.start()
        for match in re.finditer(
            ",",
            sentence
        )
    ]

    if not comma_positions:
        return [sentence]

    action_endings = (
        "하고",
        "올리고",
        "처리하고",
        "확인하고",
        "수정하고",
        "저장하고",
        "완료하고",
        "보내고",
        "전달하고",
        "끝났고",
        "마쳤고",
        "하며",
        "하면서",
        "해서",
        "하여",
    )

    split_positions = []

    for position in comma_positions:

        left = sentence[
            :position
        ].rstrip()

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
# ==================================================

def build_candidates(body):

    candidates = []

    inherited_time_scope = None

    sentences = split_sentences(
        body
    )

    for sentence in sentences:

        # 특수문자만 존재하면 무시
        if not re.search(
            r"[가-힣A-Za-z0-9]",
            sentence
        ):
            continue

        explicit_scope = (
            detect_sentence_time_scope(
                sentence
            )
        )

        if explicit_scope is not None:

            inherited_time_scope = (
                explicit_scope
            )

        sentence_context = (
            explicit_scope
            or inherited_time_scope
        )

        clauses = split_action_clauses(
            sentence
        )

        for clause in clauses:

            clause = clause.strip()

            if not clause:
                continue

            # emoji / ! / ? 등만 있는 조각 제거
            if not re.search(
                r"[가-힣A-Za-z0-9]",
                clause
            ):
                continue

            candidates.append({
                "candidate_id":
                    f"C{len(candidates) + 1:02d}",

                "text":
                    clause,

                "context_time_scope":
                    sentence_context
            })

    return candidates


# ==================================================
# Deadline 추출
# ==================================================

def extract_deadline_text(evidence):

    patterns = [
        r"오늘\s*(?:오전|오후)?\s*\d{1,2}시(?:\s*\d{1,2}분)?까지",
        r"내일\s*(?:오전|오후)?\s*\d{1,2}시(?:\s*\d{1,2}분)?까지",
        r"이번\s*주\s*[월화수목금토일]요일(?:까지)?",
        r"다음\s*주\s*[월화수목금토일]요일(?:까지)?",
        r"오늘\s*퇴근하기\s*전에",
        r"퇴근하기\s*전에",
        r"오늘\s*중",
        r"이번\s*주\s*중",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            evidence
        )

        if match:
            return match.group(0)

    return None


# ==================================================
# LLM Candidate 분석
# ==================================================

def analyze_candidate(
    speaker,
    conversation_partner,
    candidate_text,
    context_time_scope
):

    prompt = f"""
너는 한국어 회사 업무 대화에서
업무 사건(Event)을 구조화하는 분석기다.

입력은 전체 대화가 아니라
원문에서 분리한 하나의 후보 문장이다.

단순 인사, 감사, 감탄만 존재하면
events를 빈 배열로 출력한다.

한 문장에 서로 다른 업무 사건이
실제로 여러 개 존재하면
여러 Event를 생성할 수 있다.


================================
대화 정보
================================

speaker:
{speaker}

conversation_partner:
{conversation_partner}

이전 문맥 시간 범위:
{context_time_scope}

원문:
{candidate_text}


================================
필드
================================

subject:
업무 대상.


actor:
실제로 행동했거나,
행동할 예정이거나,
요청을 받아 행동해야 하는 사람.


related_people:
업무와 관련 있지만
현재 정보만으로 actor나 recipient로
확정할 수 없는 사람.


related_people.certainty:

confirmed
uncertain

"아마", "아마도", "~일 텐데",
"것 같다"처럼 추정이면 uncertain.


action:
실제 업무 행동 또는 상태.


recipient:
업무 결과나 문서를
실제로 전달받는 사람.


event_type:

request
requirement
plan
progress
completion
status
question
decision


status:
현재 업무 상태가
명확한 경우에 기록.


time_scope:

past
current
future
unknown


deadline_text:
실제 업무 마감 표현.


prerequisite:
해당 업무를 수행하기 전에
먼저 충족되어야 하는 조건.

예:

"승인되면 제가 제출할게요"

prerequisite = "승인 완료"


constraint:
업무 진행을 막거나 제한하는
시스템, 권한, 절차 조건.

예:

"최종 승인이 있어야 제출 버튼이 눌립니다"

constraint =
"최종 승인 전에는 제출 불가"


certainty:

confirmed
uncertain

Event 자체가 확정적인 사실/계획이면 confirmed.

추측 자체가 Event이면 uncertain.


================================
판단 규칙
================================

1.
speaker라는 이유만으로
actor로 지정하지 않는다.


2.
질문 문장은 question이다.

질문만으로 업무 상태를
확정하지 않는다.


3.
"하겠습니다"
"할게요"
"확인해볼게요"
"확인할게요"

처럼 화자가 앞으로 행동하겠다고 하면

event_type = plan


4.
"끝났습니다"
"확인했어요"
"저장했어요"

처럼 이미 수행한 행동은

completion 또는 status다.


5.
"부탁드립니다"
"해주세요"
"기다려주세요"

처럼 상대에게 행동을 요구하면

request다.

다른 수행자가 명시되지 않았다면
conversation_partner가 actor다.


6.
"해야 합니다"
"요청해야 해요"
"승인이 필요합니다"

처럼 업무 절차상 필요한 내용은

requirement다.


7.
"제가 승인자라서요"

는 승인을 완료했다는 뜻이 아니다.

현재 역할 상태다.

event_type = status
status = 승인자


8.
"최종 승인이 있어야
제출 버튼이 눌립니다"

는 업무 제약이다.

constraint =
"최종 승인 전에는 제출 불가"


9.
"승인되면 제가 제출할게요"

에서

제출은 plan.

prerequisite =
"승인 완료"


10.
"승인되면 제출하고
접수 여부까지 확인할게요"

처럼 여러 행동이
동일 조건 이후 이루어진다면

각 Event에

prerequisite =
"승인 완료"

를 기록한다.


11.
"아마 연서영 매니저님일텐데"

에서 연서영은
확정 담당자가 아니다.

related_people에 넣고

certainty = uncertain

으로 둔다.


12.
단,

"아마 연서영 매니저님일텐데,
제가 확인해볼게요"

처럼

사람에 대한 추정과
화자의 확정적 행동 계획이
같이 존재하면

연서영의 certainty만 uncertain이고

화자의 "확인하겠다"는 Event 자체는
confirmed다.


13.
"구매팀에 요청해야해요"

는 구매팀에 이미 요청했다는 뜻이 아니다.

업무 절차상 요청 필요라는
requirement다.


14.
"회의 끝나고 확인할게요"

에서

회의는 subject가 아니다.

회의는 행동 시점이다.

확인 대상이 현재 문장만으로
명확하지 않다면
subject는 null로 둘 수 있다.


15.
"승인자 변경이 필요하면
제가 할 수 있을까요?"

는 승인자 변경 가능 여부에 관한
question이다.

실제로 변경 요청을 했다고
판단하면 안 된다.


16.
"오늘 오후 2시까지 제출할
발주 요청서 작성 끝났습니다"

에서

작성 완료와
제출 마감은 다른 정보다.

오늘 오후 2시는
작성 완료의 deadline이 아니다.


17.
"직접 변경은 안되고"

와 같은 표현은
직접 처리할 수 없다는
업무 제약을 의미한다.


18.
conversation_partner라는 이유만으로
recipient를 지정하지 않는다.


19.
메시지에 없는

업무
사람
완료 사실
수신자
권한
담당 확정
인계 수락

을 만들지 않는다.


20.
알 수 없는 값은 null.


설명하지 말고
JSON Schema 형식만 출력한다.
"""

    result = call_ollama(
        prompt
    )

    return result.get(
        "events",
        []
    )


# ==================================================
# 질문 정규화
# ==================================================

def normalize_question_events(
    events,
    evidence
):

    if "?" not in evidence:
        return events

    if not events:
        return []

    # 질문 Candidate에서는
    # 모델이 여러 허위 Event를 만드는 것을 억제
    first = events[0]

    first["event_type"] = "question"
    first["actor"] = None
    first["status"] = None
    first["prerequisite"] = None
    first["constraint"] = None

    return [first]


# ==================================================
# Python fallback
# ==================================================

def create_fallback_events(
    speaker,
    evidence
):

    fallback_events = []

    # ----------------------------------------------
    # "합계는 맞네요"
    # ----------------------------------------------

    match = re.search(
        r"([가-힣A-Za-z0-9_]+)는\s*맞네요",
        evidence
    )

    if match:

        subject = match.group(1)

        fallback_events.append({
            "subject": subject,
            "actor": speaker,
            "related_people": [],
            "action": "확인",
            "recipient": None,
            "event_type": "status",
            "status": "정상 확인",
            "time_scope": "current",
            "deadline_text": None,
            "prerequisite": None,
            "constraint": None,
            "certainty": "confirmed"
        })

    return fallback_events


# ==================================================
# 문장 안의 제출 Requirement 별도 생성
#
# 예:
#
# 오늘 오후 2시까지 제출할
# 발주 요청서 작성 끝났습니다.
#
# →
# Event 1: 작성 완료
# Event 2: 2시까지 제출 필요
# ==================================================

def create_submission_requirement(
    evidence,
    context_time_scope
):

    deadline = extract_deadline_text(
        evidence
    )

    if not deadline:
        return []

    has_submission = (
        "제출할" in evidence
        or "제출해야" in evidence
        or "제출 필요" in evidence
    )

    if not has_submission:
        return []

    return [
        {
            "subject": "제출",
            "actor": None,
            "related_people": [],
            "action": "제출 필요",
            "recipient": None,
            "event_type": "requirement",
            "status": None,
            "time_scope":
                context_time_scope
                or "current",
            "deadline_text": deadline,
            "prerequisite": None,
            "constraint": None,
            "certainty": "confirmed"
        }
    ]


# ==================================================
# 구조화 필드의 명백한 단순 오타 정규화
# evidence 원문은 절대 수정하지 않음
# ==================================================

def normalize_structured_text(value):
    if not isinstance(value, str):
        return value

    # 예: "ㅅ승인자 변경" -> "승인자 변경"
    # 한글 음절 바로 앞에 단독으로 붙은 자모만 보수적으로 제거
    return re.sub(
        r"(?<![가-힣ㄱ-ㅎㅏ-ㅣ])([ㄱ-ㅎㅏ-ㅣ])(?=[가-힣])",
        "",
        value,
    )


# ==================================================
# Python 규칙 보정
# ==================================================

def apply_rules(
    event,
    speaker,
    partner,
    participants,
    evidence,
    context_time_scope
):

    corrections = []

    for field in ("subject", "action", "status"):
        original = event.get(field)
        normalized = normalize_structured_text(original)

        if normalized != original:
            event[field] = normalized
            corrections.append(
                f"{field}_obvious_typo_normalized"
            )


    # ==================================================
    # 1. 질문
    # ==================================================

    if "?" in evidence:

        event["event_type"] = (
            "question"
        )

        event["actor"] = None

        event["status"] = None

        event["prerequisite"] = None

        event["constraint"] = None

        corrections.append(
            "question_normalized"
        )


    # ==================================================
    # 2. 명확한 미래 행동 → plan
    #
    # "확인해볼게요"가 request로
    # 잘못 잡히는 문제 방지
    # ==================================================

    plan_markers = (
        "확인해볼게요",
        "확인할게요",
        "처리할게요",
        "제출할게요",
        "보낼게요",
        "드릴게요",
        "해볼게요",
        "하겠습니다",
        "할게요",
    )

    has_plan_marker = any(
        marker in evidence
        for marker in plan_markers
    )

    if (
        has_plan_marker
        and "?" not in evidence
    ):

        event["event_type"] = (
            "plan"
        )

        event["actor"] = speaker

        corrections.append(
            "explicit_future_action_to_plan"
        )


    # --------------------------------------------------
    # 미래에 전달/수령될 예정인 사건
    #
    # 화자의 직접 행동이라고 단정하지 않고
    # event_type만 plan으로 정규화한다.
    # --------------------------------------------------

    expected_future_markers = (
        "받을 예정",
        "받기로 예정",
        "전달될 예정",
        "전달 받을 예정",
        "전달받을 예정",
    )

    if (
        any(
            marker in evidence
            for marker in expected_future_markers
        )
        and "?" not in evidence
    ):

        event["event_type"] = (
            "plan"
        )

        corrections.append(
            "expected_future_event_to_plan"
        )


    # ==================================================
    # 3. 상대에게 하는 Request
    # ==================================================

    request_markers = (
        "부탁드려요",
        "부탁드립니다",
        "해주세요",
        "해 주세요",
        "기다려주세요",
        "기다려 주세요",
    )

    has_request_marker = any(
        marker in evidence
        for marker in request_markers
    )

    if (
        has_request_marker
        and not has_plan_marker
        and "?" not in evidence
    ):

        event["event_type"] = (
            "request"
        )

        if partner:

            event["actor"] = partner

            corrections.append(
                "request_actor_to_partner"
            )


    # ==================================================
    # 4. Requirement
    # ==================================================

    requirement_markers = (
        "해야 해서",
        "해야해서",
        "해야 합니다",
        "해야 해요",
        "해야해요",
        "해야 돼요",
        "해야 되",
        "요청해야",
        "필요합니다",
        "필요해요",
    )

    has_requirement = any(
        marker in evidence
        for marker in requirement_markers
    )

    if (
        has_requirement
        and not has_request_marker
        and not has_plan_marker
        and "?" not in evidence
    ):

        event["event_type"] = (
            "requirement"
        )

        actor = event.get(
            "actor"
        )

        # 근거 없는 actor 제거
        if (
            actor
            and actor not in evidence
        ):

            event["actor"] = None

            corrections.append(
                "unsupported_requirement_actor_removed"
            )


    # ==================================================
    # 5. 승인자 역할
    # ==================================================

    if (
        "제가 승인자" in evidence
        or "제가 승인자라서" in evidence
    ):

        event["event_type"] = (
            "status"
        )

        event["actor"] = speaker

        event["status"] = (
            "승인자"
        )

        corrections.append(
            "approver_role_normalized"
        )


    # ==================================================
    # 6. 승인 prerequisite
    # ==================================================

    prerequisite_markers = (
        "승인되면",
        "승인이 되면",
        "승인 완료 후",
        "승인 후",
    )

    if any(
        marker in evidence
        for marker in prerequisite_markers
    ):

        event["prerequisite"] = (
            "승인 완료"
        )

        corrections.append(
            "approval_prerequisite_added"
        )


    # --------------------------------------------------
    # 가정적 양보 표현은 prerequisite가 아님
    #
    # 예: "수정완료하셔도 QA에 1-2일 소요"
    # --------------------------------------------------

    concessive_markers = (
        "하셔도",
        "해도",
        "되어도",
        "돼도",
        "되더라도",
    )

    if (
        event.get("prerequisite")
        and event.get("event_type") == "status"
        and any(
            marker in evidence
            for marker in concessive_markers
        )
    ):

        event["prerequisite"] = None

        corrections.append(
            "concessive_not_prerequisite"
        )


    # ==================================================
    # 7. 승인 → 제출 시스템 제약
    # ==================================================

    if (
        "승인이 있어야" in evidence
        and (
            "제출 버튼" in evidence
            or "제출" in evidence
        )
    ):

        event["constraint"] = (
            "최종 승인 전에는 제출 불가"
        )

        corrections.append(
            "approval_submission_constraint_added"
        )


    # ==================================================
    # 8. 직접 변경/처리 불가 제약
    # ==================================================

    direct_change_block_markers = (
        "직접 변경은 안되고",
        "직접 변경은 안 되고",
        "직접 변경할 수 없",
        "직접 처리는 안되고",
        "직접 처리는 안 되고",
        "직접 처리할 수 없",
    )

    if any(
        marker in evidence
        for marker in direct_change_block_markers
    ):

        event["constraint"] = (
            "직접 변경 불가"
        )

        corrections.append(
            "direct_change_constraint_added"
        )


    # ==================================================
    # 9. 불확실성
    #
    # 사람에 대한 추정과
    # Event 자체의 불확실성을 분리
    # ==================================================

    uncertain_markers = (
        "아마",
        "아마도",
        "일텐데",
        "일 텐데",
        "것 같",
        "듯해",
        "듯 합니다",
    )

    is_uncertain = any(
        marker in evidence
        for marker in uncertain_markers
    )

    explicit_action_markers = (
        "할게요",
        "해볼게요",
        "확인할게요",
        "확인해볼게요",
        "하겠습니다",
        "했습니다",
        "했어요",
    )

    has_explicit_action = any(
        marker in evidence
        for marker in explicit_action_markers
    )

    related_people = event.get(
        "related_people",
        []
    )

    if is_uncertain:

        # 관련 인물의 확실성은 낮춤
        for person in related_people:

            person[
                "certainty"
            ] = "uncertain"

        # 하지만 화자의 행동 계획은
        # 확정적으로 말한 경우 confirmed
        if has_explicit_action:

            event["certainty"] = (
                "confirmed"
            )

            corrections.append(
                "related_person_uncertain_event_confirmed"
            )

        else:

            event["certainty"] = (
                "uncertain"
            )

            corrections.append(
                "event_uncertainty_detected"
            )

    else:

        event["certainty"] = (
            event.get(
                "certainty"
            )
            or "confirmed"
        )

        for person in related_people:

            if not person.get(
                "certainty"
            ):

                person[
                    "certainty"
                ] = "confirmed"


    # 추정 인물만 남고 status/action이 비어 있는
    # status Event는 의미가 사라지지 않도록
    # 보수적인 상태 문구만 채운다.
    if (
        event.get("event_type") == "status"
        and not event.get("status")
        and not event.get("action")
        and related_people
        and event.get("certainty") == "uncertain"
    ):
        names = ", ".join(
            person.get("name", "")
            for person in related_people
            if person.get("name")
        )

        if names:
            event["status"] = (
                f"{names} 관련 가능성"
            )

            corrections.append(
                "uncertain_related_person_status_filled"
            )


    # ==================================================
    # 10. 결과 상태를 decision으로 과승격하지 않기
    #
    # "일정 변경되어"처럼 변경 결과만 확인되고
    # 결정/확정 행위가 직접 명시되지 않으면 status.
    # ==================================================

    decision_markers = (
        "결정",
        "하기로",
        "확정",
        "픽스",
    )

    change_result_markers = (
        "변경되어",
        "변경되었",
        "변경됐",
        "바뀌었",
    )

    if (
        event.get("event_type") == "decision"
        and any(
            marker in evidence
            for marker in change_result_markers
        )
        and not any(
            marker in evidence
            for marker in decision_markers
        )
    ):

        event["event_type"] = "status"

        corrections.append(
            "change_result_decision_to_status"
        )


    # ==================================================
    # 11. 근거 없는 partner recipient 제거
    # ==================================================

    recipient = event.get(
        "recipient"
    )

    if (
        recipient
        and partner
        and recipient == partner
        and partner not in evidence
    ):

        event["recipient"] = None

        corrections.append(
            "unsupported_partner_recipient_removed"
        )


    # ==================================================
    # 11. 시간 범위
    # ==================================================

    event_type = event.get(
        "event_type"
    )

    explicit_scope = (
        detect_sentence_time_scope(
            evidence
        )
    )

    if event_type in (
        "plan",
        "request",
    ):

        normalized_scope = (
            "future"
        )

    elif event_type == "requirement":

        normalized_scope = (
            explicit_scope
            or context_time_scope
            or "current"
        )

    else:

        normalized_scope = (
            explicit_scope
            or context_time_scope
            or event.get(
                "time_scope"
            )
            or "unknown"
        )

    if (
        event.get(
            "time_scope"
        )
        != normalized_scope
    ):

        event[
            "time_scope"
        ] = normalized_scope

        corrections.append(
            "time_scope_normalized"
        )


    # ==================================================
    # 12. Deadline
    # ==================================================

    python_deadline = (
        extract_deadline_text(
            evidence
        )
    )

    # ----------------------------------------------
    # "2시까지 제출할 요청서"를 모델이
    # 근거 없이 "제출 예정" status로 만든 경우
    # requirement로 보수적으로 정규화
    # ----------------------------------------------

    if (
        python_deadline
        and "제출할" in evidence
        and "예정" not in evidence
        and event.get("event_type") == "status"
        and "예정" in (event.get("status") or "")
    ):
        event["event_type"] = "requirement"
        event["action"] = "제출 필요"
        event["status"] = None
        event["actor"] = None
        event["deadline_text"] = python_deadline

        corrections.append(
            "unsupported_submission_schedule_to_requirement"
        )

    # ----------------------------------------------
    # "2시까지 제출할 요청서 작성 완료"
    #
    # 작성 완료 Event에는
    # 제출 deadline을 붙이지 않음
    # ----------------------------------------------

    if (
        python_deadline
        and "제출할" in evidence
        and event.get(
            "event_type"
        ) == "completion"
        and "작성" in (
            event.get(
                "action"
            )
            or ""
        )
    ):

        event[
            "deadline_text"
        ] = None

        corrections.append(
            "submission_deadline_not_attached_to_creation"
        )

    elif python_deadline:

        # 이미 제출 requirement Event라면
        # 그대로 사용
        event[
            "deadline_text"
        ] = python_deadline


    # ==================================================
    # 13. Actor 유효성 검증
    #
    # "원이-than" 등 LLM 깨짐 방지
    # ==================================================

    actor = event.get(
        "actor"
    )

    if actor:

        actor_is_known = (
            actor in participants
            or actor in evidence
        )

        if not actor_is_known:

            first_person_markers = (
                "제가",
                "저는",
                "할게요",
                "해볼게요",
                "확인할게요",
                "확인해볼게요",
                "하겠습니다",
                "했습니다",
                "했어요",
            )

            is_first_person_action = any(
                marker in evidence
                for marker
                in first_person_markers
            )

            if (
                is_first_person_action
                and event.get(
                    "event_type"
                )
                in (
                    "plan",
                    "completion",
                    "progress",
                )
            ):

                event["actor"] = (
                    speaker
                )

                corrections.append(
                    "invalid_actor_replaced_with_speaker"
                )

            else:

                event["actor"] = None

                corrections.append(
                    "unsupported_actor_removed"
                )


    # ==================================================
    # 14. 기본값 보장
    # ==================================================

    if "prerequisite" not in event:

        event["prerequisite"] = (
            None
        )

    if "constraint" not in event:

        event["constraint"] = (
            None
        )

    if not event.get(
        "certainty"
    ):

        event["certainty"] = (
            "confirmed"
        )

    for person in event.get(
        "related_people",
        []
    ):

        if not person.get(
            "certainty"
        ):

            person[
                "certainty"
            ] = "confirmed"

    event[
        "rule_corrections"
    ] = corrections

    return event


# ==================================================
# Validation
# ==================================================

def validate_event(event):

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

    allowed_event_types = {
        "request",
        "requirement",
        "plan",
        "progress",
        "completion",
        "status",
        "question",
        "decision",
    }

    if (
        event.get(
            "event_type"
        )
        not in allowed_event_types
    ):

        errors.append(
            "invalid_event_type"
        )

    allowed_time_scopes = {
        "past",
        "current",
        "future",
        "unknown",
    }

    if (
        event.get(
            "time_scope"
        )
        not in allowed_time_scopes
    ):

        errors.append(
            "invalid_time_scope"
        )

    if event.get(
        "certainty"
    ) not in {
        "confirmed",
        "uncertain",
    }:

        errors.append(
            "invalid_certainty"
        )

    for person in event.get(
        "related_people",
        []
    ):

        if person.get(
            "certainty"
        ) not in {
            "confirmed",
            "uncertain",
        }:

            errors.append(
                "invalid_related_person_certainty"
            )

    return errors


# ==================================================
# 중복 제거
# ==================================================

def deduplicate_events(events):

    output = []
    seen = set()

    for event in events:

        related_people = event.get(
            "related_people",
            []
        )

        related_key = tuple(
            sorted(
                (
                    item.get(
                        "name",
                        ""
                    ),
                    item.get(
                        "role",
                        ""
                    ),
                    item.get(
                        "certainty",
                        ""
                    )
                )
                for item
                in related_people
            )
        )

        key = (
            event.get(
                "subject"
            ),
            event.get(
                "actor"
            ),
            event.get(
                "action"
            ),
            event.get(
                "recipient"
            ),
            event.get(
                "event_type"
            ),
            event.get(
                "status"
            ),
            event.get(
                "time_scope"
            ),
            event.get(
                "deadline_text"
            ),
            event.get(
                "prerequisite"
            ),
            event.get(
                "constraint"
            ),
            event.get(
                "certainty"
            ),
            related_key,
            event.get(
                "evidence"
            ),
        )

        if key in seen:
            continue

        seen.add(key)

        output.append(
            event
        )

    return output


# ==================================================
# MAIN
# ==================================================

def main():

    print(
        "SOURCE:",
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

    records = source_data[
        "records"
    ]

    participants = get_participants(
        records
    )

    print(
        "participants:",
        participants
    )

    all_results = []

    for record in records:

        source_id = record[
            "source_id"
        ]

        speaker = record[
            "speaker_label"
        ].strip()

        partner = infer_partner(
            speaker,
            participants
        )

        body = record[
            "body"
        ]

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

            context_time_scope = (
                candidate.get(
                    "context_time_scope"
                )
            )

            print()
            print(
                candidate_id,
                ":",
                evidence,
                "| context:",
                context_time_scope
            )

            # ======================================
            # 1. Ollama 분석
            # ======================================

            events = analyze_candidate(
                speaker=speaker,
                conversation_partner=partner,
                candidate_text=evidence,
                context_time_scope=context_time_scope
            )


            # ======================================
            # 2. 질문 정규화
            # ======================================

            events = normalize_question_events(
                events,
                evidence
            )


            # ======================================
            # 3. Python 추가 Event
            #
            # 문장 속 제출 deadline 보존
            # ======================================

            extra_events = (
                create_submission_requirement(
                    evidence=evidence,
                    context_time_scope=context_time_scope
                )
            )


            # ======================================
            # 4. LLM 누락 fallback
            # ======================================

            if not events:

                events = create_fallback_events(
                    speaker=speaker,
                    evidence=evidence
                )


            # ======================================
            # 5. 추가 Event 합치기
            # ======================================

            events.extend(
                extra_events
            )


            # ======================================
            # 6. Python 규칙 보정
            # ======================================

            for event in events:

                event = apply_rules(
                    event=event,
                    speaker=speaker,
                    partner=partner,
                    participants=participants,
                    evidence=evidence,
                    context_time_scope=context_time_scope
                )

                processed_event = {
                    "source_id":
                        source_id,

                    "candidate_id":
                        candidate_id,

                    "display_time":
                        record.get(
                            "display_time"
                        ),

                    "speaker":
                        speaker,

                    "conversation_partner":
                        partner,

                    "context_time_scope":
                        context_time_scope,

                    # 실제 원문
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

                    "time_scope":
                        event.get(
                            "time_scope"
                        ),

                    "deadline_text":
                        event.get(
                            "deadline_text"
                        ),

                    "prerequisite":
                        event.get(
                            "prerequisite"
                        ),

                    "constraint":
                        event.get(
                            "constraint"
                        ),

                    "certainty":
                        event.get(
                            "certainty"
                        ),

                    "rule_corrections":
                        event.get(
                            "rule_corrections",
                            []
                        ),

                    "validation_errors":
                        validate_event(
                            event
                        )
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


        # ==========================================
        # Event ID
        # ==========================================

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


        all_results.append({
            "source_id":
                source_id,

            "body":
                body,

            "candidates":
                candidates,

            "events":
                processed_events
        })


    # ==================================================
    # 저장
    # ==================================================

    RESULT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    final_output = {
        "version":
            "event-extraction-general-v4.4",

        "case_id":
            source_data.get(
                "case_id"
            ),

        "title":
            source_data.get(
                "title"
            ),

        "model":
            MODEL,

        "participants":
            participants,

        "source_file":
            str(
                SOURCE_PATH
            ),

        "message_count":
            len(records),

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
    