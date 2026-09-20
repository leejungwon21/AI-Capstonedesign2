import json
from pathlib import Path

dest = Path(__file__).resolve().parents[1] / 'outputs/dependency-case-05'
dest.mkdir(exist_ok=True)
messages = [
('홍길동','오후 3:43','이정님, 오늘 고객사에 월간 실적 보고서 보내야하는데요, 혹시 최종 매출 집계 파일 언제 받을 수 있을까요? 오후 5시전까지 가능할까요?'),
('원이정','오후 3:43','중복 거래 3건 확인 중이에요. 정리해서 오후 5시까지 공유폴더에 올릴게요. 지금 있는 파일은 수정 전이라 사용하면 안 돼요.'),
('홍길동','오후 3:44','네네, 최종 집계가 있어야 실적 그래프랑 보고서 금액을 수정할 수가 있어서요 ㅠ 그 작업만 한시간이라ㅠㅠ'),
('원이정','오후 3:44','보고서 발송 마감은 몇 시예요?'),
('홍길동','오후 3:44','오후 6시예요. 제가 수정한 뒤 팀장님 검토도 받아야해서요! 검토는 6시쯤 받기로했어요'),
('원이정','오후 3:44','네, 중복 거래 확인 끝나면 최종 파일 경로 보내드릴게요. 최대한 빨리하고 말씀 드리겠습니다. 죄송해요'),
('홍길동','오후 3:45','알겠습니다. 보고서 틀은 만들어뒀고, 숫자랑 그래프즌 최종 파일 받은 뒤 반영하려고 합니다!'),
('홍길동','오후 3:45','그럼 이따 연락주세요 고생하십쇼'),
]
records = [{'source_id': f'case_05_M{i:03}', 'speaker_label': s, 'display_time': t, 'body': b,
            'speaker_basis': 'continuation of previous speaker in paste' if i == 8 else 'explicit pasted name',
            'message_url': None, 'slack_user_id': None} for i,(s,t,b) in enumerate(messages,1)]
source = {'case_id':'case_05','collection_method':'user_pasted_dm','data_kind':'scripted_synthetic_dialogue_posted_by_two_accounts',
          'conversation_url':'https://app.slack.com/client/T0C264NEDRA/D0C35GEKD8C',
          'source_url_basis':'user browser context, not independently verified',
          'completeness':'pasted excerpt only; not verified against Slack',
          'posting_date':None,'text_policy':'typos preserved; paste formatting and trailing whitespace normalized',
          'records':records}
scenario = {'case_id':'case_05','absent_person':'원이정','absence_cutoff':'same day 16:00',
            'cutoff_basis':'assistant-proposed assumption after receiving revised dialogue; not a message fact',
            'business_date':None,'dialogue_time_basis':'for this experiment only, treat displayed 15:43–15:45 as same-day business times',
            'supersedes':'earlier draft morning dialogue and 10:00 absence; revised dialogue controls deadlines',
            'priority_label':None,'split_group':'case_05'}
tasks = [
 {'id':'T1','name':'중복 거래 확인 및 최종 집계 공유','owner':'원이정','status':'in_progress_reported','source_ids':['case_05_M002','case_05_M006']},
 {'id':'T2','name':'보고서 숫자·그래프 수정','owner':'홍길동','status':'waiting_for_final_aggregate','source_ids':['case_05_M003','case_05_M007']},
 {'id':'T3','name':'팀장 검토','owner':'팀장(이름 미상)','status':'scheduled_reported','source_ids':['case_05_M005']},
 {'id':'T4','name':'고객사 발송','owner':None,'status':'completion_unverified','source_ids':['case_05_M001','case_05_M005']},
]
edges = [{'from':'T1','to':'T2','type':'precedes','basis':'explicit','source_ids':['case_05_M003']},
         {'from':'T2','to':'T3','type':'precedes','basis':'explicit','source_ids':['case_05_M005']},
         {'from':'T3','to':'T4','type':'precedes','basis':'inferred_from_review_requirement','source_ids':['case_05_M005']}]
review = {'provenance':'assistant-reviewed annotation; no automatic extraction or ML run',
          'tasks':tasks,'relations':edges,
          'time_constraints':[
              {'task':'T1','kind':'personal_target','time':'17:00','source_ids':['case_05_M002']},
              {'task':'T2','kind':'estimated_duration','minutes':60,'source_ids':['case_05_M003']},
              {'task':'T3','kind':'approximate_appointment','time':'around 18:00','source_ids':['case_05_M005']},
              {'task':'T4','kind':'reported_deadline','time':'18:00','source_ids':['case_05_M005']}],
          'unknowns':['대체 담당자','실제 파일 위치 및 권한','팀장 검토 소요 시간','최종 발송 담당자 확정','부재 시점의 최신 처리 상태'],
          'baseline_concern':'If final data arrives at 17:00 and edits take one hour, no time remains before the 18:00 deadline for review/send. This exists without absence.',
          'absence_concern':'Loss of the aggregate owner may further delay dependent work; delay length is unknown.'}
for filename, value in [('source.json',source),('scenario.json',scenario),('review.json',review)]:
    (dest/filename).write_text(json.dumps(value, ensure_ascii=False, indent=2),encoding='utf-8')
allowed = {r['source_id'] for r in records}
assert len(allowed) == 8
assert all(set(x['source_ids']) <= allowed for x in tasks + edges + review['time_constraints'])
print('Saved case 05: 8 messages, 4 tasks, 3 dependencies. Revised deadlines and assumed 16:00 absence recorded.')
