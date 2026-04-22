"""
shared/moodle_api.py — Cliente REST de Moodle para extracción RAW.

Todas las funciones son stateless: reciben moodle_url y token por parámetro.
Solo stdlib + convención del proyecto (sin requests).

Datasets implementados (§5.1 del CLAUDE.md):
  Estándar:  users, courses, cohorts, cohort_members,
             user_courses, user_grades, course_completions
  Custom:    cohort_members_ext, attendance_sessions, enrol_cohort_course
             (requieren plugin local_stratiorep — §9.8)
"""

import json
import urllib.request
import urllib.parse
import urllib.error

from shared.utils import log


# ─── HTTP ─────────────────────────────────────────────────────────────────────

def _moodle_call(moodle_url: str, token: str, funcion: str,
                 _timeout: int = 30, **params) -> dict | list:
    datos = {
        "wstoken":            token,
        "wsfunction":         funcion,
        "moodlewsrestformat": "json",
        **{k: str(v) for k, v in params.items()},
    }
    body = "&".join(
        f"{k}={urllib.parse.quote(str(v))}" for k, v in datos.items()
    ).encode()

    req = urllib.request.Request(
        f"{moodle_url}/webservice/rest/server.php",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_timeout) as r:
            resultado = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Moodle HTTP {e.code} [{funcion}]: {e.read().decode()[:300]}")

    if isinstance(resultado, dict) and "exception" in resultado:
        exc_type = resultado.get("exception", "error")   # ej: "accessexception"
        exc_msg  = resultado.get("message", str(resultado))
        raise RuntimeError(f"Moodle [{funcion}] {exc_type}: {exc_msg}")

    return resultado


# ─── DATASETS ESTÁNDAR ────────────────────────────────────────────────────────

def get_users(moodle_url: str, token: str) -> list[dict]:
    """
    Devuelve todos los usuarios no borrados.
    core_user_get_users con criteria no pagina: trae todos en una llamada.
    Timeout extendido a 120s porque el servidor puede tardar con volúmenes grandes.
    """
    resultado = _moodle_call(
        moodle_url, token, "core_user_get_users",
        _timeout=120,
        **{"criteria[0][key]": "deleted", "criteria[0][value]": "0"},
    )
    return resultado.get("users", [])


def get_enrolled_users_by_course(moodle_url: str, token: str,
                                  courses: list[dict],
                                  timeout: int = 10) -> list[dict]:
    """
    Tercer fallback para usuarios: itera por cada curso y recoge los matriculados.
    Usa core_enrol_get_enrolled_users (una llamada por curso).
    Devuelve lista deduplicada de usuarios.

    timeout reducido a 10s (por defecto) para no bloquear en cursos grandes.
    Con core_user_get_users habilitado este fallback no se usa.
    """
    seen: set[int] = set()
    rows: list[dict] = []
    for course in courses:
        cid = course["id"]
        try:
            datos = {
                "wstoken": token,
                "wsfunction": "core_enrol_get_enrolled_users",
                "moodlewsrestformat": "json",
                "courseid": str(cid),
            }
            body = urllib.parse.urlencode(datos).encode()
            req = urllib.request.Request(
                f"{moodle_url}/webservice/rest/server.php",
                data=body, method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                result = json.loads(r.read())
            if isinstance(result, dict) and "exception" in result:
                continue   # curso sin acceso o sin matriculados
            for user in (result if isinstance(result, list) else []):
                uid = user.get("id")
                if uid and uid not in seen:
                    seen.add(uid)
                    rows.append(user)
        except Exception as e:
            if "invalidparameter" in str(e).lower():
                continue   # curso sin matriculados es normal
            log(f"enrolled_users course {cid}: {e}", "⚠")
    return rows


def get_users_by_ids(moodle_url: str, token: str,
                     user_ids: list[int], batch_size: int = 50) -> list[dict]:
    """
    Resuelve detalles de usuario a partir de una lista de IDs usando
    core_user_get_users_by_field (field=id).

    Se usa como fallback cuando core_user_get_users no está habilitado.
    Se pagina en batches de batch_size para no superar límites del servidor.
    """
    rows = []
    ids = list(set(user_ids))   # deduplicar
    for start in range(0, len(ids), batch_size):
        batch = ids[start: start + batch_size]
        params = {"field": "id"}
        for i, uid in enumerate(batch):
            params[f"values[{i}]"] = str(uid)
        try:
            resultado = _moodle_call(moodle_url, token,
                                     "core_user_get_users_by_field", **params)
            rows.extend(resultado if isinstance(resultado, list) else [])
        except Exception as e:
            log(f"get_users_by_ids batch {start}-{start+len(batch)}: {e}", "⚠")
    return rows


def get_courses(moodle_url: str, token: str) -> list[dict]:
    resultado = _moodle_call(moodle_url, token, "core_course_get_courses", _timeout=120)
    return resultado if isinstance(resultado, list) else []


def get_cohorts(moodle_url: str, token: str) -> list[dict]:
    resultado = _moodle_call(moodle_url, token, "core_cohort_get_cohorts")
    return resultado if isinstance(resultado, list) else []


def get_cohort_members(moodle_url: str, token: str,
                       cohorts: list[dict]) -> list[dict]:
    """
    N+1: una llamada por cohorte.
    Devuelve filas {cohortid, userid}. Sin timeadded (usar cohort_members_ext para eso).
    """
    rows = []
    for i, cohort in enumerate(cohorts):
        cid = cohort["id"]
        try:
            resultado = _moodle_call(
                moodle_url, token, "core_cohort_get_cohort_members",
                **{"cohortids[0]": cid},
            )
            for entry in resultado:
                for uid in entry.get("userids", []):
                    rows.append({"cohortid": cid, "userid": uid})
        except Exception as e:
            log(f"cohort_members cohort {cid}: {e}", "⚠")
        if (i + 1) % 10 == 0:
            log(f"  cohort_members: {i + 1}/{len(cohorts)} cohortes procesadas")
    return rows


def get_user_courses(moodle_url: str, token: str,
                     users: list[dict]) -> list[dict]:
    """N+1: una llamada por usuario."""
    rows = []
    for i, user in enumerate(users):
        uid = user["id"]
        try:
            cursos = _moodle_call(
                moodle_url, token, "core_enrol_get_users_courses", userid=uid,
            )
            for curso in (cursos if isinstance(cursos, list) else []):
                rows.append({"userid": uid, **curso})
        except Exception as e:
            log(f"user_courses user {uid}: {e}", "⚠")
        if (i + 1) % 50 == 0:
            log(f"  user_courses: {i + 1}/{len(users)} usuarios procesados")
    return rows


def get_user_grades(moodle_url: str, token: str,
                    users: list[dict], courses: list[dict]) -> list[dict]:
    """
    N+1 por (usuario, curso) — MUY LENTO para volúmenes grandes.
    Obtiene los grade items del curso completo para cada usuario.
    Solo incluye filas donde graderaw no es None.

    Si el plugin local_stratiorep está instalado, usar get_all_grades_custom
    en su lugar (una sola llamada, mucho más rápido).
    """
    rows = []
    total = len(users) * len(courses)
    done = 0
    for user in users:
        uid = user["id"]
        for course in courses:
            cid = course["id"]
            try:
                resultado = _moodle_call(
                    moodle_url, token, "gradereport_user_get_grade_items",
                    courseid=cid, userid=uid,
                )
                for ug in resultado.get("usergrades", []):
                    for item in ug.get("gradeitems", []):
                        if item.get("graderaw") is not None:
                            rows.append({
                                "userid":           uid,
                                "courseid":         cid,
                                "itemid":           item.get("id"),
                                "itemtype":         item.get("itemtype"),
                                "itemname":         item.get("itemname"),
                                "graderaw":         item.get("graderaw"),
                                "gradeformatted":   item.get("gradeformatted"),
                                "gradedatesubmitted": item.get("gradedatesubmitted"),
                                "gradedategraded":  item.get("gradedategraded"),
                            })
            except Exception as e:
                msg = str(e).lower()
                # invalidparameter = usuario no matriculado en el curso, es normal
                if "invalidparameter" not in msg and "notingroup" not in msg:
                    log(f"user_grades user={uid} course={cid}: {e}", "⚠")
            done += 1
            if done % 200 == 0:
                log(f"  user_grades: {done}/{total} combinaciones procesadas")
    return rows


def get_user_grades_by_pairs(moodle_url: str, token: str,
                              pairs: list[tuple[int, int]]) -> list[dict]:
    """
    Versión optimizada de get_user_grades: solo llama para los pares
    (userid, courseid) en que el usuario está efectivamente matriculado.

    pairs — lista de (userid, courseid) obtenida de user_courses.
    """
    rows = []
    total = len(pairs)
    for i, (uid, cid) in enumerate(pairs):
        try:
            resultado = _moodle_call(
                moodle_url, token, "gradereport_user_get_grade_items",
                courseid=cid, userid=uid,
            )
            for ug in resultado.get("usergrades", []):
                for item in ug.get("gradeitems", []):
                    if item.get("graderaw") is not None:
                        rows.append({
                            "userid":             uid,
                            "courseid":           cid,
                            "itemid":             item.get("id"),
                            "itemtype":           item.get("itemtype"),
                            "itemname":           item.get("itemname"),
                            "graderaw":           item.get("graderaw"),
                            "gradeformatted":     item.get("gradeformatted"),
                            "gradedatesubmitted": item.get("gradedatesubmitted"),
                            "gradedategraded":    item.get("gradedategraded"),
                        })
        except Exception as e:
            msg = str(e).lower()
            if "invalidparameter" not in msg and "notingroup" not in msg:
                log(f"user_grades user={uid} course={cid}: {e}", "⚠")
        if (i + 1) % 200 == 0:
            log(f"  user_grades: {i + 1}/{total} pares procesados")
    return rows


def get_course_completions_by_pairs(moodle_url: str, token: str,
                                     pairs: list[tuple[int, int]]) -> list[dict]:
    """Versión optimizada: solo llama para pares inscritos (userid, courseid)."""
    rows = []
    total = len(pairs)
    for i, (uid, cid) in enumerate(pairs):
        try:
            resultado = _moodle_call(
                moodle_url, token,
                "core_completion_get_course_completion_status",
                courseid=cid, userid=uid,
            )
            status = resultado.get("completionstatus", {})
            rows.append({
                "userid":        uid,
                "courseid":      cid,
                "completed":     status.get("completed", False),
                "timecompleted": status.get("timecompleted"),
            })
        except Exception as e:
            msg = str(e).lower()
            if "invalidparameter" not in msg and "nocompletion" not in msg:
                log(f"course_completions user={uid} course={cid}: {e}", "⚠")
        if (i + 1) % 200 == 0:
            log(f"  course_completions: {i + 1}/{total} pares procesados")
    return rows


def get_course_completions(moodle_url: str, token: str,
                           users: list[dict], courses: list[dict]) -> list[dict]:
    """N+1 por (usuario, curso)."""
    rows = []
    total = len(users) * len(courses)
    done = 0
    for user in users:
        uid = user["id"]
        for course in courses:
            cid = course["id"]
            try:
                resultado = _moodle_call(
                    moodle_url, token,
                    "core_completion_get_course_completion_status",
                    courseid=cid, userid=uid,
                )
                status = resultado.get("completionstatus", {})
                rows.append({
                    "userid":     uid,
                    "courseid":   cid,
                    "completed":  status.get("completed", False),
                    "timecompleted": status.get("timecompleted"),
                })
            except Exception as e:
                msg = str(e).lower()
                if "invalidparameter" not in msg and "nocompletion" not in msg:
                    log(f"course_completions user={uid} course={cid}: {e}", "⚠")
            done += 1
            if done % 200 == 0:
                log(f"  course_completions: {done}/{total} combinaciones procesadas")
    return rows


# ─── DATASETS CUSTOM (plugin local_stratiorep — §9.8) ─────────────────────────

def get_cohort_members_ext(moodle_url: str, token: str) -> list[dict]:
    """
    Devuelve mdl_cohort_members completo con timeadded.
    Requiere plugin local_stratiorep instalado en Moodle.
    """
    resultado = _moodle_call(
        moodle_url, token, "local_stratiorep_get_cohort_members",
    )
    return resultado if isinstance(resultado, list) else []


def get_attendance_sessions(moodle_url: str, token: str) -> list[dict]:
    """
    Sesiones de asistencia (plugin attendanceregister).
    Requiere plugin local_stratiorep instalado en Moodle.
    """
    resultado = _moodle_call(
        moodle_url, token, "local_stratiorep_get_attendance_sessions",
    )
    return resultado if isinstance(resultado, list) else []


def get_enrol_cohort_course(moodle_url: str, token: str) -> list[dict]:
    """
    Puente cohorte→curso (mdl_enrol where enrol='cohort').
    Requiere plugin local_stratiorep instalado en Moodle.
    """
    resultado = _moodle_call(
        moodle_url, token, "local_stratiorep_get_enrol_cohort_course",
    )
    return resultado if isinstance(resultado, list) else []


def get_all_grades_custom(moodle_url: str, token: str) -> list[dict]:
    """
    Alternativa rápida a get_user_grades: una sola llamada trae todo.
    Requiere plugin local_stratiorep instalado en Moodle.
    """
    resultado = _moodle_call(
        moodle_url, token, "local_stratiorep_get_all_grades",
    )
    return resultado if isinstance(resultado, list) else []


def get_users_custom(moodle_url: str, token: str) -> list[dict]:
    """
    Alternativa rápida a get_users: solo devuelve los campos necesarios.
    Mucho más rápido que core_user_get_users (sin perfil completo).
    Requiere plugin local_stratiorep instalado en Moodle.
    """
    resultado = _moodle_call(
        moodle_url, token, "local_stratiorep_get_users", _timeout=120,
    )
    return resultado if isinstance(resultado, list) else []


def get_user_enrollments_custom(moodle_url: str, token: str) -> list[dict]:
    """
    Devuelve todas las inscripciones activas (userid, courseid) en una sola llamada.
    Evita el N+1 de core_enrol_get_users_courses.
    Requiere plugin local_stratiorep instalado en Moodle.
    """
    resultado = _moodle_call(
        moodle_url, token, "local_stratiorep_get_user_enrollments", _timeout=60,
    )
    return resultado if isinstance(resultado, list) else []


def get_course_completions_custom(moodle_url: str, token: str) -> list[dict]:
    """
    Devuelve todos los registros de completion en una sola llamada.
    Evita el N+1 de core_completion_get_course_completion_status.
    Requiere plugin local_stratiorep instalado en Moodle.
    """
    resultado = _moodle_call(
        moodle_url, token, "local_stratiorep_get_course_completions", _timeout=60,
    )
    return resultado if isinstance(resultado, list) else []
