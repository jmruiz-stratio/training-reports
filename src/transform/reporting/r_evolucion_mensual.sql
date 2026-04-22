-- r_evolucion_mensual: altas / horas / usuarios activos / inscritos / certificados por (mes, partner)
CREATE OR REPLACE TABLE reporting.r_evolucion_mensual AS
WITH altas AS (
  SELECT
    partner,
    date_format(fecha_alta, 'yyyy-MM') AS mes,
    COUNT(*) AS altas
  FROM semantic.f_usuarios
  GROUP BY 1, 2
),
inscritos AS (
  SELECT
    partner,
    mes_inscripcion AS mes,
    COUNT(DISTINCT userid) AS inscritos
  FROM semantic.f_inscripciones
  GROUP BY 1, 2
),
certificados AS (
  SELECT
    partner,
    date_format(fecha_nota, 'yyyy-MM') AS mes,
    COUNT(DISTINCT CASE WHEN aprobado THEN userid END) AS certificados
  FROM semantic.f_certificaciones
  GROUP BY 1, 2
),
horas AS (
  SELECT
    partner,
    mes,
    SUM(horas) AS horas,
    COUNT(DISTINCT userid) AS usuarios_activos
  FROM semantic.f_dedicacion
  GROUP BY 1, 2
)
SELECT
  COALESCE(a.partner, i.partner, c.partner, h.partner) AS partner,
  COALESCE(a.mes,     i.mes,     c.mes,     h.mes)     AS mes,
  a.altas,
  i.inscritos,
  c.certificados,
  h.horas,
  h.usuarios_activos
FROM altas a
FULL OUTER JOIN inscritos    i USING (partner, mes)
FULL OUTER JOIN certificados c USING (partner, mes)
FULL OUTER JOIN horas        h USING (partner, mes)
ORDER BY partner, mes;
