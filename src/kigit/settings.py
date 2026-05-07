from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


def _settings_dir(project_dir: str) -> Path:
    return Path(project_dir).resolve() / ".kigit"


def _settings_path(project_dir: str) -> Path:
    return _settings_dir(project_dir) / "kigit.json"


def _is_abs(p: str) -> bool:
    try:
        return os.path.isabs(p)
    except Exception:
        return False


@dataclass
class KiGitSettings:
    export: dict[str, bool] = field(default_factory=dict)
    backup_base_dir: str = ".kigit-backups"
    last_revision: str = ""
    ui: dict[str, Any] = field(default_factory=dict)

    def resolved_backup_base_dir(self, project_dir: str) -> Path:
        val = (self.backup_base_dir or "").strip() or ".kigit-backups"
        if _is_abs(val):
            return Path(val).expanduser().resolve()
        return (Path(project_dir).resolve() / val).resolve()

    @classmethod
    def load(cls, project_dir: str) -> "KiGitSettings":
        path = _settings_path(project_dir)
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except Exception:
            return cls()

        export = data.get("export") if isinstance(data, dict) else None
        backup_base_dir = data.get("backup_base_dir") if isinstance(data, dict) else None
        last_revision = data.get("last_revision") if isinstance(data, dict) else None
        ui = data.get("ui") if isinstance(data, dict) else None

        return cls(
            export=dict(export) if isinstance(export, dict) else {},
            backup_base_dir=str(backup_base_dir) if isinstance(backup_base_dir, str) else ".kigit-backups",
            last_revision=str(last_revision) if isinstance(last_revision, str) else "",
            ui=dict(ui) if isinstance(ui, dict) else {},
        )

    def save(self, project_dir: str) -> None:
        sdir = _settings_dir(project_dir)
        sdir.mkdir(parents=True, exist_ok=True)
        path = _settings_path(project_dir)
        payload = {
            "export": dict(self.export),
            "backup_base_dir": self.backup_base_dir,
            "last_revision": self.last_revision,
            "ui": dict(self.ui),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
