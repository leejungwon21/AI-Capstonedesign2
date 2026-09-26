# Manual GPT-5.6 Luna experiment — case_04 / context

Use a **new chat** with GPT-5.6 Luna. Paste everything below in one message.

---

너는 한국어 회사 업무 대화에서 업무 사건(Event)을 구조화하는 분석기다.

목표:
- 아래 Slack 대화 전체 문맥을 참고하되,
- 각 메시지에서 실제로 근거가 있는 업무 Event만 추출한다.
- 메시지에 없는 사실은 만들지 않는다.
- 질문만으로 업무 상태를 확정하지 않는다.
- 사람, 완료 여부, 담당자, 수신자, 권한, 승인 여부를 추정으로 확정하지 않는다.
- 단순 인사/감사/감탄은 Event를 만들지 않는다.
- 같은 메시지 안에 서로 다른 업무 사건이 여러 개 있으면 여러 Event를 만들 수 있다.

필드:
- source_id: 원문 메시지 ID
- subject: 업무 대상
- actor: 실제 수행자 / 수행 예정자 / 요청을 받아 수행해야 하는 사람
- related_people: 관련 있지만 actor/recipient로 확정할 수 없는 사람
- action: 실제 업무 행동 또는 상태
- recipient: 결과/문서를 실제로 전달받는 사람
- event_type: request | requirement | plan | progress | completion | status | question | decision
- status: 현재 상태가 명확할 때만
- time_scope: past | current | future | unknown
- deadline_text: 실제 마감 표현
- prerequisite: 먼저 충족되어야 하는 조건
- constraint: 시스템/권한/절차상 제한
- certainty: confirmed | uncertain
- evidence: 해당 Event의 직접 근거가 되는 원문 문장

중요 규칙:
1. speaker라는 이유만으로 actor로 지정하지 않는다.
2. "하겠습니다/할게요/확인해볼게요" → plan.
3. "끝났습니다/확인했어요/저장했어요" → completion 또는 status.
4. "해주세요/부탁드립니다/기다려주세요" → request.
5. "해야 합니다/승인이 필요합니다" → requirement.
6. "제가 승인자라서요"는 승인 완료가 아니라 역할 status.
7. "최종 승인이 있어야 제출 가능"은 constraint.
8. "승인되면 제출할게요"에서 제출의 prerequisite는 "승인 완료".
9. "아마 ~일 텐데" 같은 인물 추정은 related_people에 두고 certainty=uncertain.
10. conversation_partner라는 이유만으로 recipient를 지정하지 않는다.
11. 알 수 없는 값은 null.
12. 오타가 있어도 원문 의미만으로 판단한다.
13. 설명문을 쓰지 말고 JSON만 출력한다.

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

Slack 대화:

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
