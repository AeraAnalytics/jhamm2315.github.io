"""Minimal private configuration loader (environment always wins)."""
from __future__ import annotations
import os
from pathlib import Path


def load_private_env(project: Path | None = None) -> None:
    root=(project or Path.cwd()).resolve()
    for candidate in (root.parent/".env.local",root/".env.local"):
        if not candidate.is_file(): continue
        for raw in candidate.read_text().splitlines():
            line=raw.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            key,value=line.split("=",1)
            if key.strip().isidentifier(): os.environ.setdefault(key.strip(),value.strip().strip("'\""))
