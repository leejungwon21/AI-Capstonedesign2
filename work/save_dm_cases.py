import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'outputs'
common = {
    'collection_method': 'user_pasted_dm',
    'data_kind': 'scripted_synthetic_dialogue_posted_by_two_accounts',
    'conversation_url': 'https://app.slack.com/client/T0C264NEDRA/D0C35GEKD8C',
    'source_url_basis': 'user browser context; not independently verified',
    'identity_basis': 'display names in user paste; Slack user IDs unavailable',
    'timestamp_policy': 'Displayed times are posting times, not simulated business times. Posting date unknown.',
    'completeness': 'pasted excerpt only; not verified against Slack',
    'excluded_event': {'speaker': '홍길동', 'display_time': '오후 3:29', 'text': 'Slack에 가입했습니다. 시간을 내어 인사해 보세요.', 'reason': 'workspace join notice, not work conversation'},
}
cases = [
    ('backup-case-03', 'case_03', '주간 정산표', '화요일 오전, 정확한 시각 미상', '화요일 13:00', '원이정', [
        ('원이정','오후 3:30','길동님, 지난주 정산표 업로드할 때 오류 없었어요? 이번 주 건 오늘 오후 3시까지 회계팀에 제출해야 해서요.'),
        ('홍길동','오후 3:30','네 지난주에눈 문제 없었어요. 제가 업로드하고 회계팀에 완료 메일 보냈습니다'),
        ('원이정','오후 3:30','감사합니다. 이번 주 건은 금액 대사 끝났고, 공유폴더에 `주간정산_최종.xlsx`로 저장했어요. 아직 업로드랑 완료 메일은 안 했어요.'),
        ('홍길동','오후 3:31','방금 열어봤는데 합계는 맞네요. 제출 방법은 지난주 쓴 문서 참고해주세요'),
        ('원이정','오후 3:31','네, 점심 먹고 처리할게요.'),
    ]),
    ('approval-case-04', 'case_04', '発주 요청서'.replace('発','발'), '수요일 오전 10시 대화', '수요일 11:00', '홍길동', [
        ('원이정','오후 3:36','길동님, 오늘 오후 2시까지 제출할 발주 요청서 작성 끝났습니다. 금액이랑 첨부 견적서도 확인했어요. 최종 승인 부탁드립니다.'),
        ('홍길동','오후 3:36','네 오전 회의 끝나고 확인할게요. 아직 승인 전이라 제출은 조금만 기다려주세요!!'),
        ('원이정','오후 3:37','넵 시스템에서 제가 제출하려고 했더니 최종 승인이 있어야 제출 버튼이 눌려지네요'),
        ('홍길동','오후 3:37','맞아요 이번 요청서는 제가 승인자라서요'),
        ('원이정','오후 3:37','혹시 ㅅ승인자 변경이 필요하면 제가 할 수 있을까요?'),
        ('홍길동','오후 3:37','직접 변경은 안되고 구매팀에 요청해야해요. 아마 연서영 매니저님일텐데, 변경 처리에 얼마나 걸리는 지 확인해볼게요'),
        ('원이정','오후 3:38','네 알겠습니다. 만약 승인되면 제가 제출하고 접수 여부까지 확인할게요'),
    ]),
]
for folder, case_id, title, period, cutoff, absent, messages in cases:
    dest = OUT / folder
    dest.mkdir(exist_ok=True)
    records = [{'source_id': f'{case_id}_M{i:03}', 'speaker_label': speaker, 'display_time': time,
                'body': body, 'slack_user_id': None, 'message_url': None}
               for i, (speaker, time, body) in enumerate(messages, 1)]
    source = {**common, 'case_id': case_id, 'title': title, 'records': records,
              'segmentation_basis': 'topic boundary reviewed manually; no case markers in pasted messages',
              'text_policy': 'typos preserved; paste escape characters and trailing whitespace normalized'}
    (dest / 'source.json').write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding='utf-8')
    scenario = {'case_id': case_id, 'dialogue_business_period': period, 'absence_cutoff': cutoff,
                'absent_person': absent, 'basis': 'previously agreed fictional scenario, not inferred from Slack timestamps',
                'priority_label': None, 'label_status': 'not independently annotated', 'split_group': case_id}
    (dest / 'scenario.json').write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding='utf-8')
    assert len(records) == (5 if case_id == 'case_03' else 7)
    assert len({r['source_id'] for r in records}) == len(records)
print('Saved 2 cases: 5 + 7 work messages. No API calls. Posting times separated from scenario times.')
