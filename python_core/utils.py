"""Shared utility helpers for the new core package."""

import os
from pathlib import Path


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.split("#")[0]
        os.environ[key.strip()] = val.strip()


def log(msg: str, symbol: str = "·") -> None:
    print(f"  {symbol} {msg}")
