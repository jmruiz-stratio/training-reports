-- f_certificaciones: hecho de certificaciones (solo cursos con es_certificacion=TRUE)
-- aprobado: finalgrade >= 70 (decisión §11#1)
CREATE OR REPLACE TABLE semantic.f_certificaciones AS
SELECT
  g.userid,
  g.courseid AS course_id,
  fu.partner,
  CAST(g.graderaw AS DECIMAL(5,2)) AS finalgrade,
  (CAST(g.graderaw AS DECIMAL(5,2)) >= 70) AS aprobado,
  from_unixtime(g.gradedategraded) AS fecha_nota
FROM raw.user_grades g
JOIN semantic.dim_cursos dc ON dc.course_id = g.courseid
JOIN semantic.f_usuarios fu ON fu.userid    = g.userid
WHERE g.itemtype   = 'course'
  AND g.graderaw   IS NOT NULL
  AND dc.es_certificacion = TRUE;
