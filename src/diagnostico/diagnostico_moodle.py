"""
diagnostico_moodle.py — Diagnóstico de configuración de Moodle Web Services.

Uso:
  python3 src/diagnostico/diagnostico_moodle.py

Comprueba token, conectividad y que todas las funciones necesarias
(§9.7 y §9.8 del CLAUDE.md) estén habilitadas en el servicio web de Moodle.
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error

# Añade la raíz del repo al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.shared.utils import load_env

OK   = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"
INFO = "\033[94m·\033[0m"

# ─── Funciones necesarias (§9.7 estándar + §9.8 custom) ──────────────────────

FUNCIONES_ESTANDAR = [
    ("core_webservice_get_site_info",               "Verificar token y acceso básico"),
    ("core_user_get_users",                         "Listado masivo de usuarios"),
    ("core_user_get_users_by_field",                "Buscar usuario concreto"),
    ("core_course_get_courses",                     "Listado de cursos"),
    ("core_cohort_get_cohorts",                     "Listado de cohortes"),
    ("core_cohort_get_cohort_members",              "Miembros de una cohorte"),
    ("core_enrol_get_users_courses",                "Inscripciones de un usuario"),
    ("gradereport_user_get_grade_items",            "Notas de un usuario en un curso"),
    ("core_completion_get_course_completion_status","Completion por usuario/curso"),
]

FUNCIONES_CUSTOM = [
    ("local_stratiorep_get_cohort_members",         "Miembros con timeadded (plugin)"),
    ("local_stratiorep_get_attendance_sessions",    "Sesiones asistencia (plugin)"),
    ("local_stratiorep_get_enrol_cohort_course",    "Puente cohorte→curso (plugin)"),
    ("local_stratiorep_get_all_grades",             "Todas las notas en una llamada (plugin, opcional)"),
]


def llamar_moodle(url: str, token: str, funcion: str, **params) -> dict | list:
    datos = {
        "wstoken":            token,
        "wsfunction":         funcion,
        "moodlewsrestformat": "json",
        **{k: str(v) for k, v in params.items()},
    }
    body = urllib.parse.urlencode(datos).encode()
    req = urllib.request.Request(
        f"{url}/webservice/rest/server.php",
        data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def check_funcion(url: str, token: str, funcion: str, descripcion: str) -> bool:
    try:
        resultado = llamar_moodle(url, token, funcion)
        if isinstance(resultado, dict) and "exception" in resultado:
            errorcode = resultado.get("errorcode", resultado.get("exception", ""))
            # invalidparameter/missingparam → función accesible, solo faltan params
            if "invalidparameter" in errorcode.lower() or "missingparam" in errorcode.lower():
                print(f"  {OK}  {funcion}  (accesible)")
                print(f"         → {descripcion}")
                return True
            if "access" in errorcode.lower():
                print(f"  {FAIL}  {funcion}")
            else:
                # otro error (ej: dml_missing_record_exception = función no registrada)
                print(f"  {FAIL}  {funcion}  [{errorcode}]")
            print(f"         → {descripcion}")
            return False
        print(f"  {OK}  {funcion}")
        print(f"         → {descripcion}")
        return True
    except Exception as e:
        msg = str(e).lower()
        if "invalidparameter" in msg or "missingparam" in msg:
            # La función existe y es accesible; solo le faltan parámetros concretos
            print(f"  {OK}  {funcion}  (accesible)")
            print(f"         → {descripcion}")
            return True
        if "accessexception" in msg or "webservice_access_exception" in msg:
            print(f"  {FAIL}  {funcion}")
            print(f"         → {descripcion}")
            return False
        print(f"  {WARN}  {funcion}  (error inesperado: {str(e)[:80]})")
        return False  # cualquier error desconocido = no funciona


def main():
    load_env()

    moodle_url   = os.environ.get("MOODLE_URL",   "").rstrip("/")
    moodle_token = os.environ.get("MOODLE_TOKEN", "")

    print("\n" + "═" * 62)
    print("  Diagnóstico Moodle Web Services — training-reports")
    print("═" * 62 + "\n")

    # ── 1. Variables de entorno ───────────────────────────────────────────────
    print(f"  {INFO}  Variables de entorno")
    env_ok = True
    if not moodle_url:
        print(f"  {FAIL}  MOODLE_URL no definida en .env")
        env_ok = False
    else:
        print(f"  {OK}  MOODLE_URL = {moodle_url}")

    if not moodle_token:
        print(f"  {FAIL}  MOODLE_TOKEN no definida en .env")
        env_ok = False
    else:
        print(f"  {OK}  MOODLE_TOKEN = {moodle_token[:8]}...")

    if not env_ok:
        print("\n  Añade MOODLE_URL y MOODLE_TOKEN al fichero .env y vuelve a ejecutar.")
        sys.exit(1)

    # ── 2. Conectividad básica ────────────────────────────────────────────────
    print(f"\n  {INFO}  Conectividad")
    try:
        resultado = llamar_moodle(moodle_url, moodle_token, "core_webservice_get_site_info")
        if "exception" in resultado:
            print(f"  {FAIL}  Token inválido: {resultado.get('message', '')}")
            sys.exit(1)
        print(f"  {OK}  Conectado a '{resultado.get('sitename','?')}' "
              f"como '{resultado.get('username','?')}'")
    except urllib.error.URLError as e:
        print(f"  {FAIL}  No se puede conectar a {moodle_url}: {e}")
        sys.exit(1)

    # ── 3. Funciones estándar (§9.7) ─────────────────────────────────────────
    print(f"\n  {INFO}  Funciones estándar (§9.7)")
    fallos_std = []
    for funcion, descripcion in FUNCIONES_ESTANDAR:
        if not check_funcion(moodle_url, moodle_token, funcion, descripcion):
            fallos_std.append(funcion)

    # ── 4. Funciones custom (§9.8) ────────────────────────────────────────────
    print(f"\n  {INFO}  Funciones custom plugin local_stratiorep (§9.8)")
    fallos_custom = []
    for funcion, descripcion in FUNCIONES_CUSTOM:
        if not check_funcion(moodle_url, moodle_token, funcion, descripcion):
            fallos_custom.append(funcion)

    # ── 5. Resumen ────────────────────────────────────────────────────────────
    print()
    if not fallos_std and not fallos_custom:
        print(f"  {OK}  Todo correcto. El agente puede conectarse a Moodle.\n")
        return

    if fallos_std:
        print("═" * 62)
        print(f"  {FAIL}  {len(fallos_std)} función(es) estándar sin acceso:\n")
        for f in fallos_std:
            print(f"         · {f}")
        print("""
  CÓMO AÑADIRLAS:
    Admin → Plugins → Web services → Servicios externos
    → Servicio asociado al token → Funciones → Añadir función
""")

    if fallos_custom:
        print("═" * 62)
        print(f"  {WARN}  {len(fallos_custom)} función(es) custom no disponibles:\n")
        for f in fallos_custom:
            print(f"         · {f}")
        print("""
  Las funciones custom requieren instalar el plugin local_stratiorep
  (ver moodle_plugin/ en el repo). Sin ellas, los datasets
  cohort_members_ext, attendance_sessions y enrol_cohort_course
  quedarán vacíos pero el pipeline no abortará.
""")


if __name__ == "__main__":
    main()
