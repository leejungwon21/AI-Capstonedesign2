"""Build reviewed work items and a deterministic handover checklist. No API/ML."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    p = ROOT / 'dhc-project-07/source.json'
    source = json.loads(p.read_text(encoding='utf-8-sig'))
    record = next(r for r in source['records'] if r['source_id'] == 'case_07_M005')
    corrected = '네네 2026년 1분기는 아직 검수완료로 보시면 안 돼요.'
    if record['body'] != corrected:
        record['original_body'] = record['body']
        record['body'] = corrected
        record['correction_basis'] = '사용자가 채팅에서 오타 정정 요청. Slack 메시지 수정 여부는 미확인.'
    p.write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding='utf-8')
    p = ROOT / 'dhc-project-07/scenario.json'
    scenario = json.loads(p.read_text(encoding='utf-8-sig'))
    scenario['evaluation_status'] = 'Q1 typo corrected by user; priority label pending'
    p.write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding='utf-8')

    # Fields are human-reviewed annotations, not automatic message extraction.
    # owner means known execution owner, never inferred from seniority alone.
    specs = [
        ('01','보증마감','slack-mcp/collected/warranty.json','원이정','목요일 09:30',[
            ('invoice','세금계산서 취합','원이정','partial_reported',['W031','W032'],[], '목요일 11시','이혜정','team_coverage_rule','최신 회신·연락 시점·금액 검증 여부')]),
        ('02','SAP PR/PO','slack-mcp/collected/sap.json','원이정','화요일 14:00',[
            ('migo','MIGO 처리','원이정','completion_unverified',['S005'],[],None,None,None,'실제 처리 여부'),
            ('submit','마충렬에게 제출','원이정','completion_unverified',['S005','S006'],['migo'],'화요일 퇴근 전 개인 목표',None,None,'제출 여부·서류 순서')]),
        ('03','주간 정산표','backup-case-03/source.json','원이정','화요일 13:00',[
            ('upload','정산표 업로드','원이정','not_done_at_last_message',['case_03_M003','case_03_M005'],[],'화요일 15시','홍길동','candidate_experience','현재 완료 여부·후보 가용 시간·권한'),
            ('mail','회계팀 완료 메일','원이정','not_done_at_last_message',['case_03_M003'],['upload'],'화요일 15시','홍길동','candidate_experience','발송 여부·수신 주소')]),
        ('04','발주 요청서','approval-case-04/source.json','홍길동','수요일 11:00',[
            ('approve','최종 승인','홍길동','pending_reported',['case_04_M002','case_04_M004'],[],None,None,None,'최신 승인 여부·구매팀 승인자 변경 절차'),
            ('submit','요청서 제출','원이정','waiting',['case_04_M003','case_04_M007'],['approve'],'수요일 14시',None,None,'승인 후 제출 및 접수 확인')]),
        ('05','월간 실적 보고서','dependency-case-05/source.json','원이정','당일 16:00 (가정)',[
            ('aggregate','최종 집계 공유','원이정','in_progress',['case_05_M002','case_05_M006'],[],'17시 개인 목표',None,None,'중복 거래 확인 상태·작업 파일'),
            ('edit','숫자·그래프 수정','홍길동','waiting',['case_05_M003','case_05_M007'],['aggregate'],None,None,None,'集計 도착 시각·수정 약 1시간'.replace('集計','집계')),
            ('review','팀장 검토','팀장(이름 미상)','scheduled',['case_05_M005'],['edit'],'18시쯤 예정',None,None,'검토 소요 시간·18시 발송 일정 조정')]),
        ('06','교육자료','training-material-case-06/source.json','원이정','월요일 13:00',[
            ('capture','화면 캡처 두 장 교체','원이정','not_done_at_last_message',['case_06_M001','case_06_M005'],[],'다음 주 수요일 검토·금요일 제출','홍길동','candidate_experience','최신 작업 상태·권한·일정')]),
        ('07','DHC 분석','dhc-project-07/source.json','원이정','월요일 11:00 (가상)',[
            ('ab25','A·B 2025년 검수','원이정','completed_reported',['case_07_M003','case_07_M012'],[],None,None,None,'완료 결과 참고'),
            ('ab26','A·B 2026 Q1 재검수','원이정','review_needed',['case_07_M003','case_07_M005'],[],None,None,None,'재검수 담당·파일 위치·완료 여부'),
            ('d','D 시나리오 분석','이형주','accepted_not_completed',['case_07_M006'],[],None,None,None,'수행 의사 확인됨. 최신 진행·검수 여부')]),
    ]
    all_cases = []
    report = ['# 공백 시 확인할 업무 — 통합 실행 결과\n',
              '사람이 정리한 업무 데이터를 Python 규칙으로 처리했다. 자동 추출·ML 예측·우선순위 점수는 아니다. 업무 상태는 마지막 대화 기준이며 부재 시점의 최신 상태는 재확인한다.\n',
              '직접 담당 업무와 명시된 선행 작업에 연결된 후속 업무를 표시한다. 이미 완료됐다고 보고된 업무는 확인 대상에서 제외한다. 업무 목록은 핵심 작업만 포함하며 전체 업무의 완전한 추출 결과가 아니다.\n']
    for num,title,path,absent,cutoff,rows in specs:
        raw = json.loads((ROOT/path).read_text(encoding='utf-8-sig'))
        evidence = {r['source_id'] for r in raw['records']}
        tasks = []
        for tid,name,owner,status,refs,deps,due,backup,basis,check in rows:
            assert set(refs) <= evidence
            tasks.append(dict(task_id=tid,name=name,owner=owner,status=status,source_ids=refs,
                              depends_on=deps,time_constraint_text=due,backup=backup,backup_basis=basis,
                              next_check=check,priority_label=None))
        ids = {t['task_id'] for t in tasks}
        assert all(set(t['depends_on']) <= ids for t in tasks)
        direct = {t['task_id'] for t in tasks if t['owner']==absent and t['status']!='completed_reported'}
        affected = set(direct)
        while True:
            new = {t['task_id'] for t in tasks if set(t['depends_on']) & affected and t['status']!='completed_reported'} - affected
            if not new: break
            affected.update(new)
        notes = []
        if num=='01': notes.append('イ혜정'.replace('イ','이')+' 대체 규정은 supplemental-context.json의 사용자 조직 정보. 실행·권한 확인과 별개.')
        if num=='03': notes.append('홍길동 후보 근거: case_03_M002, case_03_M004. 인계 수락이 아님.')
        if num=='06': notes.append('홍길동 후보 근거: case_06_M002, case_06_M004. 인계 수락이 아님.')
        if num=='05': notes.append('원래 일정에도 검토·발송 여유가 부족할 수 있음. 모든 일정 문제를 부재 효과로 간주하지 않음.')
        if num=='07': notes.append('D는 부재 전 이형주 역할이 수락. 이후 실제 D 수행 결과와 시점 불명의 A·B 재검수 인계 회고는 이번 원문 기준 입력에서 제외.')
        all_cases.append(dict(case_id=f'case_{num}',title=title,source_file=path,absent_person=absent,
                              cutoff=cutoff,tasks=tasks,affected_task_ids=sorted(affected),notes=notes))
        report += [f'\n## {num} {title}\n',f'부재 가정: {absent}, {cutoff}\n']
        for t in tasks:
            if t['task_id'] in affected:
                reason = '직접 담당' if t['task_id'] in direct else '후속 업무'
                coverage = f' / 대체: {t["backup"]} ({t["backup_basis"]})' if t['backup'] else ''
                report.append(f'- **{t["name"]}** ({reason}{coverage}): {t["next_check"]}. 근거: {", ".join(t["source_ids"])}\n')
        report.extend(f'\n{note}\n' for note in notes)
        if num == '07':
            handover = json.loads((ROOT / 'dhc-project-07/validated-handover.json').read_text(encoding='utf-8'))
            assert {item['task_id'] for item in handover['items']} <= ids
            all_cases[-1]['supplemented_handover'] = handover
            report.append('\n### 이형주에게 전달할 목록 — 사용자 추가 설명 포함\n')
            report.append(handover['cutoff_limitation'] + '\n')
            for item in handover['items']:
                report.append(f'- **{item["category"]}**: {item["description"]}\n')
    dest = ROOT/'integrated'
    dest.mkdir(exist_ok=True)
    (dest/'work-items.json').write_text(json.dumps({'provenance':'human-reviewed annotations; deterministic graph traversal; no ML', 'cases':all_cases},ensure_ascii=False,indent=2),encoding='utf-8')
    (dest/'handover-checklist.md').write_text('\n'.join(report),encoding='utf-8')
    dhc = all_cases[-1]
    assert dhc['affected_task_ids']==['ab26']
    assert set(all_cases[4]['affected_task_ids'])=={'aggregate','edit','review'}
    assert all(t['priority_label'] is None for c in all_cases for t in c['tasks'])
    print(f'Built {len(all_cases)} cases / {sum(len(c["tasks"]) for c in all_cases)} reviewed tasks. Evidence references and DHC/chain checks passed. No API calls.')


if __name__=='__main__':
    main()
