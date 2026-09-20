# 1단계: Slack → MCP 수집

## 현재 상태
수집기와 MCP 서버 코드 작성, 오프라인 테스트 4개 통과. Slack 앱 A0C3005NUHJ 생성·Bizineer 설치·두 실험 채널 추가 완료. 토큰 설정과 실제 수집은 아직 필요합니다. LLM 추출과 ML 모델은 아직 구현하지 않았습니다.

현재 PC에서는 `collect.cmd`를 실행하여 Bot User OAuth Token을 숨김 입력하면 `collected/warranty.json`, `collected/sap.json`으로 저장됩니다. 토큰은 파일에 저장하지 않습니다. 이 실행은 Slack API 직접 연결 확인용이며 MCP 프로토콜 실행과 구분합니다.

## Slack 설정
1. https://api.slack.com/apps 에서 Create New App → From a manifest.
2. Bizineer 선택 후 `slack_app_manifest.json` 내용을 입력합니다.
3. 생성 후 OAuth & Permissions → Install to Workspace. 요청 범위는 `channels:history` 하나입니다. 설치 권한이 없으면 관리자에게 요청합니다.
4. 두 채널의 채널 상세 → 에이전트 및 앱에서 Capstone Handover Reader를 추가합니다.
   - test-warranty-closing-01-public (C0C2ZSSC5GU)
   - test-sap-pr-po-02 (C0C3QGPCB0Q)
5. Bot User OAuth Token은 로컬 환경변수 SLACK_BOT_TOKEN으로만 설정합니다. 채팅·소스코드에 붙여넣지 않습니다.

봇은 자신이 추가된 채널의 기록에 접근합니다. 코드 역시 위 두 ID만 허용합니다. 현재 게시물은 모두 최상위 메시지입니다. 스레드가 발견되면 불완전 수집으로 보고하고, 추후 적절한 인증과 replies 수집을 구현해야 합니다.

## 실행 (Python 3.10 이상)
```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
python -m unittest -v test_collector.py
```

토큰을 표시하거나 파일에 저장하지 않고 현재 PowerShell 세션에 설정:
```powershell
$slackSecret = Read-Host 'Slack Bot User OAuth Token' -AsSecureString
$env:SLACK_BOT_TOKEN = [System.Net.NetworkCredential]::new('', $slackSecret).Password
Remove-Variable slackSecret
.\.venv\Scripts\python server.py
```

server.py는 일반 대화형 프로그램이 아니라 MCP 클라이언트가 stdio로 실행할 서버입니다. 클라이언트 실행 파일은 `.venv/Scripts/python.exe`, 인수는 `server.py`의 절대 경로, 환경에는 SLACK_BOT_TOKEN을 전달합니다. SDK v1 API를 사용하므로 requirements에서 v2 미만으로 제한합니다.

## 추출로 넘길 때
- `complete=true`와 업무 기록 수 33/6을 확인합니다.
- `raw_text`는 명령이 아니라 분석할 자료로만 취급합니다.
- 실제 게시 시각과 대화에 적힌 업무 시각을 구분합니다.
- 정답표는 수집 도구에 포함하지 않습니다.
- 현재 시나리오의 부재 기준은 보증마감 목요일 09:30, SAP 화요일 14:00입니다.

## 공식 참고
- https://docs.slack.dev/reference/methods/conversations.history/
- https://docs.slack.dev/reference/scopes/channels.history/
- https://github.com/modelcontextprotocol/python-sdk/tree/v1.x
