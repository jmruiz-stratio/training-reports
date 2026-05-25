import argparse
import json
from .analytics import (
    partner_kpis, export_partner_kpis_csv, export_reporting_package,
    internal_course_compliance,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Skill analytics CLI")
    sp = p.add_subparsers(dest="cmd", required=True)
    k = sp.add_parser("kpis")
    k.add_argument("workdir")

    e = sp.add_parser("export")
    e.add_argument("workdir")
    e.add_argument("output_csv")

    r = sp.add_parser("reporting")
    r.add_argument("workdir")
    r.add_argument("--output-excel", default="reports/informe_formacion.xlsx")
    r.add_argument("--output-csv-dir", default="reports/csv")
    r.add_argument("--partner", default=None)
    r.add_argument("--practices", default="reports/sesiones_practicas.csv",
                   help="CSV de sesiones de prácticas (se omite si no existe)")

    co = sp.add_parser(
        "compliance",
        help="Informe de cumplimiento de un curso interno (completados vs pendientes)",
    )
    co.add_argument("workdir")
    co.add_argument(
        "course_pattern",
        help="Patrón de búsqueda en el nombre del curso (ej: 'blanqueo')",
    )
    co.add_argument("--partner", default="stratio",
                    help="Partner a analizar (default: stratio)")
    co.add_argument("--empleados-xlsx", default=None,
                    help="Excel de empleados para cruzar (nombre, apellidos, rol, departamento)")
    co.add_argument("--output-excel", default="reports/compliance.xlsx")

    args = p.parse_args()
    if args.cmd == "kpis":
        print(json.dumps(partner_kpis(args.workdir), indent=2, ensure_ascii=False))
    elif args.cmd == "export":
        print(export_partner_kpis_csv(args.workdir, args.output_csv))
    elif args.cmd == "compliance":
        result = internal_course_compliance(
            args.workdir,
            args.course_pattern,
            output_excel=args.output_excel,
            partner=args.partner,
            empleados_xlsx=args.empleados_xlsx,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        result = export_reporting_package(
            args.workdir,
            output_excel=args.output_excel,
            output_csv_dir=args.output_csv_dir,
            partner=args.partner,
            practices_csv=args.practices,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def main_compliance() -> int:
    """Entrypoint dedicado: training-report-internal <workdir> <course_pattern> [opciones]"""
    p = argparse.ArgumentParser(
        prog="training-report-internal",
        description="Informe de cumplimiento de un curso interno (completados vs pendientes)",
    )
    p.add_argument("workdir")
    p.add_argument("course_pattern",
                   help="Patrón de búsqueda en el nombre del curso (ej: 'blanqueo')")
    p.add_argument("--partner", default="stratio",
                   help="Partner a analizar (default: stratio)")
    p.add_argument("--empleados-xlsx", default=None,
                   help="Excel de empleados para cruzar (nombre, apellidos, rol, departamento)")
    p.add_argument("--output-excel", default="reports/compliance.xlsx")

    args = p.parse_args()
    result = internal_course_compliance(
        args.workdir,
        args.course_pattern,
        output_excel=args.output_excel,
        partner=args.partner,
        empleados_xlsx=args.empleados_xlsx,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
