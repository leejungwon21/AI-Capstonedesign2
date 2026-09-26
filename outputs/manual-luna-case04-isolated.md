# Manual GPT-5.6 Luna experiment — case_04 / isolated

Use a **separate new chat** with GPT-5.6 Luna for each block below.
Do not show Luna the other messages.

Common instructions for every block:

너는 한국어 회사 업무 대화에서 업무 사건(Event)을 구조화하는 분석기다.
오직 아래에 주어진 한 메시지만 보고 Event를 추출한다.
메시지에 없는 사실을 만들지 않는다.
질문만으로 상태를 확정하지 않는다.
알 수 없는 값은 null.
단순 인사/감사만 있으면 events=[].
설명하지 말고 JSON만 출력한다.

출력 형식:
{
  "events": [
    {
      "source_id": "string",
      "subject": "string | null",
      "actor": "string | null",
      "related_people": [
        {
          "name": "string",
          "role": "string | null",
          "certainty": "confirmed | uncertain"
        }
      ],
      "action": "string | null",
      "recipient": "string | null",
      "event_type": "request | requirement | plan | progress | completion | status | question | decision",
      "status": "string | null",
      "time_scope": "past | current | future | unknown",
      "deadline_text": "string | null",
      "prerequisite": "string | null",
      "constraint": "string | null",
      "certainty": "confirmed | uncertain",
      "evidence": "string"
    }
  ]
}

Rules:
- "할게요/하겠습니다/확인해볼게요" → plan
- "끝났습니다/확인했어요" → completion 또는 status
- "부탁드립니다/해주세요/기다려주세요" → request
- "해야 합니다/필요합니다" → requirement
- "제가 승인자라서요"는 승인 완료가 아니라 역할 status
- "승인이 있어야 제출 가능" → constraint
- "승인되면 제출" → prerequisite="승인 완료"
- 추정 인물은 related_people, certainty=uncertain
- speaker라는 이유만으로 actor로 지정하지 않는다

---

BLOCK 1
source_id: case_04_M001
speaker: 원이정
message:
길동님, 오늘 오후 2시까지 제출할 발주 요청서 작성 끝났습니다. 금액이랑 첨부 견적서도 확인했어요. 최종 승인 부탁드립니다.

BLOCK 2
source_id: case_04_M002
speaker: 홍길동
message:
네 오전 회의 끝나고 확인할게요. 아직 승인 전이라 제출은 조금만 기다려주세요!!

BLOCK 3
source_id: case_04_M003
speaker: 원이정
message:
넵 시스템에서 제가 제출하려고 했더니 최종 승인이 있어야 제출 버튼이 눌려지네요

BLOCK 4
source_id: case_04_M004
speaker: 홍길동
message:
맞아요 이번 요청서는 제가 승인자라서요

BLOCK 5
source_id: case_04_M005
speaker: 원이정
message:
혹시 ㅅ승인자 변경이 필요하면 제가 할 수 있을까요?

BLOCK 6
source_id: case_04_M006
speaker: 홍길동
message:
직접 변경은 안되고 구매팀에 요청해야해요. 아마 연서영 매니저님일텐데, 변경 처리에 얼마나 걸리는 지 확인해볼게요

BLOCK 7
source_id: case_04_M007
speaker: 원이정
message:
네 알겠습니다. 만약 승인되면 제가 제출하고 접수 여부까지 확인할게요
