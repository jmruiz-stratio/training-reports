"""
shared/practices_auth.py — Login en admin.practices.stratio.com sin navegador.

Implementación con urllib + http.cookiejar + html.parser (solo stdlib).
Sigue el flujo OAuth2-proxy → SSO → redirección → cookies.

Si el SSO usa JavaScript pesado y este módulo falla, usar el fallback
Selenium de refresh_cookies.py --selenium.
"""

import html.parser
import http.cookiejar
import urllib.error
import urllib.parse
import urllib.request


# ─── Parser de formulario HTML ────────────────────────────────────────────────

class _FormParser(html.parser.HTMLParser):
    """Extrae action y campos hidden/text de un formulario HTML."""

    def __init__(self):
        super().__init__()
        self.action: str | None = None
        self.method: str = "post"
        self.fields: dict[str, str] = {}
        self._in_form = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self._in_form = True
            self.action = attrs.get("action")
            self.method = attrs.get("method", "post").lower()
        elif tag == "input" and self._in_form:
            name  = attrs.get("name", "")
            value = attrs.get("value", "")
            typ   = attrs.get("type", "text").lower()
            if name and typ not in ("submit", "button", "image", "reset"):
                self.fields[name] = value

    def handle_endtag(self, tag):
        if tag == "form":
            self._in_form = False


def _absolute_url(base_url: str, action: str) -> str:
    """Convierte una action relativa en URL absoluta."""
    if action.startswith("http"):
        return action
    parsed = urllib.parse.urlparse(base_url)
    if action.startswith("/"):
        return f"{parsed.scheme}://{parsed.netloc}{action}"
    # relativa al path
    path = parsed.path.rsplit("/", 1)[0]
    return f"{parsed.scheme}://{parsed.netloc}{path}/{action}"


# ─── Login ────────────────────────────────────────────────────────────────────

def get_cookies(rocket_url: str, user: str, password: str,
                tenant: str = "formacion") -> dict[str, str]:
    """
    Hace login en admin.practices.stratio.com y devuelve
    {"stratio-cookie": "...", "JSESSIONID": "..."}.

    Parámetros:
      rocket_url — https://admin.practices.stratio.com
      user       — usuario del SSO (ej: admin)
      password   — contraseña
      tenant     — tenant Stratio (default: formacion)

    Lanza RuntimeError si el login falla.
    """
    jar    = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar),
        urllib.request.HTTPRedirectHandler(),
    )
    opener.addheaders = [
        ("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    ]

    # Paso 1: iniciar flujo OAuth2 → SSO
    start_url = f"{rocket_url.rstrip('/')}/oauth2/start?rd=%2Frocketf%2F"
    try:
        resp = opener.open(start_url, timeout=20)
    except urllib.error.URLError as e:
        raise RuntimeError(f"No se puede conectar a {rocket_url}: {e}") from e

    login_html = resp.read().decode("utf-8", errors="replace")
    login_url  = resp.geturl()

    # Paso 2: parsear formulario de login
    fp = _FormParser()
    fp.feed(login_html)

    if not fp.action:
        raise RuntimeError(
            f"No se encontró formulario de login en {login_url}. "
            "El SSO puede requerir JavaScript — usa --selenium."
        )

    action_url = _absolute_url(login_url, fp.action)

    # Paso 3: rellenar credenciales + tenant
    fields = fp.fields.copy()
    fields["username"] = user
    fields["password"] = password

    # El campo tenant puede tener varios nombres según la versión del SSO
    tenant_keys = [k for k in fields if "tenant" in k.lower()]
    if tenant_keys:
        fields[tenant_keys[0]] = tenant
    else:
        fields["customFields[tenant]"] = tenant

    # Paso 4: POST al SSO
    body = urllib.parse.urlencode(fields).encode()
    req  = urllib.request.Request(
        action_url, data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer":      login_url,
        },
    )
    try:
        resp = opener.open(req, timeout=20)
        resp.read()
    except urllib.error.URLError as e:
        raise RuntimeError(f"Error en POST de login: {e}") from e

    # Paso 5: extraer cookies
    cookies = {c.name: c.value for c in jar}
    sc = cookies.get("stratio-cookie", "")
    js = cookies.get("JSESSIONID", "")

    if not sc or not js:
        raise RuntimeError(
            f"Login fallido para tenant={tenant!r}: "
            f"cookies obtenidas={list(cookies.keys())}. "
            "Verifica usuario/contraseña. "
            "Si el SSO requiere JS, usa: python3 src/refresh_cookies.py --selenium"
        )

    result = {"stratio-cookie": sc, "JSESSIONID": js}
    sticky = cookies.get("stickyrocket")
    if sticky:
        result["stickyrocket"] = sticky
    return result


# ─── Fallback Selenium ────────────────────────────────────────────────────────

def get_cookies_selenium(rocket_url: str, user: str, password: str,
                         tenant: str = "formacion",
                         headless: bool = True) -> dict[str, str]:
    """
    Fallback: obtiene cookies via Selenium + Firefox.
    Requiere: pip install selenium  &&  sudo apt install firefox-geckodriver
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as e:
        raise RuntimeError(
            "Selenium no instalado. Ejecuta: pip install selenium\n"
            "Y asegúrate de tener geckodriver: sudo apt install firefox-geckodriver"
        ) from e

    import time

    target   = rocket_url.rstrip("/")
    login_url = f"{target}/oauth2/start?rd=%2Frocketf%2F"

    opts = Options()
    if headless:
        opts.add_argument("--headless")
    driver = webdriver.Firefox(options=opts)
    wait   = WebDriverWait(driver, 30)

    try:
        driver.get(login_url)

        user_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
        user_field.clear()
        user_field.send_keys(user)
        driver.find_element(By.ID, "password").send_keys(password)

        # Inyectar tenant
        try:
            tf = driver.find_element(
                By.CSS_SELECTOR,
                "input[name='customFields[tenant]'], input[name='tenant']",
            )
            tf.clear()
            tf.send_keys(tenant)
        except Exception:
            driver.execute_script("""
                var f = document.querySelector('form');
                if (f) {
                    var h = document.createElement('input');
                    h.type  = 'hidden';
                    h.name  = 'customFields[tenant]';
                    h.value = arguments[0];
                    f.appendChild(h);
                }
            """, tenant)

        driver.find_element(
            By.CSS_SELECTOR, "input[type='submit'], button[type='submit']"
        ).click()

        wait.until(EC.url_contains(urllib.parse.urlparse(target).netloc))
        time.sleep(2)

        all_cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
    finally:
        driver.quit()

    sc = all_cookies.get("stratio-cookie", "")
    js = all_cookies.get("JSESSIONID", "")
    if not sc or not js:
        raise RuntimeError(
            f"Selenium: login fallido para tenant={tenant!r}. "
            f"Cookies obtenidas: {list(all_cookies.keys())}"
        )

    result = {"stratio-cookie": sc, "JSESSIONID": js}
    sticky = all_cookies.get("stickyrocket")
    if sticky:
        result["stickyrocket"] = sticky
    return result
