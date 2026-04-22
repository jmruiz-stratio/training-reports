-- f_usuarios: hecho de usuarios con partner derivado del username/email
CREATE OR REPLACE TABLE semantic.f_usuarios AS
SELECT
  u.id AS userid,
  u.username,
  u.email,
  concat(u.firstname, ' ', u.lastname) AS nombre_completo,
  CASE
    WHEN LOWER(u.email) LIKE '%stratio%' OR LOWER(u.username) LIKE '%stratio%' THEN 'stratio'
    ELSE reverse(split(reverse(u.username), '-')[0])
  END AS partner,
  from_unixtime(u.timecreated) AS fecha_alta,
  from_unixtime(u.lastaccess)  AS ultimo_acceso,
  (u.suspended = 0) AS activo
FROM raw.users u;
