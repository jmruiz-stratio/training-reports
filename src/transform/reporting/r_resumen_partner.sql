-- r_resumen_partner: un número por partner: altas, inscritos, certificados, horas, último acceso
CREATE OR REPLACE TABLE reporting.r_resumen_partner AS
SELECT
  p.partner,
  p.tipo,
  p.region,
  COUNT(DISTINCT u.userid)                                 AS total_altas,
  COUNT(DISTINCT i.userid)                                 AS total_inscritos,
  COUNT(DISTINCT CASE WHEN c.aprobado THEN c.userid END)   AS total_certificados,
  COALESCE(SUM(d.horas), 0)                                AS total_horas,
  MAX(u.ultimo_acceso)                                     AS ultimo_acceso
FROM semantic.dim_partners p
LEFT JOIN semantic.f_usuarios        u ON u.partner = p.partner
LEFT JOIN semantic.f_inscripciones   i ON i.partner = p.partner
LEFT JOIN semantic.f_certificaciones c ON c.partner = p.partner
LEFT JOIN semantic.f_dedicacion      d ON d.partner = p.partner
GROUP BY p.partner, p.tipo, p.region;
