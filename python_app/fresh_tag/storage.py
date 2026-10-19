import json
from pathlib import Path

from .config import STATE_FILE
from .models import FreshnessStore


def load_store(path: Path = STATE_FILE) -> FreshnessStore:
    if not path.exists():
        return FreshnessStore()
    try:
        return FreshnessStore.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, KeyError):
        return FreshnessStore()


def save_store(store: FreshnessStore, path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(store.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
