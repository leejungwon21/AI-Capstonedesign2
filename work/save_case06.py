import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'outputs'
dest = root / 'training-material-case-06'
dest.mkdir(exist_ok=True)
messages = [
    ('원이정', '오후 3:48', '다음 주 금요일까지 제출할 교육자료 초안 공유폴더에 올렸어요. 목차랑 본문은 끝났고, 최신 화면 캡처 두 장만 바꾸면 됩니다.'),
    ('홍길동', '오후 3:48', '파일 확인했어요. 캡쳐할 위치도 문서에 적혀있네요 이번주 먼저 필요한 곳은 없나요?'),
    ('원이정', '오후 3:49', '네 교육은 다다음 주라 이번 주에 자료 기다리는 업무는 없어요. 검토는 다음 주 수요일에 받기로했습니다'),
    ('홍길동', '오후 3:49', '알겠습니다 지난번 자료도 제가 수정했는데 이번에도 같은 양식이네요'),
    ('원이정', '오후 3:49', '네 아직 캡쳐는 교체하지 않았고, 제가 작업할때 문서에 적힌 두 화면만 바꾸면 돼요'),
]
records = [{'source_id': f'case_06_M{i:03}', 'speaker_label': s, 'display_time': t,
            'body': b, 'message_url': None, 'slack_user_id': None}
           for i, (s, t, b) in enumerate(messages, 1)]
source = {
    'case_id': 'case_06', 'collection_method': 'user_pasted_dm',
    'data_kind': 'scripted_synthetic_dialogue_posted_by_two_accounts',
    'conversation_url': 'https://app.slack.com/client/T0C264NEDRA/D0C35GEKD8C',
    'source_url_basis': 'user browser context; not independently verified',
    'completeness': 'pasted excerpt only; not verified against Slack',
    'posting_date': None, 'identity_basis': 'pasted display names only',
    'text_policy': 'typos preserved; paste formatting normalized', 'records': records,
}
scenario = {
    'case_id': 'case_06', 'absent_person': '원이정',
    'dialogue_business_period': '월요일 오전, 정확한 시각 미상',
    'absence_cutoff': '월요일 13:00', 'return_time': None,
    'basis': 'previously proposed fictional scenario; not extracted from displayed posting times',
    'timestamp_policy': '15:48–15:49 are posting times, not simulated business times',
    'priority_label': None, 'split_group': 'case_06',
}
for filename, value in [('source.json', source), ('scenario.json', scenario)]:
    (dest / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
assert len(records) == len({r['source_id'] for r in records}) == 5
assert scenario['priority_label'] is None
for path in [
    root / 'slack-mcp/collected/warranty.json', root / 'slack-mcp/collected/sap.json',
    root / 'backup-case-03/source.json', root / 'approval-case-04/source.json',
    root / 'dependency-case-05/source.json', dest / 'source.json',
]:
    assert path.is_file(), path
    json.loads(path.read_text(encoding='utf-8-sig'))
print('Case 06 saved: 5 messages. Source JSON files for all 6 cases verified.')
