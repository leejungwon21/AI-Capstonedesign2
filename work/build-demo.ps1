$ErrorActionPreference = 'Stop'
$out = Join-Path (Get-Location) 'outputs/handover-demo'
New-Item -ItemType Directory -Force -Path "$out/input", "$out/evaluation" | Out-Null
$utf8 = New-Object System.Text.UTF8Encoding($false)
function Save($path, $value) { [IO.File]::WriteAllText((Join-Path $out $path), $value, $utf8) }
$people = @(
 @{id='P1';name='김지수';role='운영·고객 승인 담당'},
 @{id='P2';name='이민호';role='개발 담당'},
 @{id='P3';name='박서연';role='디자인 담당'},
 @{id='P4';name='최도윤';role='CRM 운영 담당'},
 @{id='P5';name='정하린';role='팀장'}
)
$specs = @'
[
 {"id":"T01","project":"캠페인 A","channel":"proj-campaign-a","name":"캠페인 소재 검수","owner":"김지수","backup":null,"due":"2026-09-18T12:00:00+09:00","status":"수정안 대기","deps":[],"priority":"즉시 대응","reason":"당일 마감이며 대체 검수자가 없고 테스트·본 발송의 선행 업무","messages":[["박서연","캠페인 A 수정 소재는 금요일 18일 10시에 전달 예정입니다. 아직 최종 파일은 아닙니다."],["김지수","제가 18일 정오까지 소재 검수할게요. 검수 기준은 문서 D01입니다. 이번 검수 대체자는 아직 없습니다."],["박서연","현재 수정 진행 중입니다. 최종본 전달 전에는 이전 시안을 발송에 쓰지 말아주세요."]]},
 {"id":"T02","project":"캠페인 A","channel":"proj-campaign-a","name":"테스트 발송","owner":"최도윤","backup":null,"due":"2026-09-18T15:00:00+09:00","status":"검수 대기","deps":["T01"],"priority":"즉시 대응","reason":"담당자는 남아 있지만 당일 테스트가 부재자의 검수에 의존","messages":[["최도윤","테스트 발송은 제가 맡습니다. 지수님 소재 검수가 끝나야 실행할 수 있어요."],["최도윤","테스트 완료 목표는 18일 15시입니다. 절차는 문서 D02에 적었습니다."],["정하린","검수 전 테스트 실행은 보류하세요. 검수가 늦어지면 발송 일정 조정 여부를 바로 판단해야 합니다."]]},
 {"id":"T03","project":"캠페인 A","channel":"proj-campaign-a","name":"캠페인 본 발송","owner":"최도윤","backup":null,"due":"2026-09-18T17:00:00+09:00","status":"테스트 대기","deps":["T02"],"priority":"즉시 대응","reason":"당일 발송이 검수와 테스트 지연의 영향을 받음","messages":[["최도윤","본 발송은 18일 17시입니다. 테스트 통과 후 제가 실행합니다."],["김지수","타깃 고객 선정과 발송 일정 합의는 완료했습니다. 이번 캠페인은 기존 고객 재구매 안내입니다."],["최도윤","발송 도구 접근 권한은 제 계정에 있습니다. 테스트를 통과하지 않으면 본 발송하지 않겠습니다."]]},
 {"id":"T04","project":"캠페인 A","channel":"proj-campaign-a","name":"캠페인 성과 보고","owner":"김지수","backup":"최도윤","due":"2026-09-25T17:00:00+09:00","status":"예정","deps":["T03"],"priority":"일반 대응","reason":"다음 주 마감이며 대체자가 수락했고 보고 절차가 있음","messages":[["김지수","성과 보고는 25일 17시까지입니다. 보고 양식은 D03으로 정리했습니다."],["최도윤","지수님 부재 시 성과 보고는 제가 대신 맡겠습니다. 집계 화면 권한도 확인했습니다."],["정하린","성과 보고는 실제 발송 후 집계하세요. 당일 긴급 대응 목록에는 넣지 않고 다음 주 진행 상황을 확인하겠습니다."]]},
 {"id":"T05","project":"캠페인 A","channel":"proj-campaign-a","name":"추가 고객 설문","owner":"김지수","backup":null,"due":null,"status":"진행 여부 미확인","deps":[],"priority":"확인 필요","reason":"제안만 있고 착수·마감·대체 담당자가 확정되지 않음","messages":[["김지수","캠페인 이후 추가 고객 설문을 하면 어떨까요? 질문안을 생각해보겠습니다."],["정하린","설문은 제안으로 접수할게요. 실제 진행 여부와 일정은 아직 정하지 않았습니다."],["최도윤","설문 후속 논의나 문서는 이 채널에서 아직 확인하지 못했습니다."]]},
 {"id":"T06","project":"결제 연동 B","channel":"proj-payment-b","name":"운영 인증키 승인","owner":"김지수","backup":null,"due":"2026-09-18T11:00:00+09:00","status":"승인 대기","deps":[],"priority":"즉시 대응","reason":"운영 승인 권한이 부재자에게만 있고 당일 연동 검증을 막음","messages":[["이민호","운영 인증키 요청을 등록했습니다. 18일 11시까지 내부 승인이 필요합니다."],["김지수","운영 인증키 내부 승인 권한은 현재 저에게만 있습니다. 아직 승인하지 않았고, 대체 승인자도 등록되지 않았습니다."],["정하린","승인 권한 변경은 제가 운영 지원 창구에 요청할 수 있습니다. 요청만으로 즉시 승인 권한이 생기는 것은 아닙니다."]]},
 {"id":"T07","project":"결제 연동 B","channel":"proj-payment-b","name":"결제 연동 검증","owner":"이민호","backup":null,"due":"2026-09-18T16:00:00+09:00","status":"인증키 승인 대기","deps":["T06"],"priority":"즉시 대응","reason":"당일 검증에 운영 인증키가 필요하고 승인자가 부재","messages":[["이민호","SDK 연동 코드는 작성했습니다. 운영 인증키가 승인되어야 운영 환경 검증이 가능합니다."],["이민호","연동 검증 마감은 18일 16시입니다. 테스트 항목은 D04에 있습니다."],["김지수","코드 작성 완료와 운영 검증 완료는 별개입니다. 현재 운영 검증은 시작하지 못했습니다."]]},
 {"id":"T08","project":"결제 연동 B","channel":"proj-payment-b","name":"결제 예외 처리 구현","owner":"이민호","backup":null,"due":"2026-09-22T17:00:00+09:00","status":"진행 중","deps":[],"priority":"일반 대응","reason":"부재자 승인 없이 독립 진행 가능하고 당일 마감이 아님","messages":[["이민호","타임아웃과 중복 결제 예외 처리는 제가 22일까지 구현합니다."],["이민호","이 작업은 모의 서버로 개발할 수 있어서 운영 인증키 승인과 독립적으로 진행 가능합니다."],["정하린","기존 합의된 요구사항대로 진행하세요. 이번 구현에 지수님 추가 승인은 필요하지 않습니다."]]},
 {"id":"T09","project":"결제 연동 B","channel":"proj-payment-b","name":"고객사 진행 상황 회신","owner":"김지수","backup":"정하린","due":"2026-09-18T14:00:00+09:00","status":"회신 준비","deps":[],"priority":"일반 대응","reason":"당일 마감이지만 대체자가 업무와 자료 접근을 확인함","messages":[["김지수","고객사 진행 상황 회신은 18일 14시까지입니다. 하린님을 대체 담당자로 부탁드립니다."],["정하린","수락합니다. 고객사 연락처와 이전 회신은 D05에서 확인했고 자료 접근도 됩니다."],["정하린","인증키 승인이 늦어져도 현재 상태를 그대로 회신할 수 있습니다. 검증 완료라고 쓰지 않겠습니다."]]},
 {"id":"T10","project":"결제 연동 B","channel":"proj-payment-b","name":"결제 FAQ 초안","owner":"김지수","backup":null,"due":null,"status":"최신 상태 미확인","deps":[],"priority":"확인 필요","reason":"초안 존재와 최신 위치·검토 상태를 확정할 수 없음","messages":[["김지수","결제 FAQ 초안을 작성 중입니다. 정리되면 공유하겠습니다."],["이민호","최신 FAQ 링크를 부탁드립니다. 지금 채널에서 확인 가능한 공유본은 못 찾았습니다."],["정하린","FAQ의 마감과 검토 담당자는 아직 확정하지 않았습니다. 초안이 없다고 단정하지 말고 위치부터 확인해야 합니다."]]}
]
'@ | ConvertFrom-Json
$messages = @(); $truth = @(); $index = 0
foreach ($task in $specs) {
  $sources = @()
  foreach ($m in $task.messages) {
    $index++
    $id = 'M{0:d3}' -f $index
    $sources += $id
    $ts = ([DateTimeOffset]::Parse('2026-09-17T10:00:00+09:00')).AddMinutes($index * 7).ToString('yyyy-MM-ddTHH:mm:sszzz')
    $messages += [ordered]@{source_id=$id;channel=$task.channel;timestamp=$ts;author=$m[0];text=$m[1];synthetic=$true}
  }
  $truth += [ordered]@{task_id=$task.id;name=$task.name;project=$task.project;owner=$task.owner;backup=$task.backup;deadline=$task.due;state=$task.status;depends_on=$task.deps;expected_triage=$task.priority;rationale=$task.reason;evidence_ids=$sources}
}
$docs = @(
 @{source_id='D01';title='캠페인 소재 검수 기준';text='최종 수정본의 대상 고객, 문구, 링크, 이미지를 확인한다. 과거 시안은 발송에 사용하지 않는다. 본 문서는 검수 기준이며 검수 완료 증거가 아니다.'},
 @{source_id='D02';title='테스트·본 발송 절차';text='최도윤이 실행한다. 소재 검수 완료 후 내부 테스트 계정으로 발송하여 링크와 이미지 표시를 확인한다. 테스트 통과 후 본 발송한다.'},
 @{source_id='D03';title='캠페인 성과 보고 양식';text='발송일, 발송 수, 클릭 수, 집계 기간, 특이사항을 기록한다. 현재 문서는 양식이며 실제 성과 수치는 아직 없다.'},
 @{source_id='D04';title='결제 연동 검증 항목';text='운영 인증키 승인 후 정상 결제와 취소를 확인한다. SDK 코드 작성과 운영 검증을 별도 상태로 관리한다.'},
 @{source_id='D05';title='가상 고객사 회신 메모';text='고객사: 가온상점(가상). 연락 창구: demo-customer@example.invalid. 회신 항목: 구현 상태, 운영 검증 상태, 다음 확인 일정. 김지수와 정하린이 열람 가능하다.'}
)
Save 'input/people.json' (ConvertTo-Json -InputObject $people -Depth 8)
Save 'input/messages.json' (ConvertTo-Json -InputObject $messages -Depth 8)
Save 'input/documents.json' (ConvertTo-Json -InputObject $docs -Depth 8)
$request = [ordered]@{scenario_id='S001';synthetic=$true;target_person='김지수';analysis_at='2026-09-18T09:00:00+09:00';absence_start='2026-09-18T09:00:00+09:00';expected_return=$null;triage_window_end='2026-09-18T18:00:00+09:00';instruction='김지수의 갑작스러운 부재에 대해 당일 대응할 업무를 분석한다. 복귀일은 모른다. 자료에 없는 내용은 확인 필요로 표시한다. 제공된 기록만 사용하고 주장마다 source_id를 제시한다.'}
Save 'input/request.json' ($request | ConvertTo-Json -Depth 8)
Save 'evaluation/answer-key.json' (ConvertTo-Json -InputObject $truth -Depth 8)
$post = @('# Slack 수동 게시용 가상 기록', '', '모든 인물·업무는 가상입니다. 각 블록을 해당 채널에 별도 메시지로 게시하세요.', '게시자는 실제 가상 직원 계정이 아닙니다. 원문 작성자와 기록 시각은 본문에 명시합니다.', '실제 Slack 게시 시각과 아래 가상 업무 시각은 다릅니다. 재생 실험에서는 본문 기록 시각을 사용하세요.', '평가용 answer-key.json은 게시하지 마세요.', '')
foreach ($m in $messages) { $post += @("## #$($m.channel) / $($m.source_id)", '', "[가상 기록 | $($m.timestamp) | 작성자: $($m.author) | source_id: $($m.source_id)]", $m.text, '') }
foreach ($d in $docs) { $post += @("## 문서 $($d.source_id): $($d.title)", '', $d.text, '') }
Save 'slack-posts.md' ($post -join "`n")
$readme = @'
# 갑작스러운 업무 공백: 첫 번째 테스트 데이터

전부 가상 데이터입니다. 실제 회사 정보는 사용하지 않았습니다.

## 시나리오
- 가상 회사: 온담랩. 직원 5명, 프로젝트 2개, 업무 후보 10개.
- 2026-09-18 09:00(KST), 김지수가 갑자기 부재. 복귀일 미정, 당사자에게 질문할 수 없음.
- 그날 18:00까지 우선 대응할 업무를 찾는 실험입니다.
- 자료는 전날까지의 기록입니다. 미래 예정 사항은 실제 완료 사실이 아닙니다.

## 지금 할 순서
1. 먼저 파일로 시험: `input`의 JSON 4개를 분석 AI에 제공하세요.
2. “업무별 현재 상태, 완료한 일, 남은 일, 즉시 대응/일반 대응/확인 필요, 판단 이유, 다음 행동, 출처를 정리하라”고 요청하세요.
3. 결과가 나온 뒤에만 `evaluation/answer-key.json`과 비교하세요.
4. Slack 테스트 워크스페이스에 `proj-campaign-a`, `proj-payment-b` 채널을 만드세요.
5. `slack-posts.md`의 블록을 각 채널에 게시하고 D01~D05 문서도 적절한 프로젝트 채널에 공유하세요.
6. 이후 MCP 수집 결과가 파일 입력 때와 같은 정보를 복원하는지 확인하세요.

## 파일 구분
- `input/`: 분석 프로그램에 제공할 자료. 정답 라벨은 포함하지 않습니다.
- `evaluation/answer-key.json`: 사람이 비교할 정답표. 분석 Agent·검색 인덱스·Slack에 넣지 마세요.
- `slack-posts.md`: 수동 게시용 텍스트. 아직 Slack에 게시되지 않았습니다.

## 정답 기준과 범위
- 즉시 대응: 당일 업무 연속성에 지장이 있어 담당/승인 재배정이나 일정 조정이 필요한 사례.
- 일반 대응: 현재 담당 또는 수락한 대체자가 진행 가능하며 당일 공백 대응이 우선되지 않는 사례.
- 확인 필요: 기록만으로 상태·마감을 확정할 수 없는 사례. 안전하다는 뜻이 아닙니다.
- T05는 확정 업무가 아니라 제안입니다. T10은 문서 부재가 아니라 최신 자료 미확인입니다.
- T09는 당일 마감이라도 대체자가 준비되어 있습니다. 마감만으로 위험을 판정하면 오답입니다.
- 예상 분류는 설계자가 만든 시나리오 판단이며 실제 사고 결과나 전문가 검증 라벨이 아닙니다.

## 평가 체크
- 업무/제안 구분, 완료와 예정 구분, 대체 담당자 반영, 후속 업무 영향, 모르는 정보의 표시를 확인합니다.
- 각 주장에 올바른 source_id가 붙었는지 확인합니다.
- 그래프의 DEPENDS_ON은 후행 업무 → 선행 업무 방향입니다.
- 이 데이터는 추출·연동 확인용입니다. ML 학습 성능을 보고할 규모나 독립성은 없습니다.
- 학습 실험에서는 독립적인 여러 프로젝트·부재 시나리오를 만들고 시나리오 단위로 학습/평가를 분리해야 합니다.
- Slack의 실제 메시지 ID·링크는 게시 후에 저장해야 합니다. 현재 source_id는 로컬 실험 식별자입니다.
- 이 버전은 짧고 정리된 대화입니다. 이후 스레드, 일정 변경, 중복 업무명, 관련 없는 대화를 추가해야 합니다.
'@
Save 'START-HERE.md' $readme
if ($messages.Count -ne 30 -or $truth.Count -ne 10 -or $people.Count -ne 5) { throw 'Unexpected counts' }
foreach ($t in $truth) {
 foreach ($id in $t.evidence_ids) { if ($id -notin $messages.source_id) { throw "Missing evidence $id" } }
 foreach ($id in $t.depends_on) { if ($id -notin $truth.task_id) { throw "Missing dependency $id" } }
}
foreach ($m in $messages) { if ([DateTimeOffset]::Parse($m.timestamp) -ge [DateTimeOffset]::Parse($request.analysis_at)) { throw 'Future message' } }
Get-ChildItem -Path $out -Recurse -Filter *.json | ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8 | ConvertFrom-Json | Out-Null }
Write-Output 'Validated: 5 people, 10 task candidates, 30 messages, 5 documents; references and cutoff checked.'
