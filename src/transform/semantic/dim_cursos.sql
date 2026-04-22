-- dim_cursos: dimensión de cursos con flag de certificación, categoría, versión e idioma
CREATE OR REPLACE TABLE semantic.dim_cursos AS
SELECT
  id AS course_id,
  fullname AS course_name,
  (LOWER(fullname) LIKE '%certificación%' OR LOWER(fullname) LIKE '%certification%') AS es_certificacion,
  CASE
    WHEN LOWER(fullname) LIKE '%governance%'      THEN 'Governance'
    WHEN LOWER(fullname) LIKE '%data processing%' THEN 'Data Processing'
    WHEN LOWER(fullname) LIKE '%intelligence%'    THEN 'Intelligence'
    WHEN LOWER(fullname) LIKE '%operaciones%'     THEN 'Operaciones'
    ELSE 'Otros'
  END AS categoria,
  NULLIF(regexp_extract(fullname, '(1[34]\\.[0-9])', 1), '') AS version,
  CASE
    WHEN fullname LIKE '% - ES' THEN 'ES'
    WHEN fullname LIKE '% - EN' THEN 'EN'
    WHEN fullname LIKE '% - FR' THEN 'FR'
    ELSE NULL
  END AS idioma
FROM raw.courses;
