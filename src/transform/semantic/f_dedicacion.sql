-- f_dedicacion: horas por (usuario, curso, mes) desde attendance_sessions
CREATE OR REPLACE TABLE semantic.f_dedicacion AS
SELECT
  s.userid,
  s.courseid AS course_id,
  fu.partner,
  date_format(date_trunc('month', from_unixtime(s.login)), 'yyyy-MM') AS mes,
  ROUND(SUM(s.duration) / 3600.0, 2) AS horas
FROM raw.attendance_sessions s
JOIN semantic.f_usuarios fu ON fu.userid = s.userid
GROUP BY
  s.userid,
  s.courseid,
  fu.partner,
  date_trunc('month', from_unixtime(s.login));
