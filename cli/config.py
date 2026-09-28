import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".webnovel-toolkit"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULTS = {
    "output_dir": str(Path.home() / "Downloads" / "fan_tl_chapters"),
    "retries": 2,
    "timeout": 60000,
}


def load_config():
    data = DEFAULTS.copy()
    try:
        if CONFIG_FILE.exists():
            loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update({k: v for k, v in loaded.items() if k in DEFAULTS})
    except Exception:
        pass
    return data


def save_config(data):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
