import json
from pathlib import Path

dest = Path(__file__).resolve().parents[1] / 'outputs/dhc-project-07'
messages = [
('원이정',None,'매니저님~ 송영종 매니저님이 요청하신 DHC 분석 건 진행 상황 공유드려요.'),
('홍길동','오후 4:13','네 이정 매니저님. 제가 그날 미팅에 못들어가서요 혹시 10분 뒤에 시간되시면 옐로우 박스에서 간단히 설명해주세요'),
('원이정','오후 4:13','일단 A랑 B는 2025년 데이터로 돌려보고 검수까지 끝냈어요. 2026년 1분기 데이터도 적용해봤는데, 그쪽은 한 번 더 확인이 필요해요.'),
('홍길동','오후 4:13','그럼 ab 전부 끜난건 아니고 2025년 것만 끝난거죺'),
('원이정','오후 4:14','네네 2026년 1분기는 아직 검수완료로 보시면 돼요.'),
('홍길동','오후 4:14','아아 넵 D는 제가 할게요.'),
('홍길동','오후 4:14','A,B랑 rate 범위도 다르던데 그 부분 구분해야겠어요'),
('원이정','오후 4:15','맞아요. A, B는 6~8%고 D는 5~9%예요. D는 mapping도 달라서 따로 확인해야 해요.'),
('홍길동','오후 4:15','그리고 c는 안하는거 맞죠?'),
('원이정','오후 4:15','네, C는 지점 단위 평가라 이번 검증에서는 제외한다고 하셨어요. 현재 기준이랑 A, B, D만 비교하면 됩니다.'),
('홍길동','오후 4:15','아 네넵 2025,2026 같이 보고 기준 정하려나봐요'),
('원이정','오후 4:15','네~ 두 기간 결과 종합해서 보신다고 했어요. 우선 지금은 A, B의 2025년 검수까지 끝난 상태로 봐주시면 됩니다.'),
]
records = []
for i,(speaker,time,body) in enumerate(messages,1):
    records.append({'source_id':f'case_07_M{i:03}', 'speaker_label':speaker,
                    'scenario_role':'이형주' if speaker=='홍길동' else speaker,
                    'speaker_basis':'inferred from preceding context' if i==1 else 'continuation in paste' if i==7 else 'explicit pasted name',
                    'display_time':time,'body':body,'message_url':None,'slack_user_id':None})
source = {'case_id':'case_07','collection_method':'user_pasted_dm',
          'data_kind':'scripted_reconstruction_of_user_experience',
          'conversation_url':'https://app.slack.com/client/T0C264NEDRA/D0C35GEKD8C',
          'completeness':'pasted excerpt only; not independently verified',
          'role_mapping_basis':'previously agreed for case_07 only, not present in this pasted excerpt',
          'posting_date':None,'text_policy':'typos preserved; paste escapes and blockquote formatting normalized',
          'records':records}
scenario = {'case_id':'case_07','absent_person':'원이정',
            'dialogue_business_period':'가상 월요일 오전 10시', 'absence_cutoff':'가상 월요일 오전 11시',
            'time_basis':'previously proposed scenario; display times 16:13–16:15 are posting times',
            'absence_type':'갑작스러운 외근','return_time':None,'contact_unavailable':None,
            'priority_label':None,'split_group':'case_07',
            'evaluation_status':'Q1 status clarification pending',
            'future_outcome_policy':'User recollection that Lee later performed D is excluded from pre-absence input.'}
for name,value in [('source.json',source),('scenario.json',scenario)]:
    (dest/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
assert len(records)==12
assert records[4]['body']=='네네 2026년 1분기는 아직 검수완료로 보시면 돼요.'
print('Saved 12 DHC messages; conflicting statement preserved; case-specific role mapping recorded.')
