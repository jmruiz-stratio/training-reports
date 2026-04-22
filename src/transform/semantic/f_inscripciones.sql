-- f_inscripciones: hecho de inscripciones a cohortes con fecha (requiere cohort_members_ext)
CREATE OR REPLACE TABLE semantic.f_inscripciones AS
SELECT
  cm.userid,
  cm.cohortid AS cohort_id,
  fu.partner,
  dc.categoria,
  dc.version,
  from_unixtime(cm.timeadded) AS fecha_inscripcion,
  date_format(from_unixtime(cm.timeadded), 'yyyy-MM') AS mes_inscripcion
FROM raw.cohort_members_ext cm
JOIN semantic.f_usuarios   fu ON fu.userid    = cm.userid
JOIN semantic.dim_cohortes dc ON dc.cohort_id = cm.cohortid;
