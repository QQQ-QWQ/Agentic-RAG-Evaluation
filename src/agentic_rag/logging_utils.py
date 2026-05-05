from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_run_log(record: dict[str, Any], log_dir: str | Path = "runs/logs") -> str:
    config_name = str(record.get("config") or "unknown")
    target_dir = Path(log_dir) / config_name
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path = target_dir / "run_logs.jsonl"

    log_record = dict(record)
    log_record["logged_at"] = datetime.now(timezone.utc).isoformat()
    log_record["log_path"] = str(log_path)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_record, ensure_ascii=False) + "\n")
    return str(log_path)
