# Manual GPT-5.6 Luna experiment — case_04 / context

Use a **new chat** with GPT-5.6 Luna. Paste everything below in one message.

---

너는 한국어 회사 업무 대화에서 업무 사건(Event)을 구조화하는 분석기다.

## 목표

아래 Slack 대화 전체 문맥을 참고하되, 각 메시지에서 **원문으로 직접 뒷받침되는 업무 사실만** Event로 추출한다.

이 작업의 목적은 요약문 작성이 아니라, 이후 Task 통합에 사용할 수 있는 **근거 추적 가능한 Event 데이터**를 만드는 것이다.

## 최우선 원칙

1. **원문 보존**
   - evidence는 반드시 해당 source_id 메시지에 실제로 존재하는 원문 문장 또는 구절을 그대로 사용한다.
   - 원문을 요약하거나 표현을 바꿔서 evidence를 만들지 않는다.

2. **근거 없는 사실 생성 금지**
   - 메시지에 없는 업무 단계, 승인 절차, 권한, 담당자, 완료 사실, 수신자, 인계 수락을 만들지 않는다.
   - 상식적으로 그럴 것 같아도 원문 근거가 없으면 null 또는 uncertain으로 둔다.

3. **문맥은 해석에만 사용**
   - 앞뒤 메시지는 생략된 대상이나 대명사를 이해하는 데 참고할 수 있다.
   - 그러나 현재 source_id에 직접 근거가 없는 새로운 Event를 다른 메시지에서 끌어와 만들지 않는다.
   - 각 Event의 source_id와 evidence는 반드시 서로 일치해야 한다.

4. **상태와 행동을 구분**
   - "아직 승인 전", "승인자다", "제출 불가"처럼 현재 상황을 설명하는 것은 status다.
   - "제출할게요", "확인해볼게요", "승인 부탁드립니다"처럼 실제 수행/요청 행동은 plan 또는 request다.
   - 상태 설명을 억지로 새로운 실행 action으로 바꾸지 않는다.

5. **완료된 것과 남은 행동을 구분**
   - 이미 끝난 작성, 확인, 검토는 completion으로 기록한다.
   - 완료된 준비를 다시 해야 할 action처럼 만들지 않는다.

6. **불확실성 유지**
   - "아마", "~일 텐데", "것 같다" 등 추정은 확정 사실로 바꾸지 않는다.
   - 인물 추정은 related_people에 두고 그 사람의 certainty를 uncertain으로 둔다.
   - 문맥상 여러 해석이 가능하고 원문으로 확정할 수 없으면 값을 임의 선택하지 않는다.

7. **질문은 사실 확정이 아님**
   - 질문은 question이다.
   - 질문 내용만으로 실제 변경, 승인, 완료, 요청이 발생했다고 판단하지 않는다.

8. **단순 대화 제외**
   - 단순 인사, 감사, 감탄, 동의 표현만 있으면 Event를 만들지 않는다.

9. **한 메시지에 여러 사건 허용**
   - 한 메시지 안에 서로 다른 업무 사건이 여러 개 존재하면 여러 Event로 분리한다.
   - 단, 같은 사실을 중복 Event로 만들지 않는다.

## 필드 정의

- source_id: 직접 근거가 있는 원문 메시지 ID
- subject: 업무 대상
- actor: 실제 수행자 / 수행 예정자 / 요청을 받아 수행해야 하는 사람
- related_people: 관련 있지만 actor/recipient로 확정할 수 없는 사람
- action: 실제 업무 행동 또는 상태 변화
- recipient: 결과/문서를 실제로 전달받는 사람
- event_type: request | requirement | plan | progress | completion | status | question | decision
- status: 현재 상태가 원문에서 명확할 때만 기록
- time_scope: past | current | future | unknown
- deadline_text: 원문에 실제로 등장하는 업무 마감 표현
- prerequisite: 해당 행동 전에 먼저 충족되어야 하는 조건
- constraint: 시스템/권한/절차상 진행 제한
- certainty: Event 자체의 확실성
- evidence: 해당 Event를 직접 뒷받침하는 원문 구절

## 세부 판단 규칙

1. speaker라는 이유만으로 actor로 지정하지 않는다.
2. "하겠습니다", "할게요", "확인해볼게요", "확인할게요"처럼 화자가 앞으로 행동하겠다고 하면 plan이다.
3. "끝났습니다", "확인했어요", "저장했어요"처럼 이미 수행한 행동은 completion 또는 status다.
4. "해주세요", "부탁드립니다", "기다려주세요"처럼 상대에게 행동을 요구하면 request다.
5. "해야 합니다", "요청해야 해요", "승인이 필요합니다"처럼 절차상 필요한 내용은 requirement다.
6. "제가 승인자라서요"는 승인 완료가 아니라 역할 status다.
7. "최종 승인이 있어야 제출 버튼이 눌린다"는 constraint이며, 승인 완료 사실이 아니다.
8. "승인되면 제가 제출할게요"에서 제출 Event의 prerequisite는 "승인 완료"다.
9. "아마 연서영 매니저님일 텐데"처럼 담당자를 추정하는 표현은 담당 확정이 아니다.
10. conversation_partner라는 이유만으로 recipient를 지정하지 않는다.
11. "오늘 오후 2시까지 제출할 발주 요청서 작성 끝났습니다"에서:
    - 작성 완료는 completion
    - "오늘 오후 2시까지"는 제출 관련 시간 정보
    - 작성 완료의 deadline으로 잘못 붙이지 않는다.
12. "승인자 변경이 필요하면 제가 할 수 있을까요?"는 변경 가능 여부에 대한 question이며, 실제 변경 요청이나 변경 완료가 아니다.
13. "구매팀에 요청해야해요"는 구매팀에 이미 요청했다는 뜻이 아니라 requirement다.
14. "직접 변경은 안되고"는 직접 변경 불가 constraint다.
15. 알 수 없는 값은 null이다.
16. 오타가 있어도 원문을 임의 수정하지 말고 문맥상 확실한 범위에서만 해석한다.
17. 설명문, 평가, 요약을 쓰지 말고 JSON만 출력한다.

## 출력 전 자체 점검

각 Event마다 아래를 확인한다.

- source_id가 실제 메시지 ID인가?
- evidence가 해당 source_id의 원문에 정확히 포함되는가?
- 원문에 없는 actor/recipient/완료/승인을 만들어내지 않았는가?
- status와 action을 혼동하지 않았는가?
- 질문을 사실로 확정하지 않았는가?
- uncertain을 confirmed로 바꾸지 않았는가?
- 같은 사실을 중복 Event로 만들지 않았는가?

## 출력 형식

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

## Slack 대화

[case_04_M001] 원이정
길동님, 오늘 오후 2시까지 제출할 발주 요청서 작성 끝났습니다. 금액이랑 첨부 견적서도 확인했어요. 최종 승인 부탁드립니다.

[case_04_M002] 홍길동
네 오전 회의 끝나고 확인할게요. 아직 승인 전이라 제출은 조금만 기다려주세요!!

[case_04_M003] 원이정
넵 시스템에서 제가 제출하려고 했더니 최종 승인이 있어야 제출 버튼이 눌려지네요

[case_04_M004] 홍길동
맞아요 이번 요청서는 제가 승인자라서요

[case_04_M005] 원이정
혹시 ㅅ승인자 변경이 필요하면 제가 할 수 있을까요?

[case_04_M006] 홍길동
직접 변경은 안되고 구매팀에 요청해야해요. 아마 연서영 매니저님일텐데, 변경 처리에 얼마나 걸리는 지 확인해볼게요

[case_04_M007] 원이정
네 알겠습니다. 만약 승인되면 제가 제출하고 접수 여부까지 확인할게요
