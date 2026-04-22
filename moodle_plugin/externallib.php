<?php
defined('MOODLE_INTERNAL') || die();

require_once($CFG->libdir . '/externallib.php');

class local_stratiorep_external extends external_api {

    // ── get_cohort_members ────────────────────────────────────────────────────

    public static function get_cohort_members_parameters() {
        return new external_function_parameters([]);
    }

    public static function get_cohort_members() {
        global $DB;
        // get_records_sql indexa por la primera columna — necesitamos clave única
        $rows = $DB->get_records_sql(
            "SELECT CONCAT(cohortid, '_', userid) AS recid, cohortid, userid, timeadded
               FROM {cohort_members}
              ORDER BY cohortid, userid"
        );
        return array_values(array_map(fn($r) => [
            'cohortid'  => (int) $r->cohortid,
            'userid'    => (int) $r->userid,
            'timeadded' => (int) $r->timeadded,
        ], $rows));
    }

    public static function get_cohort_members_returns() {
        return new external_multiple_structure(
            new external_single_structure([
                'cohortid'  => new external_value(PARAM_INT,  'ID de la cohorte'),
                'userid'    => new external_value(PARAM_INT,  'ID del usuario'),
                'timeadded' => new external_value(PARAM_INT,  'Unix epoch de alta en la cohorte'),
            ])
        );
    }

    // ── get_attendance_sessions ───────────────────────────────────────────────

    public static function get_attendance_sessions_parameters() {
        return new external_function_parameters([]);
    }

    public static function get_attendance_sessions() {
        global $DB;
        // mdl_attendanceregister_session.register → mdl_attendanceregister.course
        $rows = $DB->get_records_sql(
            'SELECT s.id, s.userid, r.course AS courseid, s.login, s.duration
               FROM {attendanceregister_session} s
               JOIN {attendanceregister} r ON r.id = s.register
              ORDER BY s.userid, r.course, s.login'
        );
        return array_values(array_map(fn($r) => (array) $r, $rows));
    }

    public static function get_attendance_sessions_returns() {
        return new external_multiple_structure(
            new external_single_structure([
                'id'       => new external_value(PARAM_INT,  'ID de la sesión'),
                'userid'   => new external_value(PARAM_INT,  'ID del usuario'),
                'courseid' => new external_value(PARAM_INT,  'ID del curso'),
                'login'    => new external_value(PARAM_INT,  'Unix epoch de inicio de sesión'),
                'duration' => new external_value(PARAM_INT,  'Duración en segundos'),
            ])
        );
    }

    // ── get_enrol_cohort_course ───────────────────────────────────────────────

    public static function get_enrol_cohort_course_parameters() {
        return new external_function_parameters([]);
    }

    public static function get_enrol_cohort_course() {
        global $DB;
        // customint1 almacena el cohortid en los registros enrol='cohort'
        $rows = $DB->get_records_sql(
            "SELECT id, customint1 AS cohortid, courseid
               FROM {enrol}
              WHERE enrol = 'cohort'
                AND customint1 IS NOT NULL
              ORDER BY customint1, courseid"
        );
        return array_values(array_map(fn($r) => (array) $r, $rows));
    }

    public static function get_enrol_cohort_course_returns() {
        return new external_multiple_structure(
            new external_single_structure([
                'id'       => new external_value(PARAM_INT, 'ID del registro enrol'),
                'cohortid' => new external_value(PARAM_INT, 'ID de la cohorte'),
                'courseid' => new external_value(PARAM_INT, 'ID del curso'),
            ])
        );
    }

    // ── get_users ─────────────────────────────────────────────────────────────

    public static function get_users_parameters() {
        return new external_function_parameters([]);
    }

    public static function get_users() {
        global $DB;
        $rows = $DB->get_records_sql(
            'SELECT id, username, email, firstname, lastname, timecreated, lastaccess, suspended
               FROM {user}
              WHERE deleted = 0 AND id > 1
              ORDER BY id'
        );
        return array_values(array_map(fn($r) => (array) $r, $rows));
    }

    public static function get_users_returns() {
        return new external_multiple_structure(
            new external_single_structure([
                'id'          => new external_value(PARAM_INT,    'ID del usuario'),
                'username'    => new external_value(PARAM_TEXT,   'Username'),
                'email'       => new external_value(PARAM_EMAIL,  'Email'),
                'firstname'   => new external_value(PARAM_TEXT,   'Nombre'),
                'lastname'    => new external_value(PARAM_TEXT,   'Apellidos'),
                'timecreated' => new external_value(PARAM_INT,    'Unix epoch de creación'),
                'lastaccess'  => new external_value(PARAM_INT,    'Unix epoch de último acceso'),
                'suspended'   => new external_value(PARAM_INT,    '1 si suspendido'),
            ])
        );
    }

    // ── get_user_enrollments ──────────────────────────────────────────────────

    public static function get_user_enrollments_parameters() {
        return new external_function_parameters([]);
    }

    public static function get_user_enrollments() {
        global $DB;
        $rows = $DB->get_records_sql(
            'SELECT CONCAT(ue.userid, \'_\', e.courseid) AS id,
                    ue.userid, e.courseid
               FROM {user_enrolments} ue
               JOIN {enrol} e ON e.id = ue.enrolid
              WHERE ue.status = 0 AND e.status = 0
              ORDER BY ue.userid, e.courseid'
        );
        return array_values(array_map(fn($r) => [
            'userid'   => (int) $r->userid,
            'courseid' => (int) $r->courseid,
        ], $rows));
    }

    public static function get_user_enrollments_returns() {
        return new external_multiple_structure(
            new external_single_structure([
                'userid'   => new external_value(PARAM_INT, 'ID del usuario'),
                'courseid' => new external_value(PARAM_INT, 'ID del curso'),
            ])
        );
    }

    // ── get_course_completions ────────────────────────────────────────────────

    public static function get_course_completions_parameters() {
        return new external_function_parameters([]);
    }

    public static function get_course_completions() {
        global $DB;
        $rows = $DB->get_records_sql(
            'SELECT id, userid, course AS courseid,
                    CASE WHEN timecompleted > 0 THEN 1 ELSE 0 END AS completed,
                    timecompleted
               FROM {course_completions}
              ORDER BY userid, course'
        );
        return array_values(array_map(fn($r) => [
            'userid'        => (int) $r->userid,
            'courseid'      => (int) $r->courseid,
            'completed'     => (int) $r->completed,
            'timecompleted' => (int) $r->timecompleted,
        ], $rows));
    }

    public static function get_course_completions_returns() {
        return new external_multiple_structure(
            new external_single_structure([
                'userid'        => new external_value(PARAM_INT, 'ID del usuario'),
                'courseid'      => new external_value(PARAM_INT, 'ID del curso'),
                'completed'     => new external_value(PARAM_INT, '1 si completado'),
                'timecompleted' => new external_value(PARAM_INT, 'Unix epoch de completion (0 si no completado)'),
            ])
        );
    }

    // ── get_all_grades ────────────────────────────────────────────────────────

    public static function get_all_grades_parameters() {
        return new external_function_parameters([]);
    }

    public static function get_all_grades() {
        global $DB;
        // Para itemtype='course' la nota calculada está en finalgrade, no en rawgrade
        $rows = $DB->get_records_sql(
            "SELECT gg.id, gg.userid, gi.courseid, gg.finalgrade AS graderaw,
                    gg.timemodified AS gradedategraded
               FROM {grade_grades} gg
               JOIN {grade_items} gi ON gi.id = gg.itemid
              WHERE gi.itemtype = 'course'
                AND gg.finalgrade IS NOT NULL
              ORDER BY gg.userid, gi.courseid"
        );
        return array_values(array_map(fn($r) => (array) $r, $rows));
    }

    public static function get_all_grades_returns() {
        return new external_multiple_structure(
            new external_single_structure([
                'id'              => new external_value(PARAM_INT,   'ID del registro grade_grades'),
                'userid'          => new external_value(PARAM_INT,   'ID del usuario'),
                'courseid'        => new external_value(PARAM_INT,   'ID del curso'),
                'graderaw'        => new external_value(PARAM_FLOAT, 'Nota numérica (0-100)'),
                'gradedategraded' => new external_value(PARAM_INT,   'Unix epoch de la última modificación'),
            ])
        );
    }
}
