# Slack 추출 → Supabase 연결

## 구성

- `src/pipeline.py`: 실제 Slack 메시지를 받아 Event → Task → Work 반환. Gold 파일을 읽지 않는다.
- `src/schemas.py`, `src/pipeline_context.py`: 서비스와 기존 평가 코드가 공유하는 스키마·맥락 처리.
- `src/deadlines.py`: 작성 시각 기준 KST 마감 계산, 날짜만 있는 경우 시간 추측 금지.
- `src/db.py`: 현재 5개 테이블용 변환·저장, DB만 읽어서 ML 그래프 생성.
- `scripts/sync_slack.py`: 저장 계획 생성, 저장된 동일 계획 적용, 저장 후 행 검증·그래프 생성.

표준 라이브러리만 사용한다. Python 3.10 이상. `.env.example`은 설정 이름 참고용이며 자동으로 읽지 않는다.
`OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`를 백엔드 프로세스의 환경변수로 설정한다.
Supabase 키를 프론트나 메시지 JSON에 넣지 않는다.

## 입력

기존 실험 envelope의 `people` + `messages` 또는 collector의 `records` + `people`을 받는다.
사람 객체는 `{slack_id, name}`. 메시지는 고유 `source_id`/`id`, `slack_ts`/`timestamp`,
`conversation_id`/`channel`, `slack_author_id`/`author_id`, `raw_text`/`text`가 필요하다.
ISO 작성 시각은 시간대를 포함하고, Slack 원본 `ts` 문자열도 그대로 받는다.

```json
{
  "people": [{"slack_id":"U01","name":"김지수"},{"slack_id":"U02","name":"이정"}],
  "messages": [{
    "id":"C01:1791608400.000001", "channel":"C01", "author_id":"U01",
    "timestamp":"2026-10-10T05:00:00Z",
    "text":"이정씨, 계약서 내일 오전 10시까지 주세요."
  }]
}
```

이 메시지의 마감은 `deadline_text="내일 오전 10시까지"`,
`due_at="2026-10-11T10:00:00+09:00"`이다. Task에는 같은 값을 `deadline_at`으로 저장한다.
날짜만 확정되면 추출 결과에는 날짜를 보존하고 DB timestamp는 null로 둔다.
정확한 날짜만의 DB 보존까지 필요하면 별도 date/precision 컬럼을 팀원과 합의해야 한다.

## 실행

```bash
python scripts/sync_slack.py --input messages.json --out handover_runs/run.json
python scripts/sync_slack.py --apply-plan handover_runs/run.json
```

첫 명령은 DB를 읽고 LLM을 호출하여 저장 계획을 만들지만 DB에 쓰지는 않는다.
두 번째 명령은 저장된 계획을 적용하며 LLM을 다시 호출하지 않는다.
적용 시 현재 DB와 계획 당시 snapshot fingerprint가 다르면 중단한다.
적용 후 모든 저장 대상 행을 읽어 확인하고 `handover_runs/run.graph.json`을 생성한다.

```bash
# 이전 실행의 상태 이력 유지
python scripts/sync_slack.py --input messages.json --prior-result handover_runs/run.json --out handover_runs/next.json
# LLM 없이 이미 추출한 서비스 결과를 연결
python scripts/sync_slack.py --result service_result.json --out handover_runs/import.json
# 키 없이 저장 형식 검증: DB snapshot JSON 제공
python scripts/sync_slack.py --result service_result.json --snapshot db_snapshot.json --out handover_runs/offline.json
python -m unittest discover -s tests -v
```

## 현재 DB와의 매핑

| 추출 | DB |
|---|---|
| people[].slack_id | persons.person_id |
| actor.name / actor.slack_id | events.actor / actor_id |
| recipient.name / recipient.slack_id | events.recipient / recipient_id |
| 메시지 작성자·채널·스레드 | speaker_id / conversation_id / parent_ts / slack_ts |
| deadline.text / deadline.at | deadline_text / due_at (Event), deadline_at (Task) |
| constraint + note | memo (내용은 추출 결과에 분리 보존) |
| 자료 URL들 | reference에 줄바꿈으로 보존 |
| prerequisite | 원문 조건을 현존 컬럼에 보존, 불명확한 관계는 생성하지 않음 |
| work.tasks / task.events | HAS_TASK / HAS_EVENT |
| Task participants | OWNER / APPROVER / REVIEWER / COLLABORATOR / RELATED |
| actor / requester / related_people | ACTOR / REQUESTER / RELATED (Person → Event) |

REQUESTER는 원문에서 확인한 실제 요청자다. 발화자를 무조건 REQUESTER로 만들지 않는다.
recipient 등의 ML에 없는 역할, Task 간 링크, 미해결 선행조건은 계획의 warnings와 원본 결과에 보존한다.
Event → Event DEPENDS_ON은 기존 DB 관계를 유지한다. 새로운 선행관계 해소 로직은 이 변경에 포함하지 않는다.

Relation 번호는 현재 graph 브랜치의 `export_graph.py`와 동일한 10종이다.
`HAS_TASK=0, HAS_EVENT=1, OWNER=2, APPROVER=3, REVIEWER=4, COLLABORATOR=5,
RELATED=6, ACTOR=7, REQUESTER=8, DEPENDS_ON=9`.
13종인 이전 Notion 표를 혼합하지 않는다. Node 번호는 `Person=0, Task=1, Work=2, Event=3`.
노드·관계 수는 고정하지 않는다. 그래프 전체는 DB 데이터만으로 생성한다.

## ID·갱신 규칙

- 새 Event/Task/Work ID는 UUID 기반으로 발급한다. 실험 순번을 운영 DB ID로 쓰지 않는다.
- 동일 메시지의 동일 사실은 ID를 유지한다. 단일 사실 수정은 기존 ID를 유지한다.
- 여러 사실 수정으로 대응이 모호하거나 사실이 제거되면 자동 저장을 멈춘다. 오연결·임의 삭제를 하지 않는다.
- 기존 Task/Work를 DB에서 읽어 LLM에 전달하고 반환한 기존 ID를 검사한다.
- nodes upsert 후 변경된 업무의 관계만 갱신하며 전체 edges를 지우지 않는다.
- 사람은 이름으로 자동 합치지 않는다. 같은 이름의 기존 PERSON-ID와 신규 Slack-ID가 있으면 적용을 멈춘다.
  동명이인일 수도 있으므로 DB 담당자가 신원 매핑과 기존 관계 전환을 먼저 확정해야 한다.
- 원문·전체 추출 결과·상태 이력은 `handover_runs` 계획에 보존한다. 원문·상태 이력용 DB 테이블은 별도 협의가 필요하다.

## 범위와 운영 조건

현재 DB에는 50 Persons / 104 Tasks / 26 Works / 312 Events / 1,766 Edges의 가상 데이터가 있다.
실제 Slack 사용자 ID로 자동 전환하지 않는다. 준비 결과의 identity_conflicts를 먼저 해결해야 한다.
REST의 테이블별 쓰기는 전체 트랜잭션이 아니다. 실패 시 일부 테이블만 저장될 수 있다.
적용 전 `.before.json`과 원본 계획을 보존하고, 실패 후 DB 상태를 확인해 새 계획을 생성한다.
실시간 처리 시 이 실행부를 단일 worker에서 직렬화해야 한다. 분산 동시 쓰기·트랜잭션 RPC는 별도 구현 대상이다.

최종 목표는 실시간 동기화다. `run_pipeline`은 수신 메시지 묶음용 진입점이다.
이 변경은 Slack Events API 웹훅 서버·OAuth·상시 worker 배포까지 구현하지 않는다.
collector는 초기 수집/복구용으로 유지한다. 현재 collector의 replies는 첫 페이지만 처리하므로
200개를 넘는 답글을 완전 수집하려면 별도 pagination 보완이 필요하다.

이 변경으로 연결용 코드와 오프라인 검증을 제공한다. 실제 API 키로 하는 LLM 호출과 DB 쓰기는
배포 환경에서 위 명령으로 검증해야 한다. 5개 public 테이블의 RLS가 꺼져 있으므로 프론트 공개 전 권한 정책을 설정한다.
