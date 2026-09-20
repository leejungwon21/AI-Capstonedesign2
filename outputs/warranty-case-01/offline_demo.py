"""Reviewed facts -> graph and candidate features. No API or trained model."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build(data):
    records = data['records']
    expected = {f'W{i:03}' for i in range(1, 34)}
    if not data['complete'] or len(records) != 33 or {r['source_id'] for r in records} != expected:
        raise ValueError('Only the reviewed 33-message pre-absence snapshot is supported.')
    sources = {r['source_id']: r['url'] for r in records}
    # Manually reviewed facts, not machine-extracted predictions.
    tasks = [
        {'id': 'debit 수신', 'status': 'received_reported', 'sources': ['W016']},
        {'id': 'stage8 수정 및 발송', 'status': 'completed_reported', 'sources': ['W012', 'W013', 'W014']},
        {'id': '보증마감 내역 발송', 'status': 'completed_reported', 'sources': [f'W{i:03}' for i in range(17, 26)]},
        {'id': '세금계산서 취합', 'status': 'partial_as_of_0900', 'sources': [f'W{i:03}' for i in range(26, 34)]},
    ]
    dealers = ['한독', '코오롱', '도이치', '동성', '내쇼날', '바바리안', '삼천리']
    nodes = [{'id': p, 'type': 'person'} for p in ['원이정', '이혜정', '이재영']]
    nodes += [{'id': d, 'type': 'organization'} for d in dealers]
    nodes += [dict(t, type='task') for t in tasks]
    edges = [
        {'from': '원이정', 'to': t['id'], 'type': 'works_on', 'sources': t['sources']}
        for t in tasks
    ]
    edges += [{'from': d, 'to': '세금계산서 취합', 'type': 'requested_supplier', 'sources': [f'W{i:03}']}
              for d, i in zip(dealers, range(19, 26))]
    edges += [{'from': '이혜정', 'to': '세금계산서 취합', 'type': 'coordinates', 'sources': ['W031', 'W033']}]
    received = {r['speaker_label'].split(' → ')[0] for r in records if r['source_id'] in {f'W{i:03}' for i in range(26, 31)}}
    missing = [d for d in dealers if d not in received]
    # Requested deadline Thu 11:00 minus assumed absence Thu 09:30.
    features = {'task': '세금계산서 취합', 'deadline_remaining_hours': 1.5,
                'requested_supplier_count': len(dealers), 'received_supplier_count': len(received),
                'unreceived_supplier_count_as_of_0900': len(missing),
                'observed_owner_count': sum(e['type'] == 'works_on' and e['to'] == '세금계산서 취합' for e in edges),
                'backup_available': None, 'documentation_available': None,
                'amount_validation_complete': None, 'priority_label': None}
    ids = {n['id'] for n in nodes}
    assert all(e['from'] in ids and e['to'] in ids and set(e['sources']) <= expected for e in edges)
    return {'provenance': 'Human-reviewed development fixture, not ML output.',
            'cutoff': '마감 주 목요일 09:30', 'absent_person': '원이정',
            'nodes': nodes, 'edges': edges, 'candidate_features': features,
            'unreceived_suppliers_as_of_0900': missing, 'sources': sources}


def main():
    data = json.loads((ROOT.parent / 'slack-mcp/collected/warranty.json').read_text(encoding='utf-8-sig'))
    graph = build(data)
    (ROOT / 'offline-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'offline-report.md').write_text('''# 보증마감 공백 실험

가정: 원이정이 마감 주 목요일 09:30에 갑자기 부재한다. W001~W033만 사용했다. 대화를 검토해 입력한 사실을 Python으로 연결한 실험이며, 자동 추출이나 ML 예측은 아니다.

## 먼저 인계할 업무: 세금계산서 취합

- 요청 마감: 목요일 11시. 가정한 부재 시점에서 1시간 30분 남음(W019~W025).
- 09시까지 수신 보고: 코오롱·도이치·동성·내쇼날·삼천리, 5개사(W026~W030).
- 09시 미회신 보고: 한독·바바리안, 2개사(W032). 09시 이후 도착 여부는 다시 확인해야 한다.
- 이혜정의 직전 지시: 조금 더 기다리기(W033). 즉시 독촉을 확정 지시로 만들지 않는다.
- 다음 담당자가 확인할 사항: 최신 수신 여부, 파일 위치와 접근 권한, 받은 파일의 금액 검증 여부. 이후 연락 시점은 이혜정과 협의한다.

## 이미 진행된 일

| 업무 | 확인된 상태 |
|---|---|
| debit 수신 | 월요일 수신 확인(W016) |
| stage8 total 오류 | 수정 후 재검수 승인, 발송 회고 있음(W012~W014) |
| 보증마감 파일 | 작업·검수·수식 제거 후 7개사 발송 기록(W017~W025) |

원본 파일은 제공되지 않았다. 수신 보고를 파일 검증 완료로 해석하지 않는다. 모빌리티 자료 반영 여부 등 일부 사항은 미확인이다. 이 그래프는 핵심 흐름의 일부이며 전체 업무 목록이 아니다.

## ML 입력 준비 결과

마감까지 1.5시간 / 요청 7개사 / 수신 5개사 / 미회신 2개사 / 기록상 실행 담당자 1명.
대체 담당자·문서 존재·금액 검증 여부는 미상(null)이다. 미상을 없음(0)으로 바꾸지 않는다. 기록상 담당자 1명이 실제로 유일하게 수행 가능한 사람이라는 뜻도 아니다.

위 우선 확인 제안은 사람이 작성한 판단이다. 위험 확률이나 모델 예측으로 표시하지 않는다. 목요일 10시 요청, 11시 완료, 금요일 보험사 전달은 입력에 없으며 사용하지 않았다.
''', encoding='utf-8')
    print('Offline warranty complete: 33 source records; 5 received, 2 outstanding as of 09:00; no API or ML run.')


if __name__ == '__main__':
    main()
