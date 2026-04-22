-- r_partner_categoria: certificados y alumnos únicos por partner × categoría de curso
CREATE OR REPLACE TABLE reporting.r_partner_categoria AS
SELECT
  fu.partner,
  dc.categoria,
  COUNT(DISTINCT c.userid)                               AS alumnos,
  COUNT(DISTINCT CASE WHEN c.aprobado THEN c.userid END) AS aprobados
FROM semantic.f_certificaciones c
JOIN semantic.dim_cursos dc ON dc.course_id = c.course_id
JOIN semantic.f_usuarios fu ON fu.userid    = c.userid
GROUP BY fu.partner, dc.categoria;
