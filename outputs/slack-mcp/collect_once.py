"""Interactive local credential entry. Never stores the token."""
import getpass
import json
import os
from pathlib import Path
from collector import collect

if __name__ == "__main__":
    if not os.environ.get("SLACK_BOT_TOKEN"):
        os.environ["SLACK_BOT_TOKEN"] = getpass.getpass("Slack Bot User OAuth Token (hidden): ").strip()
    destination = Path(__file__).parent / "collected"
    destination.mkdir(exist_ok=True)
    try:
        for case in ("warranty", "sap"):
            result = collect(case)
            path = destination / (case + ".json")
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{case}: {len(result['records'])} records; complete={result['complete']}; {path}")
    except RuntimeError as exc:
        print(str(exc))
        raise SystemExit(1)
    finally:
        os.environ.pop("SLACK_BOT_TOKEN", None)
