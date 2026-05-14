#!/usr/bin/env python3
"""
practices-session-extractor

Lee los logs de oauth2-proxy en keos-auth, extrae sesiones de alumnos
y las indexa en OpenSearch (formacion-datastores).

Eventos que parsea:
  [AuthSuccess]  → inicio de sesión (email, tenant, groups, created, expires)
  /oauth2/auth   → actividad de sesión (actualiza last_seen por email/IP)
  /oauth2/sign_out → fin de sesión (actualiza fecha_fin y certficación practicada)

Se ejecuta como CronJob diario en formacion-apps.
"""
import json
import re
import ssl
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime

# ── Configuración ─────────────────────────────────────────────────────────────
NAMESPACE   = os.getenv("KEOS_AUTH_NS",   "keos-auth")
OS_HOST     = os.getenv("OS_HOST",        "opensearch-coordinator.formacion-datastores.svc.certspractices.int")
OS_PORT     = int(os.getenv("OS_PORT",    "9200"))
OS_INDEX    = os.getenv("OS_INDEX",       "practices_sessions")
CERT_FILE   = os.getenv("TLS_CERT",      "/certs/tls.crt")
KEY_FILE    = os.getenv("TLS_KEY",       "/certs/tls.key")
K8S_TOKEN_F = "/var/run/secrets/kubernetes.io/serviceaccount/token"
K8S_CA_F    = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
K8S_API     = "https://kubernetes.default.svc.certspractices.int"

STUDENT_TENANTS = {"formacion", "stratio"}

CERT_MAP = [
    ("governance",    "Governance"),
    ("intelligence",  "Intelligence"),
    ("discovery",     "Data Processing"),
    ("virtualizer",   "Data Processing"),
    ("rocket",        "Operaciones"),
    ("genai",         "AI"),
]

# Mapeo canónico dominio → nombre de grupo/partner
DOMAIN_PARTNER = {
    "pichincha.com":              "Pichincha",
    "sri.gob.ec":                 "sri",
    "baninter.com":               "bancointernacional",
    "bancointernacional.ec":      "bancointernacional",
    "policia.es":                 "policia",
    "ineco.com":                  "ineco",
    "mivau.gob.es":               "sgad",
    "externos.sanidad.gob.es":    "sgad",
    "seg-social.es":              "sgad",
    "mintur.es":                  "sgad",
    "digital.gob.es":             "sgad",
    "mites.gob.es":               "sgad",
    "tcu.es":                     "sgad",
    "miteco.es":                  "sgad",
    "aemps.es":                   "sgad",
    "sanidad.gob.es":             "sgad",
    "inferia.io":                 "sgad",
    "soprasteria.com":            "SopraSteria",
    "soprasterianext.com":        "SopraSteria",
    "bigspark.dev":               "BigSpark",
    "myqorg.com":                 "myq",
    "myqorg.biz":                 "myq",
    "centrohub.co":               "centrohub",
    "telefonica.com":             "telefonica",
    "gruposolutia.com":           "GrupoSolutia",
    "hiberus.com":                "hiberus",
    "emeal.nttdata.com":          "nttdata",
    "nttdata.com":                "nttdata",
}


def log(msg):
    print(f"[{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}] {msg}", flush=True)


# ── Kubernetes API ─────────────────────────────────────────────────────────────

def _k8s_ctx():
    token = open(K8S_TOKEN_F).read().strip()
    ctx = ssl.create_default_context(cafile=K8S_CA_F)
    return token, ctx


def k8s_get_json(path):
    token, ctx = _k8s_ctx()
    req = urllib.request.Request(
        f"{K8S_API}{path}",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, context=ctx) as r:
        return json.loads(r.read())


def k8s_get_logs(ns, pod):
    token, ctx = _k8s_ctx()
    req = urllib.request.Request(
        f"{K8S_API}/api/v1/namespaces/{ns}/pods/{pod}/log",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, context=ctx) as r:
        return r.read().decode("utf-8", errors="replace")


def get_oauth2_proxy_pods():
    try:
        data = k8s_get_json(
            f"/api/v1/namespaces/{NAMESPACE}/pods"
            f"?labelSelector=app.kubernetes.io%2Fname%3Doauth2-proxy"
        )
        names = [p["metadata"]["name"] for p in data.get("items", [])]
        if names:
            return names
    except Exception:
        pass
    # fallback: todos los pods y filtramos
    data = k8s_get_json(f"/api/v1/namespaces/{NAMESPACE}/pods")
    return [
        p["metadata"]["name"] for p in data.get("items", [])
        if "oauth2-proxy" in p["metadata"]["name"]
    ]


# ── OpenSearch ─────────────────────────────────────────────────────────────────

def _os_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.load_cert_chain(CERT_FILE, KEY_FILE)
    return ctx


def os_ensure_index():
    mapping = {
        "mappings": {
            "properties": {
                "email":         {"type": "keyword"},
                "user":          {"type": "keyword"},
                "partner":       {"type": "keyword"},
                "tenant":        {"type": "keyword"},
                "fecha_inicio":  {"type": "date", "format": "yyyy-MM-dd HH:mm:ss||epoch_millis"},
                "fecha_fin":     {"type": "date", "format": "yyyy-MM-dd HH:mm:ss||epoch_millis"},
                "last_seen":     {"type": "date", "format": "yyyy-MM-dd HH:mm:ss||epoch_millis"},
                "certificacion": {"type": "keyword"},
                "groups":        {"type": "keyword"},
            }
        }
    }
    ctx = _os_ctx()
    req = urllib.request.Request(
        f"https://{OS_HOST}:{OS_PORT}/{OS_INDEX}",
        data=json.dumps(mapping).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req, context=ctx) as r:
            log(f"Índice '{OS_INDEX}' creado")
    except urllib.error.HTTPError as e:
        if e.code in (400, 404):
            pass  # ya existe
        else:
            raise


def os_bulk_index(docs):
    if not docs:
        return
    ctx = _os_ctx()
    lines = []
    for doc in docs:
        doc_id = f"{doc['user']}_{doc['fecha_inicio'].replace(' ', 'T')}"
        lines.append(json.dumps({"index": {"_index": OS_INDEX, "_id": doc_id}}))
        lines.append(json.dumps(doc))
    body = "\n".join(lines) + "\n"
    req = urllib.request.Request(
        f"https://{OS_HOST}:{OS_PORT}/_bulk",
        data=body.encode(),
        headers={"Content-Type": "application/x-ndjson"},
        method="POST"
    )
    with urllib.request.urlopen(req, context=ctx) as r:
        resp = json.loads(r.read())
    errors = [i for i in resp.get("items", []) if "error" in i.get("index", {})]
    log(f"  Bulk: {len(resp['items'])} docs | errores: {len(errors)}")
    for e in errors[:3]:
        log(f"  ERROR doc: {e['index'].get('error')}")


# ── Parseo de logs ─────────────────────────────────────────────────────────────

def _ts_parse(s):
    """Convierte timestamp del log (2026/05/13 13:22:03) a string normalizado."""
    try:
        return datetime.strptime(s, "%Y/%m/%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return s


def _partner_from_email(email):
    domain = email.split("@")[-1] if "@" in email else email
    return DOMAIN_PARTNER.get(domain, domain.split(".")[0])


def _cert_from_path(path):
    path_lower = path.lower()
    for key, val in CERT_MAP:
        if key in path_lower:
            return val
    return None


def parse_logs(raw_logs):
    """
    Devuelve lista de dicts de sesión.
    Estrategia:
      1. AuthSuccess  → crea sesión keyed by (email, created)
      2. /oauth2/auth → actualiza last_seen por source_ip
      3. sign_out     → cierra sesión por source_ip más cercana
    """
    sessions = {}        # (email, fecha_inicio) → doc
    ip_to_email = {}     # source_ip → email más reciente
    ip_last_seen = {}    # source_ip → last_seen timestamp

    for line in raw_logs.splitlines():
        # ── AuthSuccess ────────────────────────────────────────────────────────
        if "[AuthSuccess]" in line:
            ip_m      = re.match(r'(\d+\.\d+\.\d+\.\d+):', line)
            email_m   = re.search(r'(\S+@\S+) \[\d{4}/\d{2}/\d{2}', line)
            tenant_m  = re.search(r'\btenant:(\w+)', line)
            user_m    = re.search(r'\buser:(\S+)', line)
            created_m = re.search(r'\bcreated:(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            expires_m = re.search(r'\bexpires:(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            groups_m  = re.search(r'\bgroups:\[([^\]]+)\]', line)

            if not (email_m and tenant_m and created_m and expires_m):
                continue
            tenant = tenant_m.group(1)
            if tenant not in STUDENT_TENANTS:
                continue

            email   = email_m.group(1)
            user    = user_m.group(1) if user_m else email.split("@")[0]
            created = created_m.group(1)
            expires = expires_m.group(1)
            groups  = groups_m.group(1).split() if groups_m else []
            src_ip  = ip_m.group(1) if ip_m else None

            key = (email, created)
            sessions[key] = {
                "email":        email,
                "user":         user,
                "partner":      _partner_from_email(email),
                "tenant":       tenant,
                "fecha_inicio": created,
                "fecha_fin":    expires,
                "last_seen":    created,
                "groups":       groups,
                "_src_ip":      src_ip,
            }
            if src_ip:
                ip_to_email[src_ip] = (email, created)
            continue

        # ── /oauth2/auth (actividad) ────────────────────────────────────────────
        if "/oauth2/auth" in line and " 202 " in line:
            ip_m    = re.match(r'(\d+\.\d+\.\d+\.\d+):', line)
            ts_m    = re.search(r'\[(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\]', line)
            email_m = re.search(r'(\S+@\S+) \[\d{4}/\d{2}/\d{2}', line)
            if not (ip_m and ts_m):
                continue
            src_ip = ip_m.group(1)
            ts_str = _ts_parse(ts_m.group(1))
            if email_m:
                email = email_m.group(1)
                ip_to_email[src_ip] = ip_to_email.get(src_ip) or (email, None)
            ip_last_seen[src_ip] = max(
                ip_last_seen.get(src_ip, ""), ts_str
            )
            continue

        # ── sign_out ────────────────────────────────────────────────────────────
        if "sign_out" in line:
            ip_m = re.match(r'(\d+\.\d+\.\d+\.\d+):', line)
            ts_m = re.search(r'\[(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\]', line)
            if not (ip_m and ts_m):
                continue
            src_ip = ip_m.group(1)
            ts_str = _ts_parse(ts_m.group(1))
            key = ip_to_email.get(src_ip)
            if key and key in sessions:
                sessions[key]["fecha_fin"] = ts_str
            continue

    # Aplicar last_seen por IP a cada sesión
    for key, doc in sessions.items():
        src_ip = doc.pop("_src_ip", None)
        if src_ip and src_ip in ip_last_seen:
            doc["last_seen"] = max(doc["last_seen"], ip_last_seen[src_ip])

    return list(sessions.values())


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log("=== Extractor de sesiones de prácticas iniciado ===")

    os_ensure_index()

    pods = get_oauth2_proxy_pods()
    log(f"Pods oauth2-proxy en '{NAMESPACE}': {pods}")
    if not pods:
        log("ERROR: No se encontraron pods oauth2-proxy")
        sys.exit(1)

    all_docs = []
    for pod in pods:
        log(f"Leyendo logs de {pod}...")
        try:
            raw = k8s_get_logs(NAMESPACE, pod)
            docs = parse_logs(raw)
            log(f"  {pod}: {len(docs)} sesiones extraídas")
            all_docs.extend(docs)
        except Exception as e:
            log(f"  ERROR en {pod}: {e}")

    # Deduplicar por (email, fecha_inicio)
    seen, unique = set(), []
    for d in all_docs:
        k = (d["email"], d["fecha_inicio"])
        if k not in seen:
            seen.add(k)
            unique.append(d)

    log(f"Total sesiones únicas: {len(unique)}")
    os_bulk_index(unique)
    log("=== Extracción completada ===")


if __name__ == "__main__":
    main()
