-- r_alertas: partners sin actividad en los últimos 30 días
CREATE OR REPLACE TABLE reporting.r_alertas AS
SELECT
  partner,
  MAX(ultimo_acceso)                                              AS ultimo_acceso,
  DATEDIFF(CURRENT_DATE, CAST(MAX(ultimo_acceso) AS DATE))       AS dias_sin_actividad
FROM semantic.f_usuarios
GROUP BY partner
HAVING MAX(ultimo_acceso) < date_sub(CURRENT_DATE, 30);
