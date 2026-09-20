"""No API calls. Hand-reviewed SAP facts -> graph -> absence check.

This fixture is a development example, not model predictions or training data.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    data = json.loads((ROOT.parent / 'slack-mcp/collected/sap.json').read_text(encoding='utf-8-sig'))
    sources = {r['source_id']: r['url'] for r in data['records']}
    nodes = [
        {'id': name, 'type': 'person'}
        for name in ['원이정', '이혜정', '이휘태', '정상환', '마충렬']
    ] + [
        {'id': 'WP1 승인', 'type': 'task', 'status': 'completed_reported', 'source_ids': ['S002', 'S004']},
        {'id': 'WP2 승인', 'type': 'task', 'status': 'completed_reported', 'source_ids': ['S002', 'S004']},
        {'id': 'MIGO 처리', 'type': 'task', 'status': 'planned_completion_unverified', 'source_ids': ['S005']},
        {'id': '서류 제출', 'type': 'task', 'status': 'planned_completion_unverified', 'source_ids': ['S005', 'S006']},
    ]
    edges = [
        {'from': '이휘태', 'to': 'WP1 승인', 'type': 'approver', 'source_ids': ['S002']},
        {'from': '정상환', 'to': 'WP2 승인', 'type': 'approver', 'source_ids': ['S002']},
        {'from': '원이정', 'to': 'MIGO 처리', 'type': 'works_on', 'source_ids': ['S005']},
        {'from': '원이정', 'to': '서류 제출', 'type': 'works_on', 'source_ids': ['S005']},
        {'from': 'MIGO 처리', 'to': '서류 제출', 'type': 'precedes', 'source_ids': ['S005']},
        {'from': '서류 제출', 'to': '마충렬', 'type': 'recipient', 'source_ids': ['S005']},
    ]
    ids = {node['id'] for node in nodes}
    for edge in edges:
        assert edge['from'] in ids and edge['to'] in ids
        assert set(edge['source_ids']) <= sources.keys()
    absent = '원이정'
    affected = [edge['to'] for edge in edges if edge['from'] == absent and edge['type'] == 'works_on']
    graph = {
        'provenance': 'Manually reviewed fixture; no automatic LLM extraction or ML inference.',
        'cutoff': '화요일 오후 2시', 'absent_person': absent,
        'nodes': nodes, 'edges': edges, 'sources': sources,
        'directly_affected_tasks': affected,
        'limitations': ['No risk score or trained model.', 'Backup availability is unknown.',
                        'Reported completion is not verified in SAP.',
                        'Small illustrative graph, not exhaustive extraction.'],
    }
    (ROOT / 'offline-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    report = '''# 결제 없는 SAP 공백 실험

## 실험 방식
대화에서 검토해 정리한 정보를 Python에 예시 데이터로 넣었다. Python은 담당자와 업무의 연결을 따라 공백 시 확인할 업무를 찾는다. API 호출, 자동 대화 추출, 학습된 ML 모델은 사용하지 않았다.

## 화요일 오후 2시, 원이정이 갑자기 부재한다면

| 확인 대상 | 대화상 상태 | 인수자가 확인할 내용 |
|---|---|---|
| MIGO 처리 | 처리하겠다는 계획만 있음 | 실제 처리 여부와 수행 가능한 담당자 |
| 서류 제출 | 퇴근 전 제출하겠다는 계획만 있음 | 마충렬 수령 여부, 미제출 시 서류 정렬 순서 |

두 업무 모두 S005에서 원이정과 직접 연결된다. 완료 여부가 없으므로 반드시 미완료라고 단정하지 않는다. 대체 담당자가 없다고도 단정하지 않는다.

WP1·WP2 승인은 S004에서 이미 완료됐다고 보고됐다. 다시 승인 대기 업무로 안내하지 않는다. PO번호는 이혜정이 메일로 보냈다고 했지만, 실제 번호와 메일 원문은 입력에 없다.

## 이 실험에서 확인한 것
- 대화에서 정리한 정보를 사람–업무 그래프로 표현할 수 있다.
- 부재자의 업무 연결을 따라 확인 대상을 찾을 수 있다.
- 위험 순위의 정확성이나 자동 추출 성능을 검증한 것은 아니다.

## 다음 단계
보증마감 사례도 공백 시점 이전 메시지만 사용해 같은 형식으로 정리한다. 이후 여러 독립 사례와 평가 기준을 준비한 뒤 ML 학습·평가를 진행한다. 이 두 사례만으로 ML 성능을 주장하지 않는다.
'''
    (ROOT / 'offline-report.md').write_text(report, encoding='utf-8')
    print(f'Offline demo complete: {len(nodes)} nodes, {len(edges)} edges; {len(affected)} tasks to check. No API used.')


if __name__ == '__main__':
    main()
