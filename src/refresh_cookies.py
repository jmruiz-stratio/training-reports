#!/usr/bin/env python3
"""
refresh_cookies.py — Renueva las cookies de Rocket (tenant formacion) en el .env.

Uso:
  python3 src/refresh_cookies.py              # urllib (sin dependencias extra)
  python3 src/refresh_cookies.py --selenium   # fallback Selenium + Firefox

Cuándo ejecutarlo:
  - Cuando el agente falla con 401/403 al subir a HDFS.
  - Las cookies expiran aproximadamente cada 8 horas.
"""

import argparse
import os
import sys
from pathlib import Path

# Raíz del repo al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.shared.utils import load_env
from src.shared.practices_auth import get_cookies, get_cookies_selenium

ENV_FILE = Path(__file__).parent.parent / ".env"
ENV_KEY  = "PRACTICES_COOKIES_FORMACION"


def _update_env(cookie_str: str) -> None:
    """Actualiza PRACTICES_COOKIES_FORMACION en el .env."""
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{ENV_KEY}="):
            new_lines.append(f"{ENV_KEY}={cookie_str}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{ENV_KEY}={cookie_str}")
    ENV_FILE.write_text("\n".join(new_lines) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Renueva cookies de Rocket (tenant formacion) en el .env"
    )
    parser.add_argument(
        "--selenium", action="store_true",
        help="Usa Selenium + Firefox en lugar de urllib (si el SSO requiere JS)",
    )
    parser.add_argument(
        "--visible", action="store_true",
        help="Con --selenium: muestra la ventana del navegador (para depurar)",
    )
    args = parser.parse_args()

    load_env(str(ENV_FILE))
    rocket_url = os.environ.get("STRATIO_URL", "https://admin.practices.stratio.com")
    user       = os.environ.get("STRATIO_USER", "").strip()
    password   = os.environ.get("STRATIO_PASS", "").strip()
    tenant     = os.environ.get("STRATIO_TENANT", "formacion")

    if not user or not password:
        print("  ✗  STRATIO_USER o STRATIO_PASS no definidos en .env")
        sys.exit(1)

    print(f"\n  Obteniendo cookies para tenant={tenant!r} en {rocket_url}")
    print(f"  Usuario: {user}")
    print(f"  Método:  {'Selenium' if args.selenium else 'urllib (stdlib)'}\n")

    try:
        if args.selenium:
            cookies = get_cookies_selenium(
                rocket_url, user, password, tenant,
                headless=not args.visible,
            )
        else:
            cookies = get_cookies(rocket_url, user, password, tenant)
    except RuntimeError as e:
        print(f"  ✗  {e}")
        if not args.selenium:
            print("\n  Prueba con el fallback Selenium:")
            print("    python3 src/refresh_cookies.py --selenium")
        sys.exit(1)

    # Construir el string de cookie en el mismo formato que training-agents
    cookie_parts = ["lang=en"]
    cookie_parts.append(f"stratio-cookie={cookies['stratio-cookie']}")
    if "stickyrocket" in cookies:
        cookie_parts.append(f"stickyrocket={cookies['stickyrocket']}")
    cookie_parts.append(f"JSESSIONID={cookies['JSESSIONID']}")
    cookie_str = "; ".join(cookie_parts)

    _update_env(cookie_str)

    print(f"  ✓  Cookies actualizadas en {ENV_FILE.name}")
    print(f"     stratio-cookie: {cookies['stratio-cookie'][:40]}...")
    print(f"     JSESSIONID:     {cookies['JSESSIONID']}")
    print()


if __name__ == "__main__":
    main()
