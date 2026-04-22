-- dim_cohortes: dimensión de cohortes con categoría, versión e idioma derivados del nombre
CREATE OR REPLACE TABLE semantic.dim_cohortes AS
SELECT
  id AS cohort_id,
  name AS cohort_name,
  CASE
    WHEN LOWER(name) LIKE '%governance%'      THEN 'Governance'
    WHEN LOWER(name) LIKE '%data processing%' THEN 'Data Processing'
    WHEN LOWER(name) LIKE '%intelligence%'    THEN 'Intelligence'
    WHEN LOWER(name) LIKE '%operaciones%'     THEN 'Operaciones'
    ELSE 'Otros'
  END AS categoria,
  NULLIF(regexp_extract(name, '(1[34]\\.[0-9])', 1), '') AS version,
  CASE
    WHEN name LIKE '% - ES' THEN 'ES'
    WHEN name LIKE '% - EN' THEN 'EN'
    WHEN name LIKE '% - FR' THEN 'FR'
    ELSE NULL
  END AS idioma,
  CAST(visible AS BOOLEAN) AS visible
FROM raw.cohorts;
