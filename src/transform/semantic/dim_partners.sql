-- dim_partners: dimensión de partners derivada de usuarios + tabla maestra
CREATE OR REPLACE TABLE semantic.dim_partners AS
WITH partners_from_users AS (
  SELECT DISTINCT
    CASE
      WHEN LOWER(email) LIKE '%stratio%' OR LOWER(username) LIKE '%stratio%' THEN 'stratio'
      ELSE reverse(split(reverse(username), '-')[0])
    END AS partner
  FROM raw.users
)
SELECT
  p.partner,
  m.tipo,
  m.region,
  m.trajo_oportunidades,
  m.trajo_clientes,
  m.paga_certificacion,
  m.total_pagado,
  m.notas
FROM partners_from_users p
LEFT JOIN raw.partners_meta m ON m.partner = p.partner;
