"""
agent/extract.py — Orquestador de extracción RAW desde Moodle.

run(dataset, moodle_url, token) → list[dict]

Para los datasets N+1 (user_courses, user_grades, course_completions,
cohort_members) necesita los datasets padre ya extraídos; se pasan como
caché en memoria para no repetir llamadas.
"""

from shared.utils import log
from shared.moodle_api import (
    get_users,
    get_users_by_ids,
    get_enrolled_users_by_course,
    get_courses,
    get_cohorts,
    get_cohort_members,
    get_user_courses,
    get_user_grades,
    get_user_grades_by_pairs,
    get_course_completions,
    get_course_completions_by_pairs,
    get_cohort_members_ext,
    get_attendance_sessions,
    get_enrol_cohort_course,
    get_all_grades_custom,
    get_users_custom,
    get_user_enrollments_custom,
    get_course_completions_custom,
)


def _is_access_denied(exc: Exception) -> bool:
    """Moodle devuelve accessexception o webservice_access_exception según la versión."""
    s = str(exc).lower()
    return "accessexception" in s or "webservice_access_exception" in s or "access_exception" in s


class Extractor:
    """
    Mantiene en caché los datasets base (users, courses, cohorts) para
    reutilizarlos en las llamadas N+1 sin volver a pedirlos a Moodle.
    """

    def __init__(self, moodle_url: str, token: str):
        self.moodle_url = moodle_url
        self.token      = token
        self._cache: dict[str, list[dict]] = {}

    def _base(self, name: str) -> list[dict]:
        if name not in self._cache:
            self._cache[name] = self.run(name)
        return self._cache[name]

    def run(self, dataset: str) -> list[dict]:
        url, tok = self.moodle_url, self.token

        if dataset == "users":
            log("Extrayendo users...")
            # Intenta primero la función custom (campos mínimos, una sola llamada rápida)
            try:
                rows = get_users_custom(url, tok)
                log(f"users: {len(rows)} filas (custom)", "✓")
                return rows
            except Exception as e:
                log(f"local_stratiorep_get_users no disponible ({e}), usando core_user_get_users...", "⚠")
            try:
                rows = get_users(url, tok)
            except RuntimeError as e:
                if not _is_access_denied(e):
                    raise
                # Fallback 1: IDs desde cohort_members_ext → core_user_get_users_by_field
                log("core_user_get_users sin acceso — intentando fallback vía cohort_members_ext", "⚠")
                try:
                    members = self._base("cohort_members_ext")
                    user_ids = list({m["userid"] for m in members})
                    log(f"  Resolviendo {len(user_ids)} usuarios únicos vía core_user_get_users_by_field...")
                    rows = get_users_by_ids(url, tok, user_ids)
                except Exception:
                    # Fallback 2: iterar por curso con core_enrol_get_enrolled_users
                    log("cohort_members_ext no disponible — fallback vía enrolled users por curso", "⚠")
                    courses = self._base("courses")
                    log(f"  Iterando {len(courses)} cursos para obtener usuarios matriculados...")
                    rows = get_enrolled_users_by_course(url, tok, courses)
            log(f"users: {len(rows)} filas", "✓")
            return rows

        elif dataset == "courses":
            log("Extrayendo courses...")
            rows = get_courses(url, tok)
            log(f"courses: {len(rows)} filas", "✓")
            return rows

        elif dataset == "cohorts":
            log("Extrayendo cohorts...")
            try:
                rows = get_cohorts(url, tok)
            except RuntimeError as e:
                if not _is_access_denied(e):
                    raise
                log("core_cohort_get_cohorts sin acceso — intentando fallback desde cohort_members_ext", "⚠")
                try:
                    members = self._base("cohort_members_ext")
                    unique_ids = sorted({m["cohortid"] for m in members})
                    log("  ⚠  Nombres de cohorte no disponibles: categoría/versión/idioma = desconocidos", "⚠")
                    rows = [{"id": cid, "name": f"cohort_{cid}", "visible": 1,
                             "_fallback": True} for cid in unique_ids]
                except Exception:
                    # Sin cohort_members_ext tampoco: devolver lista vacía
                    log("cohort_members_ext tampoco disponible — cohorts vacío hasta habilitar funciones", "⚠")
                    rows = []
            log(f"cohorts: {len(rows)} filas", "✓")
            return rows

        elif dataset == "cohort_members":
            cohorts = self._base("cohorts")
            log(f"Extrayendo cohort_members ({len(cohorts)} cohortes)...")
            rows = get_cohort_members(url, tok, cohorts)
            log(f"cohort_members: {len(rows)} filas", "✓")
            return rows

        elif dataset == "user_courses":
            # Intenta primero la función custom (una sola llamada, sin N+1)
            try:
                log("Extrayendo user_courses vía custom (local_stratiorep_get_user_enrollments)...")
                rows = get_user_enrollments_custom(url, tok)
                log(f"user_courses: {len(rows)} filas (custom)", "✓")
                return rows
            except Exception as e:
                log(f"local_stratiorep_get_user_enrollments no disponible ({e}), usando N+1...", "⚠")
            users = self._base("users")
            log(f"Extrayendo user_courses N+1 ({len(users)} usuarios)...")
            rows = get_user_courses(url, tok, users)
            log(f"user_courses: {len(rows)} filas", "✓")
            return rows

        elif dataset == "user_grades":
            # Intenta primero la función custom (una sola llamada, mucho más rápida)
            try:
                log("Extrayendo user_grades vía custom (local_stratiorep_get_all_grades)...")
                rows = get_all_grades_custom(url, tok)
                log(f"user_grades: {len(rows)} filas (custom)", "✓")
                return rows
            except Exception as e:
                if not _is_access_denied(e):
                    log(f"Custom falló ({e}), usando N+1...", "⚠")
                else:
                    log("Plugin custom sin acceso, usando N+1...", "⚠")

            # N+1 optimizado: solo pares (usuario, curso) en que el usuario está inscrito
            user_courses_data = self._base("user_courses")
            if user_courses_data:
                # custom devuelve {userid, courseid}; core N+1 devuelve {userid, id (=courseid)}
                pairs = [
                    (e["userid"], e.get("courseid") or e.get("id"))
                    for e in user_courses_data
                    if e.get("courseid") or e.get("id")
                ]
                log(f"Extrayendo user_grades N+1 optimizado ({len(pairs)} pares inscritos)...")
                rows = get_user_grades_by_pairs(url, tok, pairs)
            else:
                # Último recurso: producto cartesiano completo
                users   = self._base("users")
                courses = self._base("courses")
                log(f"Extrayendo user_grades N+1 completo ({len(users)} × {len(courses)})...")
                rows = get_user_grades(url, tok, users, courses)
            log(f"user_grades: {len(rows)} filas", "✓")
            return rows

        elif dataset == "course_completions":
            # Intenta primero la función custom (una sola llamada)
            try:
                log("Extrayendo course_completions vía custom (local_stratiorep_get_course_completions)...")
                rows = get_course_completions_custom(url, tok)
                log(f"course_completions: {len(rows)} filas (custom)", "✓")
                return rows
            except Exception as e:
                log(f"local_stratiorep_get_course_completions no disponible ({e}), usando N+1...", "⚠")
            # Fallback: usa user_courses para limitar a pares realmente inscritos
            user_courses_data = self._base("user_courses")
            if user_courses_data:
                pairs_uc = [
                    (e["userid"], e.get("courseid") or e.get("id"))
                    for e in user_courses_data
                    if e.get("courseid") or e.get("id")
                ]
                log(f"Extrayendo course_completions N+1 ({len(pairs_uc)} pares inscritos)...")
                rows = get_course_completions_by_pairs(url, tok, pairs_uc)
            else:
                users   = self._base("users")
                courses = self._base("courses")
                log(f"Extrayendo course_completions N+1 completo ({len(users)}×{len(courses)})...")
                rows = get_course_completions(url, tok, users, courses)
            log(f"course_completions: {len(rows)} filas", "✓")
            return rows

        # ── Custom (plugin local_stratiorep) ──────────────────────────────────

        elif dataset == "cohort_members_ext":
            log("Extrayendo cohort_members_ext (custom)...")
            rows = get_cohort_members_ext(url, tok)
            log(f"cohort_members_ext: {len(rows)} filas", "✓")
            return rows

        elif dataset == "attendance_sessions":
            log("Extrayendo attendance_sessions (custom)...")
            rows = get_attendance_sessions(url, tok)
            log(f"attendance_sessions: {len(rows)} filas", "✓")
            return rows

        elif dataset == "enrol_cohort_course":
            log("Extrayendo enrol_cohort_course (custom)...")
            rows = get_enrol_cohort_course(url, tok)
            log(f"enrol_cohort_course: {len(rows)} filas", "✓")
            return rows

        else:
            raise ValueError(f"Dataset desconocido: {dataset!r}")


def run_all(moodle_url: str, token: str,
            datasets: list[str]) -> dict[str, list[dict]]:
    """
    Extrae todos los datasets indicados y devuelve {nombre: [filas]}.
    Los datasets custom que fallen por plugin no instalado se omiten con aviso.
    """
    extractor = Extractor(moodle_url, token)
    results: dict[str, list[dict]] = {}

    for dataset in datasets:
        try:
            rows = extractor.run(dataset)
            results[dataset] = rows
            extractor._cache[dataset] = rows   # evita doble extracción si otro dataset lo necesita
        except Exception as e:
            if _is_access_denied(e):
                log(f"{dataset}: función sin acceso en el servicio del token, omitido", "⚠")
                results[dataset] = []
            else:
                raise RuntimeError(f"Error extrayendo {dataset}: {e}") from e

    return results
