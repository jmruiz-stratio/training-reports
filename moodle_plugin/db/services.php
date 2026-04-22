<?php
defined('MOODLE_INTERNAL') || die();

$functions = [

    'local_stratiorep_get_cohort_members' => [
        'classname'   => 'local_stratiorep_external',
        'methodname'  => 'get_cohort_members',
        'description' => 'Devuelve mdl_cohort_members completo (cohortid, userid, timeadded). '
                       . 'La función estándar core_cohort_get_cohort_members no devuelve timeadded.',
        'type'        => 'read',
        'capabilities'=> '',
        'ajax'        => false,
    ],

    'local_stratiorep_get_attendance_sessions' => [
        'classname'   => 'local_stratiorep_external',
        'methodname'  => 'get_attendance_sessions',
        'description' => 'Devuelve sesiones del plugin attendanceregister '
                       . '(userid, courseid, login unix-epoch, duration segundos). '
                       . 'El plugin attendanceregister no expone webservices propios.',
        'type'        => 'read',
        'capabilities'=> '',
        'ajax'        => false,
    ],

    'local_stratiorep_get_enrol_cohort_course' => [
        'classname'   => 'local_stratiorep_external',
        'methodname'  => 'get_enrol_cohort_course',
        'description' => 'Devuelve el puente cohorte→curso de mdl_enrol '
                       . '(cohortid, courseid). No expuesto en la API estándar.',
        'type'        => 'read',
        'capabilities'=> '',
        'ajax'        => false,
    ],

    'local_stratiorep_get_all_grades' => [
        'classname'   => 'local_stratiorep_external',
        'methodname'  => 'get_all_grades',
        'description' => 'Devuelve todas las notas finales de curso en una sola llamada '
                       . '(userid, courseid, graderaw, gradedategraded). '
                       . 'Evita el N+1 de gradereport_user_get_grade_items.',
        'type'        => 'read',
        'capabilities'=> '',
        'ajax'        => false,
    ],

    'local_stratiorep_get_users' => [
        'classname'   => 'local_stratiorep_external',
        'methodname'  => 'get_users',
        'description' => 'Devuelve usuarios activos con solo los campos necesarios '
                       . '(id, username, email, firstname, lastname, timecreated, lastaccess, suspended). '
                       . 'Mucho más rápido que core_user_get_users porque no incluye perfil completo.',
        'type'        => 'read',
        'capabilities'=> '',
        'ajax'        => false,
    ],

    'local_stratiorep_get_user_enrollments' => [
        'classname'   => 'local_stratiorep_external',
        'methodname'  => 'get_user_enrollments',
        'description' => 'Devuelve todas las inscripciones activas (userid, courseid) en una sola llamada. '
                       . 'Evita el N+1 de core_enrol_get_users_courses.',
        'type'        => 'read',
        'capabilities'=> '',
        'ajax'        => false,
    ],

    'local_stratiorep_get_course_completions' => [
        'classname'   => 'local_stratiorep_external',
        'methodname'  => 'get_course_completions',
        'description' => 'Devuelve todos los registros de completion de cursos en una sola llamada. '
                       . 'Evita el N+1 de core_completion_get_course_completion_status.',
        'type'        => 'read',
        'capabilities'=> '',
        'ajax'        => false,
    ],

];

$services = [
    'Stratio Reports' => [
        'functions'       => array_keys($functions),
        'restrictedusers' => 1,
        'enabled'         => 1,
        'shortname'       => 'stratiorep',
    ],
];
