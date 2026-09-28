from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PathsConfig:
    root: Path
    chapters: Path
    cleaned: Path
    ebooks: Path
    pdf: Path
    logs: Path

    @classmethod
    def from_root(cls, root: Path) -> "PathsConfig":
        root = Path(root).expanduser().resolve()
        return cls(
            root=root,
            chapters=root / "chapters",
            cleaned=root / "cleaned",
            ebooks=root / "ebooks",
            pdf=root / "pdf",
            logs=root / "logs",
        )

    def ensure(self) -> None:
        for path in (self.root, self.chapters, self.cleaned, self.ebooks, self.pdf, self.logs):
            path.mkdir(parents=True, exist_ok=True)


@dataclass
class AppConfig:
    output_root: Path = field(default_factory=lambda: Path.home() / "Downloads" / "webnovel-toolkit")
    retries: int = 2
    request_timeout: int = 30
    browser_timeout: int = 60
    pause_between_retries: float = 1.0
    show_timestamps: bool = False

    @property
    def paths(self) -> PathsConfig:
        return PathsConfig.from_root(self.output_root)


class ConfigStore:
    """Small persistent JSON config; intentionally dependency-free."""

    def __init__(self, path: Path | None = None):
        self.path = path or (Path.home() / ".webnovel-toolkit" / "config.json")

    def load(self) -> AppConfig:
        if not self.path.exists():
            config = AppConfig()
            config.paths.ensure()
            self.save(config)
            return config
        try:
            data: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
            config = AppConfig(
                output_root=Path(data.get("output_root", AppConfig().output_root)).expanduser(),
                retries=max(0, int(data.get("retries", 2))),
                request_timeout=max(5, int(data.get("request_timeout", 30))),
                browser_timeout=max(10, int(data.get("browser_timeout", 60))),
                pause_between_retries=max(0.0, float(data.get("pause_between_retries", 1.0))),
                show_timestamps=bool(data.get("show_timestamps", False)),
            )
            config.paths.ensure()
            return config
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            config = AppConfig()
            config.paths.ensure()
            return config

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(config)
        payload["output_root"] = str(config.output_root.expanduser())
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
