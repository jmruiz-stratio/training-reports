-- f_actividad: primer y último acceso por (usuario, curso) desde attendance_sessions
CREATE OR REPLACE TABLE semantic.f_actividad AS
WITH sesiones AS (
  SELECT
    s.userid,
    s.courseid AS course_id,
    MIN(from_unixtime(s.login)) AS primer_acceso,
    MAX(from_unixtime(s.login)) AS ultimo_acceso
  FROM raw.attendance_sessions s
  GROUP BY s.userid, s.courseid
)
SELECT
  se.userid,
  se.course_id,
  fu.partner,
  TRUE AS tiene_actividad,
  se.primer_acceso,
  se.ultimo_acceso
FROM sesiones se
JOIN semantic.f_usuarios fu ON fu.userid = se.userid;
