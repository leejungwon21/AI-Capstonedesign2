"""On-demand Slack history collector.

The collector never polls in the background. Gold labels are not loaded here.
Raw text is retained for provenance, while model_text removes URLs so IDs such as
WORK-00005 embedded in links cannot leak into LLM evaluation.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request


SLACK_API = "https://slack.com/api"


def _token(explicit=None):
    value = (explicit or os.environ.get("SLACK_TOKEN", "")).strip()
    if not value:
        raise RuntimeError("SLACK_TOKEN is not configured.")
    return value


def _get(method, params, token=None):
    req = urllib.request.Request(
        f"{SLACK_API}/{method}?" + urllib.parse.urlencode(params),
        headers={"Authorization": "Bearer " + _token(token)},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Slack HTTP error {exc.code}") from None

    if not data.get("ok"):
        raise RuntimeError("Slack API error: " + str(data.get("error", "unknown")))
    return data


def sanitize_for_model(text):
    text = re.sub(r"https?://\S+", "[LINK]", text or "")
    return text


def collect_channel(channel_id, *, token=None, include_threads=True):
    messages = []
    cursor = ""

    while True:
        params = {"channel": channel_id, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        page = _get("conversations.history", params, token)
        messages.extend(page.get("messages", []))
        cursor = page.get("response_metadata", {}).get("next_cursor", "").strip()
        if not cursor:
            break

    records = []
    for message in sorted(messages, key=lambda x: float(x["ts"])):
        record = {
            "source_id": f"{channel_id}:{message['ts']}",
            "conversation_id": channel_id,
            "conversation_type": "unknown",
            "parent_ts": message.get("thread_ts"),
            "slack_ts": message["ts"],
            "slack_author_id": message.get("user"),
            "raw_text": message.get("text", ""),
            "model_text": sanitize_for_model(message.get("text", "")),
            "edited": message.get("edited"),
        }
        records.append(record)

        if include_threads and message.get("reply_count"):
            replies = _get(
                "conversations.replies",
                {"channel": channel_id, "ts": message["ts"], "limit": 200},
                token,
            )
            for reply in replies.get("messages", [])[1:]:
                records.append({
                    "source_id": f"{channel_id}:{reply['ts']}",
                    "conversation_id": channel_id,
                    "conversation_type": "unknown",
                    "parent_ts": message["ts"],
                    "slack_ts": reply["ts"],
                    "slack_author_id": reply.get("user"),
                    "raw_text": reply.get("text", ""),
                    "model_text": sanitize_for_model(reply.get("text", "")),
                    "edited": reply.get("edited"),
                })

    records.sort(key=lambda x: float(x["slack_ts"]))
    return {"channel_id": channel_id, "records": records}


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("channel_id")
    parser.add_argument("--out", default="collected.json")
    args = parser.parse_args()

    result = collect_channel(args.channel_id)
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
