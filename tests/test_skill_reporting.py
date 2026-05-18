from pathlib import Path

from skill import analytics


def test_export_reporting_package_smoke(monkeypatch, tmp_path):
    workdir = tmp_path / "work"
    workdir.mkdir()

    def fake_loader():
        return (
            lambda con, base: {"f_usuarios"},
            lambda con, st, out, pcsv=None: ["resumen_partner"],
            lambda st, con: [("resumen_partner", "r_resumen_partner", "SELECT 1 AS n")],
        )

    monkeypatch.setattr(analytics, "_load_reporting_helpers", fake_loader)

    result = analytics.export_reporting_package(
        str(workdir),
        output_excel=str(tmp_path / "report.xlsx"),
        output_csv_dir=str(tmp_path / "csv"),
    )

    assert result["excel"].endswith("report.xlsx")
    assert len(result["csv_files"]) == 1
    assert Path(result["csv_files"][0]).exists()
