"""Unit tests for incident scenario modules: contract only."""
from __future__ import annotations

import importlib.util
from pathlib import Path


_INCIDENTS_DIR = Path(__file__).parent.parent.parent / "incidents"
_SLUGS = ["retry-loop", "surprise-cost", "hallucination-drift"]


def _load(slug: str):
    path = _INCIDENTS_DIR / slug / "scenario.py"
    spec = importlib.util.spec_from_file_location(f"incidents.{slug}.scenario", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_all_scenario_files_exist():
    for slug in _SLUGS:
        path = _INCIDENTS_DIR / slug / "scenario.py"
        assert path.exists(), f"Missing {path}"


def test_each_scenario_has_run_callable():
    for slug in _SLUGS:
        mod = _load(slug)
        assert callable(getattr(mod, "run", None)), f"{slug} missing callable run()"


def test_each_scenario_has_description():
    for slug in _SLUGS:
        mod = _load(slug)
        assert isinstance(getattr(mod, "DESCRIPTION", None), str), f"{slug} missing DESCRIPTION"
        assert mod.DESCRIPTION, f"{slug} DESCRIPTION is empty"


def test_each_scenario_has_agent_id():
    for slug in _SLUGS:
        mod = _load(slug)
        assert isinstance(getattr(mod, "AGENT_ID", None), str), f"{slug} missing AGENT_ID"


def test_run_accepts_no_arguments():
    """run() must be callable with zero arguments per the spec contract."""
    import inspect
    for slug in _SLUGS:
        mod = _load(slug)
        sig = inspect.signature(mod.run)
        required = [
            p for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
        ]
        assert required == [], f"{slug}.run() has required parameters: {required}"
