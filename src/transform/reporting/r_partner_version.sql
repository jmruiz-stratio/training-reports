-- r_partner_version: matriz partner × versión de certificaciones
CREATE OR REPLACE TABLE reporting.r_partner_version AS
SELECT
  fu.partner,
  dc.version,
  COUNT(DISTINCT c.userid)                               AS alumnos,
  COUNT(DISTINCT CASE WHEN c.aprobado THEN c.userid END) AS aprobados
FROM semantic.f_certificaciones c
JOIN semantic.dim_cursos dc ON dc.course_id = c.course_id
JOIN semantic.f_usuarios fu ON fu.userid    = c.userid
WHERE dc.version IS NOT NULL
GROUP BY fu.partner, dc.version;
