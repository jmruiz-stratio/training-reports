from datetime import date

from batch_agent import runner
from python_core.config import Settings


def test_ingest_daily_skip_upload(monkeypatch, tmp_path):
    monkeypatch.setattr(
        runner,
        "load_settings",
        lambda: Settings(
            moodle_url="http://moodle",
            moodle_token="token",
            stratio_url="",
            stratio_user="",
            stratio_pass="",
            stratio_tenant="formacion",
            hdfs_base_path="/informes/moodle",
            workdir=str(tmp_path),
        ),
    )
    monkeypatch.setattr(runner, "run_all", lambda *_: {"users": [{"id": 1, "username": "u-acme", "email": "u@acme.com"}]})
    monkeypatch.setattr(runner, "write", lambda rows, dataset, workdir: str(tmp_path / f"{dataset}.parquet"))
    monkeypatch.setattr(runner, "validate_dataset", lambda rows, path, dataset: "abc123")
    monkeypatch.setattr(runner, "run_sanity", lambda workdir: {"total_users": 1})

    result = runner.ingest_daily(date(2026, 4, 22), skip_upload=True)
    assert result["upload_skipped"] is True
    assert result["datasets_uploaded"] == []
    assert result["checksums"]["users"] == "abc123"


def test_ingest_daily_requires_stratio_url_when_upload(monkeypatch, tmp_path):
    monkeypatch.setattr(
        runner,
        "load_settings",
        lambda: Settings(
            moodle_url="http://moodle",
            moodle_token="token",
            stratio_url="",
            stratio_user="",
            stratio_pass="",
            stratio_tenant="formacion",
            hdfs_base_path="/informes/moodle",
            workdir=str(tmp_path),
        ),
    )
    monkeypatch.setattr(runner, "run_all", lambda *_: {"users": [{"id": 1}]})
    monkeypatch.setattr(runner, "write", lambda rows, dataset, workdir: str(tmp_path / f"{dataset}.parquet"))
    monkeypatch.setattr(runner, "validate_dataset", lambda rows, path, dataset: "abc123")
    monkeypatch.setattr(runner, "run_sanity", lambda workdir: {})

    try:
        runner.ingest_daily(date(2026, 4, 22), skip_upload=False)
        assert False, "Expected RuntimeError"
    except RuntimeError as e:
        assert "STRATIO_URL" in str(e)
