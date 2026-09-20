"""SAP extraction through local Ollama only; no API key or paid endpoint."""
import argparse
from datetime import datetime, timezone
import json
import urllib.request
import urllib.error
from extract import ROOT, Result, prepare, validate_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='qwen3:4b-instruct')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    original, records = prepare()
    payload = {'model': args.model, 'stream': False,
               'messages': [{'role': 'system', 'content': original['instructions']},
                            {'role': 'user', 'content': original['input']}],
               'format': Result.model_json_schema(),
               'options': {'temperature': 0, 'num_ctx': 8192, 'num_predict': 5000}}
    if args.dry_run:
        assert len(records) == 6
        print('Local request ready: SAP 6 records; JSON schema; no answer key; no network call.')
        return
    # Explicitly bypass proxies so conversation text only goes to loopback.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open('http://127.0.0.1:11434/api/tags', timeout=5) as response:
            models = json.load(response).get('models', [])
        if args.model not in {m['name'] for m in models}:
            print('Local model missing. Download the chosen model first: ollama pull ' + args.model)
            return
        request = urllib.request.Request('http://127.0.0.1:11434/api/chat',
            data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        print('Running local model. This may take several minutes. No OpenAI key needed.', flush=True)
        with opener.open(request, timeout=600) as response:
            answer = json.load(response)
    except urllib.error.HTTPError as error:
        print(f'Local Ollama HTTP error {error.code}. Check model availability and memory.')
        return
    except (urllib.error.URLError, TimeoutError):
        print('Local Ollama unavailable or timed out. Open Ollama, then retry. No automatic retry.')
        return
    folder = ROOT / 'local-results'
    folder.mkdir(exist_ok=True)
    stem = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    # Keep model output for error analysis; failed output is never called verified.
    (folder / f'{stem}-raw.json').write_text(json.dumps(answer, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        if not answer.get('done') or answer.get('done_reason') == 'length':
            raise ValueError('Incomplete generation')
        result = validate_result(json.loads(answer['message']['content']), {r['source_id'] for r in records})
    except (ValueError, KeyError, TypeError):
        print('Model output failed validation. Raw output saved for review; no validated result.')
        return
    path = folder / f'{stem}-validated.json'
    path.write_text(json.dumps({'model': args.model, 'result': result,
        'validation': 'Schema and evidence IDs only; semantic accuracy needs review.',
        'sources': {r['source_id']: r['url'] for r in records}}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Saved: {path}')


if __name__ == '__main__':
    main()
