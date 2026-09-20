import csv
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'outputs'
dest = root / 'labeling'
dest.mkdir(exist_ok=True)
cases = [
    ('case_01', '보증마감', 'slack-mcp/collected/warranty.json', '원이정', '목요일 09:30', '본문의 업무 시각 사용. W001~W033은 해당 시점 이전 자료.'),
    ('case_02', 'SAP PR/PO', 'slack-mcp/collected/sap.json', '원이정', '화요일 14:00', '본문의 화요일 11시·13시 30분 대화 사용.'),
    ('case_03', '주간 정산표', 'backup-case-03/source.json', '원이정', '화요일 13:00', '오전 대화로 가정. 표시된 게시 시각과 분리.'),
    ('case_04', '발주 요청서', 'approval-case-04/source.json', '홍길동', '수요일 11:00', '수요일 오전 10시 대화로 가정. 표시된 게시 시각과 분리.'),
    ('case_05', '월간 실적 보고서', 'dependency-case-05/source.json', '원이정', '당일 16:00', '분석자가 제안한 부재 설정. 이번 사례만 표시된 15:43~15:45를 업무 시각으로 간주.'),
    ('case_06', '교육자료', 'training-material-case-06/source.json', '원이정', '월요일 13:00', '월요일 오전 대화로 가정. 표시된 게시 시각과 분리.'),
]
parts = ['# 평가용 원문 모음\n\n재현·가상 사례. 부재는 실험 설정이며 복귀 시점은 모두 미상이다. 개별 업무의 우선순위를 판단한다. 아래에는 우선순위 정답이나 분석 의견을 넣지 않았다.\n']
count = 0
for case_id, title, path, person, cutoff, note in cases:
    data = json.loads((root / path).read_text(encoding='utf-8-sig'))
    parts.append(f'\n## {case_id} — {title}\n\n부재자: {person} / 부재 시점: {cutoff}\n\n시각 처리: {note}\n')
    for record in data['records']:
        clock = record.get('record_header', record.get('display_time', '미상'))
        parts.append(f'\n### {record["source_id"]} | {record["speaker_label"]}\n\n기록상 시각: {clock}\n\n{record["body"]}\n')
        count += 1
assert count == 64
(dest / 'conversations.md').write_text('\n'.join(parts), encoding='utf-8')
template = dest / 'answers-template.csv'
# Never overwrite filled-in evaluations on rerun.
if not template.exists():
    fields = ['reviewer_id','prior_exposure','case_id','task_name','label','reason','evidence_ids','unknowns','baseline_issue','absence_impact','next_check']
    with template.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in cases:
            writer.writerow({'case_id': row[0]})
with template.open(encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))
assert len(rows) >= 6
print('Evaluation packet ready: 6 scenarios, 64 source records. No labels generated.')
