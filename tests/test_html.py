import json
import re
from pathlib import Path

from incopilot import cli
from incopilot.html import render_html

ROOT = Path(__file__).resolve().parent.parent
SLOT = re.compile(r'<script id="report-data" type="application/json">(.*?)</script>', re.S)
SAMPLE = re.compile(r'<script id="sample-data" type="application/json">(.*?)</script>', re.S)


def test_site_and_packaged_viewer_are_the_same_file():
    assert (ROOT / "site" / "viewer.html").read_text() == (ROOT / "incopilot" / "viewer.html").read_text()


def test_bundled_sample_is_a_valid_report():
    page = (ROOT / "incopilot" / "viewer.html").read_text()
    sample = json.loads(SAMPLE.search(page).group(1))
    assert sample["schema_version"] == "2" and sample["severity"] == "critical"
    assert SLOT.search(page).group(1) == "null"
    assert "S3cr3tPass" not in page


def test_render_embeds_report_and_drops_sample():
    page = render_html({"schema_version": "2", "meta": {"target": "x"}, "stats": {}, "findings": {}})
    assert json.loads(SLOT.search(page).group(1))["meta"]["target"] == "x"
    assert SAMPLE.search(page).group(1) == "null"


def test_log_content_cannot_break_out_of_the_script_element():
    evil = '</script><script>alert(1)</script><img src=x onerror=alert(1)> &  '
    page = render_html({"schema_version": "2", "meta": {"target": evil}, "stats": {}, "findings": {}})
    body = SLOT.search(page).group(1)
    assert "<" not in body and ">" not in body and "&" not in body
    assert json.loads(body)["meta"]["target"] == evil
    assert page.count("<script") == 3  # data, sample, viewer code


def test_cli_html_flag(example_log, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.run(["file", "--path", str(example_log), "--html", "-q"]) == cli.EXIT_OK
    page = (tmp_path / "out" / "report.html").read_text()
    assert json.loads(SLOT.search(page).group(1))["findings"]["http_5xx"]["count"] == 5
    assert cli.run(["file", "--path", str(example_log), "--out-dir", "o2", "-q"]) == cli.EXIT_OK
    assert not (tmp_path / "o2" / "report.html").exists()
