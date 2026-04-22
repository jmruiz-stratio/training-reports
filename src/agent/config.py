"""
agent/config.py — Carga de configuración desde .env y constantes del agente.
"""

import os
from shared.utils import load_env

load_env()

# ─── Moodle ───────────────────────────────────────────────────────────────────
MOODLE_URL   = os.environ.get("MOODLE_URL",   "").rstrip("/")
MOODLE_TOKEN = os.environ.get("MOODLE_TOKEN", "")

# ─── Stratio / Rocket ────────────────────────────────────────────────────────
ROCKET_URL     = os.environ.get("STRATIO_URL",    "").rstrip("/")
STRATIO_USER   = os.environ.get("STRATIO_USER",   "")
STRATIO_PASS   = os.environ.get("STRATIO_PASS",   "")
STRATIO_TENANT = os.environ.get("STRATIO_TENANT", "formacion")

# ─── HDFS ────────────────────────────────────────────────────────────────────
HDFS_BASE_PATH = os.environ.get("HDFS_BASE_PATH", "/informes/moodle")

# ─── Agente ──────────────────────────────────────────────────────────────────
WORKDIR   = os.environ.get("AGENT_WORKDIR",    "/tmp/moodle-reports-agent")
LOG_LEVEL = os.environ.get("AGENT_LOG_LEVEL",  "INFO")

# Datasets estándar (siempre se extraen)
DATASETS_STANDARD = [
    "users",
    "courses",
    "cohorts",
    "cohort_members",
    "user_courses",
    "user_grades",
    "course_completions",
]

# Datasets custom (requieren plugin local_stratiorep — §9.8)
# Si el plugin no está instalado la extracción falla con accessexception
# y el agente los omite con aviso (no aborta).
DATASETS_CUSTOM = [
    "cohort_members_ext",
    "attendance_sessions",
    "enrol_cohort_course",
]

DATASETS_ALL = DATASETS_STANDARD + DATASETS_CUSTOM
