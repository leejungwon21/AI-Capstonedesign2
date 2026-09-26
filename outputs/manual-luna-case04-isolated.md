# Manual GPT-5.6 Luna experiment — case_04 / isolated

Use a **separate new chat** with GPT-5.6 Luna for each block below.
For each run, paste the common instructions plus exactly one BLOCK.
Do not show Luna any of the other Slack messages.

---

## Common instructions

너는 한국어 회사 업무 대화에서 업무 사건(Event)을 구조화하는 분석기다.

### 목표
아래 Slack 메시지 하나만 보고, **원문으로 직접 뒷받침되는 업무 사실만** Event로 추출한다.
이 결과는 이후 Task 통합에 사용되므로 요약보다 근거 추적 가능성이 중요하다.

### 핵심 원칙
1. evidence는 해당 source_id 원문에 실제 존재하는 문장/구절을 **그대로** 사용한다.
2. evidence의 오타·띄어쓰기는 고치지 않는다.
3. subject/action/status 같은 구조화 필드는, 같은 메시지만으로 의도가 명백한 단순 오타일 때만 정상 표현으로 정규화할 수 있다.
4. 오타 때문에 의미가 애매하면 추측하지 말고 null 또는 uncertain으로 둔다.
5. 메시지에 없는 업무 단계, 승인, 권한, 담당자, 완료, 수신자, 인계 수락을 만들지 않는다.
6. 현재 메시지 외의 다른 Slack 문맥은 사용하지 않는다.
7. 상태(status)와 실제 행동(plan/request/completion 등)을 구분한다.
8. 질문은 question이며, 질문 내용만으로 실제 변경·승인·완료·요청을 확정하지 않는다.
9. 질문 속 가정 조건("~필요하면", "~된다면")을 실제 prerequisite로 확정하지 않는다.
10. "아마", "~일 텐데", "것 같다" 같은 추정은 확정 사실로 바꾸지 않는다.
11. 단순 인사·감사·감탄·동의만 있으면 Event를 만들지 않는다.
12. 한 메시지에 서로 다른 업무 사건이 여러 개 있으면 여러 Event로 분리하되 중복 생성하지 않는다.

### 필드
- source_id: 원문 메시지 ID
- subject: 업무 대상
- actor: 행동 수행자/예정자/요청받은 수행자. 역할·상태 Event에서는 그 역할·상태의 명시적 주체
- related_people: 관련 있으나 actor/recipient로 확정할 수 없는 사람
- action: 실제 업무 행동 또는 상태 변화
- recipient: 결과/문서/요청을 실제로 전달받는 대상
- event_type: request | requirement | plan | progress | completion | status | question | decision
- status: 원문에서 명확한 현재 상태
- time_scope: past | current | future | unknown
- deadline_text: 실제 마감 표현만 기록
- prerequisite: 해당 행동 전에 반드시 충족되어야 한다고 원문에서 명시된 조건
- constraint: 시스템/권한/절차상 진행 제한
- certainty: confirmed | uncertain
- evidence: Event를 직접 뒷받침하는 원문

### 판단 규칙
- "할게요/하겠습니다/확인해볼게요" → plan
- "끝났습니다/확인했어요/저장했어요" → completion 또는 status
- "해주세요/부탁드립니다/기다려주세요" → request
- "해야 합니다/요청해야 해요/승인이 필요합니다" → requirement
- "제가 승인자입니다/담당자입니다" 같은 자기 역할 선언 → status, actor=speaker
- "승인이 있어야 제출 가능" → constraint이며 승인 완료 사실이 아님
- "승인되면 제출할게요" → 제출 plan, prerequisite="승인 완료"
- "~후/끝나고"는 행동 시점/선행조건이지 deadline이 아님
- 마감 표현이 앞으로 해야 할 행동을 수식할 뿐 명시적 실행 약속이 없으면, 이를 "예정" status나 plan으로 만들지 않는다. 필요하면 actor=null인 requirement로 기록한다.
- 질문 속 가정 조건은 prerequisite로 만들지 않는다.
- 상대가 누구인지 현재 메시지만으로 알 수 없으면 actor/recipient를 임의로 채우지 않는다.
- 명백한 단순 오타는 구조화 필드에서만 정규화 가능하며 evidence는 원문 그대로 둔다.
  - 예: "ㅅ승인자 변경"의 의미가 명백하면 subject="승인자 변경" 가능, evidence는 원문 그대로 유지

### 출력 전 점검
- evidence가 source_id 원문에 그대로 포함되는가?
- 원문에 없는 사실을 만들지 않았는가?
- 단순 마감 표현을 "예정"이나 plan으로 과해석하지 않았는가?
- "~후/끝나고"를 deadline으로 잘못 넣지 않았는가?
- 질문 속 가정을 prerequisite로 확정하지 않았는가?
- status와 action을 혼동하지 않았는가?
- 오타 정규화가 같은 메시지만으로 명백한가?

### 출력 형식
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

설명문 없이 JSON만 출력한다.

---

## BLOCK 1
source_id: case_04_M001
speaker: 원이정
message:
길동님, 오늘 오후 2시까지 제출할 발주 요청서 작성 끝났습니다. 금액이랑 첨부 견적서도 확인했어요. 최종 승인 부탁드립니다.

## BLOCK 2
source_id: case_04_M002
speaker: 홍길동
message:
네 오전 회의 끝나고 확인할게요. 아직 승인 전이라 제출은 조금만 기다려주세요!!

## BLOCK 3
source_id: case_04_M003
speaker: 원이정
message:
넵 시스템에서 제가 제출하려고 했더니 최종 승인이 있어야 제출 버튼이 눌려지네요

## BLOCK 4
source_id: case_04_M004
speaker: 홍길동
message:
맞아요 이번 요청서는 제가 승인자라서요

## BLOCK 5
source_id: case_04_M005
speaker: 원이정
message:
혹시 ㅅ승인자 변경이 필요하면 제가 할 수 있을까요?

## BLOCK 6
source_id: case_04_M006
speaker: 홍길동
message:
직접 변경은 안되고 구매팀에 요청해야해요. 아마 연서영 매니저님일텐데, 변경 처리에 얼마나 걸리는 지 확인해볼게요

## BLOCK 7
source_id: case_04_M007
speaker: 원이정
message:
네 알겠습니다. 만약 승인되면 제가 제출하고 접수 여부까지 확인할게요
