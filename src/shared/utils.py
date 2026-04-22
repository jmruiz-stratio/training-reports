"""
shared/utils.py — Utilidades comunes (copiado de training-agents, sin partes Gmail).
"""

import os
from pathlib import Path


def load_env(path=".env"):
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.split("#")[0]  # elimina comentario inline
        os.environ[key.strip()] = val.strip()


def log(msg, symbol="·"):
    print(f"  {symbol} {msg}")
