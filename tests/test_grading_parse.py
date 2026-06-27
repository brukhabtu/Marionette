import json
from pathlib import Path

import marionette.grading as grading
from marionette.config import Config
from marionette.mock.fixtures import REPORT_RESOLVED, REPORT_UNRESOLVED


def test_write_predictions(tmp_path):
    path = tmp_path / "preds.jsonl"
    grading.write_predictions(path, "anthropic/claude-haiku-4-5", {"inst-1": "diff --git ..."})
    line = json.loads(path.read_text().strip())
    assert line == {
        "instance_id": "inst-1",
        "model_name_or_path": "anthropic/claude-haiku-4-5",
        "model_patch": "diff --git ...",
    }


def test_build_eval_command_namespace_none():
    cfg = Config(namespace=None, instance_ids_file=None)
    cmd = grading.build_eval_command(cfg, "preds.jsonl", "run1", ["inst-1"])
    assert "--namespace" in cmd and cmd[cmd.index("--namespace") + 1] == "none"
    assert "swebench.harness.run_evaluation" in cmd
    assert "inst-1" in cmd


def _write_report(root: Path, run_id: str, model: str, instance_id: str, report: dict):
    d = root / "logs/run_evaluation" / run_id / grading.model_slug(model) / instance_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "report.json").write_text(json.dumps(report))


def test_parse_reports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model = "anthropic/claude-haiku-4-5"
    iid = "mockorg__mockrepo-1"
    _write_report(tmp_path, "run1", model, iid, REPORT_RESOLVED)
    assert grading.parse_reports("run1", model, [iid]) == {iid: True}

    _write_report(tmp_path, "run2", model, iid, REPORT_UNRESOLVED)
    assert grading.parse_reports("run2", model, [iid]) == {iid: False}


def test_parse_reports_missing_is_false(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert grading.parse_reports("nope", "m", ["x"]) == {"x": False}
