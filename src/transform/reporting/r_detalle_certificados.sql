-- r_detalle_certificados: una fila por certificación aprobada (auditoría)
CREATE OR REPLACE TABLE reporting.r_detalle_certificados AS
SELECT
  u.userid,
  u.username,
  u.email,
  u.partner,
  dc.course_name,
  dc.categoria,
  dc.version,
  dc.idioma,
  c.finalgrade,
  c.aprobado,
  c.fecha_nota
FROM semantic.f_certificaciones c
JOIN semantic.f_usuarios u  ON u.userid    = c.userid
JOIN semantic.dim_cursos dc ON dc.course_id = c.course_id
WHERE c.aprobado = TRUE;
