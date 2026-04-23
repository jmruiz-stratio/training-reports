from python_core.utils import log
from . import moodle_client as c


def _is_access_denied(exc: Exception) -> bool:
    s = str(exc).lower()
    return "accessexception" in s or "webservice_access_exception" in s or "access_exception" in s


class Extractor:
    def __init__(self, moodle_url: str, token: str):
        self.moodle_url = moodle_url
        self.token = token
        self._cache: dict[str, list[dict]] = {}

    def _base(self, name: str) -> list[dict]:
        if name not in self._cache:
            self._cache[name] = self.run(name)
        return self._cache[name]

    def run(self, dataset: str) -> list[dict]:
        url, tok = self.moodle_url, self.token
        if dataset == "users":
            try:
                return c.get_users_custom(url, tok)
            except Exception:
                pass
            try:
                return c.get_users(url, tok)
            except RuntimeError as e:
                if not _is_access_denied(e):
                    raise
                try:
                    members = self._base("cohort_members_ext")
                    return c.get_users_by_ids(url, tok, list({m["userid"] for m in members}))
                except Exception:
                    return c.get_enrolled_users_by_course(url, tok, self._base("courses"))
        if dataset == "courses":
            return c.get_courses(url, tok)
        if dataset == "cohorts":
            try:
                return c.get_cohorts(url, tok)
            except RuntimeError as e:
                if not _is_access_denied(e):
                    raise
                return [{"id": cid, "name": f"cohort_{cid}", "visible": 1, "_fallback": True}
                        for cid in sorted({m["cohortid"] for m in self._base("cohort_members_ext")})]
        if dataset == "cohort_members":
            return c.get_cohort_members(url, tok, self._base("cohorts"))
        if dataset == "user_courses":
            try:
                return c.get_user_enrollments_custom(url, tok)
            except Exception:
                return c.get_user_courses(url, tok, self._base("users"))
        if dataset == "user_grades":
            try:
                return c.get_all_grades_custom(url, tok)
            except Exception:
                pass
            uc = self._base("user_courses")
            if uc:
                pairs = [(e["userid"], e.get("courseid") or e.get("id")) for e in uc if (e.get("courseid") or e.get("id"))]
                return c.get_user_grades_by_pairs(url, tok, pairs)
            return c.get_user_grades(url, tok, self._base("users"), self._base("courses"))
        if dataset == "course_completions":
            try:
                return c.get_course_completions_custom(url, tok)
            except Exception:
                pass
            uc = self._base("user_courses")
            if uc:
                pairs = [(e["userid"], e.get("courseid") or e.get("id")) for e in uc if (e.get("courseid") or e.get("id"))]
                return c.get_course_completions_by_pairs(url, tok, pairs)
            return c.get_course_completions(url, tok, self._base("users"), self._base("courses"))
        if dataset == "cohort_members_ext":
            return c.get_cohort_members_ext(url, tok)
        if dataset == "attendance_sessions":
            return c.get_attendance_sessions(url, tok)
        if dataset == "enrol_cohort_course":
            return c.get_enrol_cohort_course(url, tok)
        raise ValueError(f"Dataset desconocido: {dataset}")


def run_all(moodle_url: str, token: str, datasets: list[str]) -> dict[str, list[dict]]:
    extractor = Extractor(moodle_url, token)
    out: dict[str, list[dict]] = {}
    for ds in datasets:
        try:
            rows = extractor.run(ds)
            out[ds] = rows
            extractor._cache[ds] = rows
            log(f"{ds}: {len(rows)} filas", "✓")
        except Exception as e:
            log(f"{ds}: omitido ({e})", "⚠")
    return out
