#!/usr/bin/env python3
"""
Crea el dashboard de sesiones de prácticas escribiendo directamente
en el índice de saved objects de OpenSearch Dashboards.

Uso (con port-forward activo):
  kubectl port-forward -n formacion-datastores svc/opensearch-coordinator 19200:9200
  python3 src/create_practices_dashboard.py

Crea en el tenant global (.osdashboards.opensearch.formacion-datastores_1):
  - Index pattern : practices_sessions  (timeField: fecha_inicio)
  - Viz 1 : Evolución temporal de sesiones (date histogram)
  - Viz 2 : Sesiones por partner — top 10 (barras)
  - Viz 3 : Certificación practicada (donut)
  - Viz 4 : Resumen por partner (tabla: sesiones + alumnos únicos)
  - Viz 5 : Distribución por tenant (pie)
  - Dashboard : Sesiones de Prácticas
"""
import json
import os
import ssl
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

OS_HOST   = os.getenv("OS_HOST",  "localhost")
OS_PORT   = int(os.getenv("OS_PORT", "19200"))
CERT_FILE = os.getenv("TLS_CERT", "secretos/admin/admin.crt")
KEY_FILE  = os.getenv("TLS_KEY",  "secretos/admin/admin_private.key")

OSD_INDEX = ".osdashboards.opensearch.formacion-datastores_1"
NOW       = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

IDX_ID          = "practices-sessions-pattern"
VIS_EVOL_ID     = "vis-practices-evolucion"
VIS_PARTNERS_ID = "vis-practices-partners"
VIS_CERT_ID     = "vis-practices-certificacion"
VIS_TABLE_ID    = "vis-practices-table"
VIS_TENANT_ID   = "vis-practices-tenant"
DASH_ID         = "dashboard-practices-sessions"


def _ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.load_cert_chain(CERT_FILE, KEY_FILE)
    return ctx


def put(doc_id: str, body: dict) -> str:
    url = f"https://{OS_HOST}:{OS_PORT}/{OSD_INDEX}/_doc/{doc_id}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="PUT",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, context=_ctx()) as r:
            result = json.loads(r.read())
            return result.get("result", "ok")
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.read().decode()[:120]}"


def saved_obj(obj_type: str, obj_id: str, attrs: dict,
              refs: list | None = None, migration: dict | None = None) -> str:
    doc = {
        "type":       obj_type,
        obj_type:     attrs,
        "references": refs or [],
        "migrationVersion": migration or {},
        "updated_at": NOW,
    }
    return put(f"{obj_type}:{obj_id}", doc)


# ── Helpers de visState ────────────────────────────────────────────────────────

def _search_src(idx_id: str = IDX_ID) -> str:
    return json.dumps({
        "index": idx_id,
        "query": {"query": "", "language": "kuery"},
        "filter": [],
    })


def _vis_attrs(title: str, vis_type: str, params: dict, aggs: list) -> dict:
    return {
        "title":       title,
        "visState":    json.dumps({"title": title, "type": vis_type,
                                   "params": params, "aggs": aggs}),
        "uiStateJSON": "{}",
        "description": "",
        "kibanaSavedObjectMeta": {"searchSourceJSON": _search_src()},
    }


def _vis_refs() -> list:
    return [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index",
             "type": "index-pattern", "id": IDX_ID}]


def _vis_migration() -> dict:
    return {"visualization": "7.10.0"}


# ── Index pattern ──────────────────────────────────────────────────────────────

def create_index_pattern():
    return saved_obj("index-pattern", IDX_ID, {
        "title":         "practices_sessions",
        "timeFieldName": "fecha_inicio",
        "fields":        "[]",
    }, migration={"index-pattern": "7.6.0"})


# ── Visualizaciones ────────────────────────────────────────────────────────────

def _cat_axis(pos="bottom"):
    return [{"id": "CategoryAxis-1", "type": "category", "position": pos,
             "show": True, "title": {},
             "labels": {"show": True, "truncate": 100, "rotate": -30},
             "scale": {"type": "linear"}}]


def _val_axis(label="Sesiones"):
    return [{"id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value",
             "position": "left", "show": True,
             "title": {"text": label},
             "labels": {"show": True, "filter": True, "truncate": 100},
             "scale": {"type": "linear", "mode": "normal"}}]


def _series_params():
    return [{"show": True, "type": "histogram", "mode": "normal",
             "data": {"label": "Sesiones", "id": "1"},
             "valueAxis": "ValueAxis-1",
             "drawLinesBetweenPoints": True, "showCircles": True}]


def create_vis_evolucion():
    params = {
        "type": "histogram", "grid": {"categoryLines": False},
        "categoryAxes": _cat_axis(), "valueAxes": _val_axis(),
        "seriesParams": _series_params(),
        "addTooltip": True, "addLegend": False,
        "legendPosition": "right", "times": [], "addTimeMarker": False,
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count",
         "schema": "metric", "params": {}},
        {"id": "2", "enabled": True, "type": "date_histogram",
         "schema": "segment", "params": {
             "field": "fecha_inicio", "useNormalizedEsInterval": True,
             "interval": "auto", "drop_partials": False,
             "min_doc_count": 1, "extended_bounds": {}}},
    ]
    return saved_obj("visualization", VIS_EVOL_ID,
                     _vis_attrs("Evolución temporal de sesiones", "histogram", params, aggs),
                     _vis_refs(), _vis_migration())


def create_vis_partners():
    params = {
        "type": "histogram", "grid": {"categoryLines": False},
        "categoryAxes": _cat_axis(), "valueAxes": _val_axis(),
        "seriesParams": _series_params(),
        "addTooltip": True, "addLegend": False,
        "legendPosition": "right", "times": [], "addTimeMarker": False,
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count",
         "schema": "metric", "params": {}},
        {"id": "2", "enabled": True, "type": "terms", "schema": "segment",
         "params": {"field": "partner", "size": 10, "order": "desc",
                    "orderBy": "1", "otherBucket": False,
                    "missingBucket": False}},
    ]
    return saved_obj("visualization", VIS_PARTNERS_ID,
                     _vis_attrs("Sesiones por partner (top 10)", "histogram", params, aggs),
                     _vis_refs(), _vis_migration())


def create_vis_certificacion():
    params = {
        "type": "pie", "addTooltip": True, "addLegend": True,
        "legendPosition": "right", "isDonut": True,
        "labels": {"show": True, "values": True, "last_level": True, "truncate": 100},
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count",
         "schema": "metric", "params": {}},
        {"id": "2", "enabled": True, "type": "terms", "schema": "segment",
         "params": {"field": "certificacion", "size": 10, "order": "desc",
                    "orderBy": "1", "otherBucket": False,
                    "missingBucket": True,
                    "missingBucketLabel": "Sin certificación detectada"}},
    ]
    return saved_obj("visualization", VIS_CERT_ID,
                     _vis_attrs("Sesiones por certificación practicada", "pie", params, aggs),
                     _vis_refs(), _vis_migration())


def create_vis_table():
    params = {
        "perPage": 15, "showPartialRows": False,
        "showMetricsAtAllLevels": False,
        "sort": {"columnIndex": None, "direction": None},
        "showTotal": False, "totalFunc": "sum",
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count",
         "schema": "metric", "params": {}, "customLabel": "Sesiones"},
        {"id": "3", "enabled": True, "type": "cardinality",
         "schema": "metric",
         "params": {"field": "email"}, "customLabel": "Alumnos únicos"},
        {"id": "2", "enabled": True, "type": "terms", "schema": "bucket",
         "params": {"field": "partner", "size": 20, "order": "desc",
                    "orderBy": "1", "otherBucket": False,
                    "missingBucket": False}},
    ]
    return saved_obj("visualization", VIS_TABLE_ID,
                     _vis_attrs("Resumen por partner", "table", params, aggs),
                     _vis_refs(), _vis_migration())


def create_vis_tenant():
    params = {
        "type": "pie", "addTooltip": True, "addLegend": True,
        "legendPosition": "right", "isDonut": False,
        "labels": {"show": True, "values": True, "last_level": True, "truncate": 100},
    }
    aggs = [
        {"id": "1", "enabled": True, "type": "count",
         "schema": "metric", "params": {}},
        {"id": "2", "enabled": True, "type": "terms", "schema": "segment",
         "params": {"field": "tenant", "size": 5, "order": "desc",
                    "orderBy": "1", "otherBucket": False,
                    "missingBucket": False}},
    ]
    return saved_obj("visualization", VIS_TENANT_ID,
                     _vis_attrs("Distribución por tenant", "pie", params, aggs),
                     _vis_refs(), _vis_migration())


# ── Dashboard ──────────────────────────────────────────────────────────────────

def create_dashboard():
    panels = [
        {"panelIndex": "1", "gridData": {"x": 0,  "y": 0,  "w": 48, "h": 12, "i": "1"},
         "version": "2.13.0", "embeddableConfig": {}, "panelRefName": "panel_1"},
        {"panelIndex": "2", "gridData": {"x": 0,  "y": 12, "w": 32, "h": 16, "i": "2"},
         "version": "2.13.0", "embeddableConfig": {}, "panelRefName": "panel_2"},
        {"panelIndex": "3", "gridData": {"x": 32, "y": 12, "w": 16, "h": 16, "i": "3"},
         "version": "2.13.0", "embeddableConfig": {}, "panelRefName": "panel_3"},
        {"panelIndex": "4", "gridData": {"x": 0,  "y": 28, "w": 48, "h": 14, "i": "4"},
         "version": "2.13.0", "embeddableConfig": {}, "panelRefName": "panel_4"},
    ]
    refs = [
        {"name": "panel_1", "type": "visualization", "id": VIS_EVOL_ID},
        {"name": "panel_2", "type": "visualization", "id": VIS_PARTNERS_ID},
        {"name": "panel_3", "type": "visualization", "id": VIS_TENANT_ID},
        {"name": "panel_4", "type": "visualization", "id": VIS_TABLE_ID},
    ]
    attrs = {
        "title": "Sesiones de Prácticas",
        "hits": 0,
        "description": "Sesiones de alumnos en el entorno de prácticas (oauth2-proxy → OpenSearch)",
        "panelsJSON": json.dumps(panels),
        "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
        "version": 1,
        "timeRestore": True,
        "timeFrom": "now-30d",
        "timeTo": "now",
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({
                "query": {"query": "", "language": "kuery"},
                "filter": [],
            }),
        },
    }
    return saved_obj("dashboard", DASH_ID, attrs, refs,
                     {"dashboard": "7.9.3"})


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    steps = [
        ("Index pattern  practices_sessions", create_index_pattern),
        ("Viz: evolución temporal",           create_vis_evolucion),
        ("Viz: sesiones por partner",         create_vis_partners),
        ("Viz: resumen tabla por partner",    create_vis_table),
        ("Viz: distribución por tenant",      create_vis_tenant),
        ("Dashboard: Sesiones de Prácticas",  create_dashboard),
    ]
    print(f"OpenSearch: https://{OS_HOST}:{OS_PORT}  →  {OSD_INDEX}\n")
    for label, fn in steps:
        result = fn()
        ok = result in ("created", "updated", "noop")
        print(f"  {'✓' if ok else '✗'}  {label}: {result}")

    print(f"\nDashboard disponible en:")
    print(f"  https://admin.formacion.practices.stratio.com"
          f"/opensearch-dashboards.formacion-datastores"
          f"/app/dashboards#/view/{DASH_ID}")
    print(f"\n  (o busca 'Sesiones de Prácticas' en Dashboards > All dashboards)")


if __name__ == "__main__":
    main()
