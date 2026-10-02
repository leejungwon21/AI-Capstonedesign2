# Pipeline Contract

## 1. 단계

Slack Message -> Event -> Task -> Work -> Graph

- Event: Slack 원문으로 직접 뒷받침되는 최소 업무 사실
- Task: 같은 구체적 업무 목표를 공유하는 Event 묶음
- Work: 같은 상위 업무 목적을 공유하는 Task 묶음

Graph/ML은 이 파이프라인 이후 단계다.

## 2. 수집 방식

초기 구현은 on-demand 방식이다.

사용자 요청 -> Slack 수집 -> Event 추출/업데이트 -> 기존 Task/Work 매칭 -> 변경분 저장

자동 polling은 사용하지 않는다.

## 3. ID 규칙

- 새 Event: 새 event_id
- 기존 Slack 메시지가 수정된 경우: 기존 Event를 업데이트한다. 단순 edit만으로 새 Event를 만들지 않는다.
- 새 Event가 기존 Task와 관련 있으면 기존 task_id에 추가한다.
- 관련 없으면 새 task_id를 생성한다.
- 같은 논리적 Work면 기존 work_id를 유지한다.
- 채널/DM이 다르다는 이유만으로 Task를 분리하지 않는다.

ID는 저장소/후처리 계층에서 안정적으로 관리한다. LLM이 Gold ID를 보고 맞히는 방식으로 평가하지 않는다.

## 4. Task 관련성 판정

다음 신호를 함께 본다.

- 같은 업무 목적
- 같은 대상/문서/이슈
- 같은 기간/회차
- 자연스러운 선행/후속 흐름
- 참여자 연결
- 파일/참조/대명사 연결

키워드가 같다는 이유만으로 병합하지 않는다. 애매한 경우 과병합보다 분리를 우선하고 certainty=uncertain으로 남긴다.

## 5. Task/Work 이름

- 원문/Event/Task에 공식 업무명이 명시되어 있으면 그 표현을 우선 사용한다.
- 이름이 명시되어 있지 않으면 묶인 하위 항목의 공통 목적과 행동을 바탕으로 생성한다.
- Gold Answer의 제목을 모델 입력에 제공하지 않는다.

## 6. 사람

사람은 다음 두 값을 함께 보관한다.

- slack_id: 시스템 식별 및 동일인 매칭 기준
- name: 화면 표시 및 디버깅

이름만으로 동일인을 판정하지 않는다.

## 7. 날짜

업무 날짜는 다음 구조를 사용한다.

```json
{
  "deadline": {
    "text": "내일까지",
    "at": "2026-10-03"
  }
}
```

- at은 YYYY-MM-DD
- 상대 날짜 해석 기준은 해당 Slack 메시지의 작성 시각(Asia/Seoul)
- 단일 날짜로 확정할 수 없으면 at=null
- audit timestamp(slack_ts, changed_at)는 원래 timestamp 정밀도를 유지한다.

## 8. Task 상태 변경

같은 task_id를 유지하면서 현재 status를 갱신하고 변경 이력을 남긴다.

```json
{
  "task_id": "TASK-00017",
  "status": "in_progress",
  "status_history": [
    {
      "from": "waiting",
      "to": "in_progress",
      "changed_at": "2026-10-02T21:10:00+09:00"
    }
  ]
}
```

## 9. 데이터 누수 방지

모델 입력 금지:
- Gold Event/Task/Work ID
- Gold Task/Work 이름
- Gold grouping 관계
- 정답을 암시하는 파일 경로/URL

예: 원문 URL에 `WORK-00005`가 포함되어 있으면 모델 입력용 text에서는 링크를 제거하거나 중립화한다.

Gold는 평가 단계에서만 로드한다.

## 10. 평가

대표 지표:
- Event: Precision / Recall / F1, 필드별 정확도
- Event -> Task: pairwise grouping Precision / Recall / F1
- Task -> Work: pairwise grouping Precision / Recall / F1
- status: Accuracy
- deadline.at: Exact Match
- slack_id: Accuracy

오류 유형도 함께 기록한다.
- Event 누락/과추출
- Task 과병합/과분리
- Work 과병합/과분리
- status/date/person/prerequisite/constraint 오류
