"""Thin wrapper around Moodle webservice calls."""

from shared import moodle_api

get_users = moodle_api.get_users
get_users_by_ids = moodle_api.get_users_by_ids
get_enrolled_users_by_course = moodle_api.get_enrolled_users_by_course
get_courses = moodle_api.get_courses
get_cohorts = moodle_api.get_cohorts
get_cohort_members = moodle_api.get_cohort_members
get_user_courses = moodle_api.get_user_courses
get_user_grades = moodle_api.get_user_grades
get_user_grades_by_pairs = moodle_api.get_user_grades_by_pairs
get_course_completions = moodle_api.get_course_completions
get_course_completions_by_pairs = moodle_api.get_course_completions_by_pairs
get_cohort_members_ext = moodle_api.get_cohort_members_ext
get_attendance_sessions = moodle_api.get_attendance_sessions
get_enrol_cohort_course = moodle_api.get_enrol_cohort_course
get_all_grades_custom = moodle_api.get_all_grades_custom
get_users_custom = moodle_api.get_users_custom
get_user_enrollments_custom = moodle_api.get_user_enrollments_custom
get_course_completions_custom = moodle_api.get_course_completions_custom
