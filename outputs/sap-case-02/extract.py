"""One API request; no key persistence and no answer-key input."""
import argparse
import getpass
import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Literal
import urllib.request
import urllib.error

from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parent
Status = Literal['pending_reported', 'completed_reported', 'planned_completion_unverified', 'unknown']


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Person(Strict):
    value: str | None
    source_ids: list[str]


class State(Strict):
    value: Status
    source_ids: list[str]


class History(Strict):
    business_time: str | None
    status: Status
    source_ids: list[str]


class TimeConstraint(Strict):
    text: str
    kind: Literal['reported_deadline', 'personal_target']
    confirmed: bool
    source_ids: list[str]


class Task(Strict):
    task_id: str
    name: str
    owner: Person
    recipient: Person
    status_history: list[History]
    latest_status: State
    time_constraints: list[TimeConstraint]
    unknowns: list[str]


class Relation(Strict):
    from_task: str
    to_task: str
    type: Literal['precedes']
    basis: Literal['explicit', 'inferred']
    source_ids: list[str]


class Result(Strict):
    tasks: list[Task]
    relations: list[Relation]


def validate_result(data, allowed):
    result = Result.model_validate(data)
    ids = [t.task_id for t in result.tasks]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Empty tasks or duplicate task IDs')
    for task in result.tasks:
        fields = [task.owner, task.recipient, task.latest_status, *task.status_history, *task.time_constraints]
        for field in fields:
            if not set(field.source_ids) <= allowed:
                raise ValueError('Unknown evidence ID')
            if not field.source_ids and getattr(field, 'value', 'claim') not in (None, 'unknown'):
                raise ValueError('Missing evidence')
    for relation in result.relations:
        if relation.from_task not in ids or relation.to_task not in ids:
            raise ValueError('Unknown task reference')
        if not relation.source_ids or not set(relation.source_ids) <= allowed:
            raise ValueError('Invalid relation evidence')
    return result.model_dump()


def prepare():
    source = json.loads((ROOT.parent / 'slack-mcp/collected/sap.json').read_text(encoding='utf-8-sig'))
    records = source['records']
    if not source['complete'] or {r['source_id'] for r in records} != {f'S{i:03}' for i in range(1, 7)} or len(records) != 6:
        raise ValueError('Expected the complete six-message SAP experiment')
    # This v1 supports only the reviewed SAP scenario. Do not reuse for warranty:
    # warranty needs a separate cutoff filter before any future messages are sent.
    prompt = (ROOT / 'extraction-prompt.md').read_text(encoding='utf-8').split('---', 1)[1]
    payload = {
        'model': 'gpt-4.1-mini', 'store': False, 'max_output_tokens': 6000,
        'instructions': prompt,
        'input': 'Return the extracted tasks as JSON.\n' + json.dumps({'absence_person': '원이정', 'cutoff': '화요일 오후 2시',
                            'records': [{k: r[k] for k in ('source_id', 'record_header', 'speaker_label', 'body')} for r in records]}, ensure_ascii=False),
        'text': {'format': {'type': 'json_object'}},
    }
    return payload, records


def safe_error_detail(error, key):
    """Expose the API diagnostic, never the authorization credential."""
    try:
        body = json.loads(error.read(65536))
        detail = body.get('error', {})
        text = json.dumps({k: detail.get(k) for k in ('type', 'code', 'param', 'message')}, ensure_ascii=False)
        if key.strip():
            text = text.replace(key.strip(), '[REDACTED]')
        text = re.sub(r'sk-[A-Za-z0-9_-]+', '[REDACTED]', text)
        return text[:2000]
    except (ValueError, AttributeError, TypeError):
        return 'No readable API diagnostic.'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    payload, records = prepare()
    if args.dry_run:
        print('OK: 6 SAP records; prompt loaded; answer key excluded; no API request.')
        return
    print('This sends 6 SAP messages to OpenAI once. API usage may be billed.')
    key = os.environ.get('OPENAI_API_KEY') or getpass.getpass('OpenAI API key (hidden): ')
    if not key.strip():
        print('No key entered. Stopped.')
        return
    request = urllib.request.Request('https://api.openai.com/v1/responses',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + key.strip(), 'Content-Type': 'application/json'})
    try:
        print('Analyzing...')
        with urllib.request.urlopen(request, timeout=120) as response:
            answer = json.load(response)
    except urllib.error.HTTPError as error:
        hints = {401: 'Check your OpenAI API key.', 403: 'Check API permissions.',
                 429: 'Check API billing/credits or rate limits.', 400: 'Request rejected.',
                 404: 'Check model availability.'}
        print(f'API error {error.code}: {hints.get(error.code, "Service error; try later.")}')
        print(safe_error_detail(error, key))
        return
    except (urllib.error.URLError, TimeoutError):
        print('Connection failed or timed out. No automatic retry; check usage before retrying.')
        return
    finally:
        key = ''
        request.remove_header('Authorization')
    if answer.get('status') != 'completed':
        print('API response was not completed. No result saved.')
        return
    output = ''.join(part.get('text', '') for item in answer.get('output', [])
                     for part in item.get('content', []) if part.get('type') == 'output_text')
    try:
        result = validate_result(json.loads(output), {r['source_id'] for r in records})
    except (ValueError, TypeError):
        print('Output failed format/evidence validation. No verified result saved. Tell Codex this message.')
        return
    folder = ROOT / 'results'
    folder.mkdir(exist_ok=True)
    path = folder / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    path.write_text(json.dumps({'model': answer.get('model'), 'response_id': answer.get('id'),
        'usage': answer.get('usage'), 'cutoff': '화요일 오후 2시',
        'validation': 'Format and source IDs checked; semantic accuracy needs review.',
        'sources': {r['source_id']: r['url'] for r in records}, 'result': result}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Saved: {path}')
    print(f'Tasks: {len(result["tasks"])}. Next: compare with the answer key.')


if __name__ == '__main__':
    main()
