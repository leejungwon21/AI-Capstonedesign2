# AI Capstone - Slack 업무 추출 파이프라인

이 브랜치는 그래프/ML 코드와 합치기 전에 Slack -> Event -> Task -> Work 파이프라인만 남긴 정리본입니다.

## 구조

- `src/slack/collector.py`: Slack 데이터를 on-demand로 수집
- `src/luna_api.py`: GPT-5.6 Luna Responses API 공통 호출부
- `prompts/event_extraction.md`: Slack Message -> Event
- `prompts/event_to_task.md`: Event -> Task
- `prompts/task_to_work.md`: Task -> Work
- `docs/pipeline-contract.md`: 최신 데이터/ID/업데이트 규칙
- `evaluation/evaluate_grouping.py`: Gold 대비 Task/Work grouping Precision, Recall, F1

## 핵심 원칙

1. Slack 수집은 자동 polling이 아니라 사용자가 인수인계를 요청할 때만 실행한다.
2. 모델 입력에는 Gold Task/Work 이름, Gold ID, 정답 관계를 넣지 않는다.
3. 원문에 Task/Work 이름이 명시되면 우선 사용하고, 없으면 맥락에서 생성한다.
4. 같은 논리적 Task/Work는 이후 실행에서도 기존 ID를 유지한다.
5. Slack 메시지 수정은 기존 Event 업데이트로 처리한다.
6. Task 상태 변경은 같은 task_id를 유지하고 status_history에 기록한다.
7. 사람은 slack_id + name을 함께 저장하고 동일인 판정은 slack_id 기준으로 한다.
8. deadline은 원문 표현과 YYYY-MM-DD 정규화 값을 함께 저장한다.

과거 실험 예시, 수동 Luna 결과, 가상환경, pycache, 특정 case 전용 생성 스크립트는 백업 브랜치
`backup/pre-cleanup-event-extraction-20260926`에 보존되어 있습니다.
