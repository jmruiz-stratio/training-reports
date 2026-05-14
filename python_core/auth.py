"""Authentication helpers for Rocket/Stratio cookies."""

import os
from python_core.config import Settings
from python_core.utils import log


def parse_cookie_header(raw: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        parts[k.strip()] = v.strip()
    return parts


def get_rocket_cookies(settings: Settings) -> dict[str, str]:
    cookie = os.environ.get("STRATIO_COOKIE", "").strip()
    jsession = os.environ.get("JSESSIONID", "").strip()
    if cookie and jsession:
        return {"stratio-cookie": cookie, "JSESSIONID": jsession}

    raw = os.environ.get("PRACTICES_COOKIES_FORMACION", "").strip()
    if raw:
        parsed = parse_cookie_header(raw)
        if parsed.get("stratio-cookie") and parsed.get("JSESSIONID"):
            return {"stratio-cookie": parsed["stratio-cookie"], "JSESSIONID": parsed["JSESSIONID"]}

    if settings.stratio_user and settings.stratio_pass:
        from shared.practices_auth import get_cookies

        log("Cookies no definidas, intentando login automático...")
        return get_cookies(
            settings.stratio_url,
            settings.stratio_user,
            settings.stratio_pass,
            settings.stratio_tenant,
        )

    raise RuntimeError("No se pudieron obtener cookies Rocket (STRATIO_COOKIE/JSESSIONID o login)")
