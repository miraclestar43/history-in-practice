"""Configuration.

Public, non-secret settings live in the repo (``config/project.json``).
Secrets and recipients live ONLY in a private env file outside the repo
(default ``~/.config/history-in-practice/runtime.env``, mode 0600). Nothing
here ever prints secret values or recipient addresses; ``describe()`` reports
only whether each key is set.
"""
from __future__ import annotations
import json, os, stat
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_ENV = Path(os.environ.get("HIP_RUNTIME_ENV", Path.home() / ".config/history-in-practice/runtime.env"))
SECRET_KEYS = {"SMTP_PASSWORD"}
PRIVATE_KEYS = {"SMTP_PASSWORD", "EMAIL_RECIPIENTS", "EMAIL_REPLY_TO", "SMTP_USERNAME"}


def parse_env(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


@dataclass
class Runtime:
    values: dict[str, str] = field(default_factory=dict)
    path: Path | None = None
    insecure_permissions: bool = False

    def get(self, key, default=""):
        return self.values.get(key, default)

    @property
    def send_enabled(self) -> bool:
        return self.get("EMAIL_SEND_ENABLED", "false").lower() == "true"

    @property
    def recipients(self) -> list[str]:
        return [r.strip() for r in self.get("EMAIL_RECIPIENTS").split(",") if r.strip()]

    def describe(self) -> dict[str, str]:
        """Safe summary: values for non-private keys, set/unset for private ones."""
        d = {}
        for k, v in sorted(self.values.items()):
            if k in PRIVATE_KEYS:
                d[k] = (f"set ({len(self.recipients)} addresses)" if k == "EMAIL_RECIPIENTS" and v else ("set" if v else "unset"))
            else:
                d[k] = v
        return d


def load_runtime(path: Path | None = None) -> Runtime:
    p = Path(path or DEFAULT_RUNTIME_ENV)
    if not p.exists():
        return Runtime({}, p)
    mode = stat.S_IMODE(p.stat().st_mode)
    rt = Runtime(parse_env(p.read_text(encoding="utf-8")), p, insecure_permissions=bool(mode & 0o077))
    if REPO in p.resolve().parents:
        raise RuntimeError("runtime env must live outside the repository")
    return rt


def load_project() -> dict:
    p = REPO / "config/project.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def data_dir() -> Path:
    d = Path(os.environ.get("HIP_DATA_DIR", REPO / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d
