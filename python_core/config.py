from dataclasses import dataclass
import os
from python_core.utils import load_env


@dataclass(frozen=True)
class Settings:
    moodle_url: str
    moodle_token: str
    stratio_url: str
    stratio_user: str
    stratio_pass: str
    stratio_tenant: str
    hdfs_base_path: str
    workdir: str


DATASETS_STANDARD = [
    "users", "courses", "cohorts", "cohort_members",
    "user_courses", "user_grades", "course_completions",
]
DATASETS_CUSTOM = ["cohort_members_ext", "attendance_sessions", "enrol_cohort_course"]
DATASETS_ALL = DATASETS_STANDARD + DATASETS_CUSTOM


def load_settings(env_path: str = ".env") -> Settings:
    load_env(env_path)
    return Settings(
        moodle_url=os.environ.get("MOODLE_URL", "").rstrip("/"),
        moodle_token=os.environ.get("MOODLE_TOKEN", ""),
        stratio_url=os.environ.get("STRATIO_URL", "").rstrip("/"),
        stratio_user=os.environ.get("STRATIO_USER", ""),
        stratio_pass=os.environ.get("STRATIO_PASS", ""),
        stratio_tenant=os.environ.get("STRATIO_TENANT", "formacion"),
        hdfs_base_path=os.environ.get("HDFS_BASE_PATH", "/informes/moodle"),
        workdir=os.environ.get("AGENT_WORKDIR", "/tmp/moodle-reports-agent"),
    )
