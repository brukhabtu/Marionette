from dataclasses import replace

from marionette.config import Config
from marionette.slice_cache import key_for, load, save
from marionette.types import Slice, SlicePlan


def _plan(cfg: Config, instance_id: str) -> SlicePlan:
    return SlicePlan(
        instance_id=instance_id,
        slices=[Slice("do a thing", ["a.py"])],
        orchestrator_model=cfg.orchestrator_model,
        orchestrator_tokens=123,
        orchestrator_cost_usd=0.01,
        cache_key=key_for(cfg, instance_id),
    )


def test_save_and_load_roundtrip(tmp_path):
    cfg = Config(cache_dir=str(tmp_path), instance_ids_file=None)
    plan = _plan(cfg, "inst-1")
    save(cfg, plan)
    loaded = load(cfg, "inst-1")
    assert loaded is not None
    assert loaded.orchestrator_tokens == 123
    assert [s.scope for s in loaded.slices] == ["do a thing"]


def test_key_changes_with_model(tmp_path):
    cfg = Config(cache_dir=str(tmp_path), instance_ids_file=None)
    k1 = key_for(cfg, "inst-1")
    cfg2 = replace(cfg, orchestrator_model="anthropic/other-model")
    assert key_for(cfg2, "inst-1") != k1


def test_key_changes_with_schema_version(tmp_path):
    cfg = Config(cache_dir=str(tmp_path), instance_ids_file=None)
    cfg2 = replace(cfg, orchestrator_schema_version=cfg.orchestrator_schema_version + 1)
    assert key_for(cfg2, "inst-1") != key_for(cfg, "inst-1")


def test_load_miss_after_model_change(tmp_path):
    cfg = Config(cache_dir=str(tmp_path), instance_ids_file=None)
    save(cfg, _plan(cfg, "inst-1"))
    cfg2 = replace(cfg, orchestrator_model="anthropic/other-model")
    assert load(cfg2, "inst-1") is None  # new key => cache miss
