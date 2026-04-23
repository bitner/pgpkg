from __future__ import annotations

from pathlib import Path

import pytest

from pgpkg.catalog import build_catalog
from pgpkg.config import load_config
from pgpkg.errors import PlanError
from pgpkg.planner import plan, render_graph_dot, render_graph_text


def _stage(project: Path, name: str) -> None:
    mig = project / "migrations"
    mig.mkdir(exist_ok=True)
    (mig / name).write_text("-- stub\n")


def _catalog(project: Path):
    return build_catalog(load_config(project))


def test_plan_fresh_install_to_base(sample_project: Path):
    _stage(sample_project, "sampleext--0.1.0.sql")
    cat = _catalog(sample_project)
    p = plan(cat, source=None, target="0.1.0")
    assert p.bootstrap_base is not None
    assert p.steps == []


def test_plan_source_to_target(sample_project: Path):
    _stage(sample_project, "sampleext--0.1.0.sql")
    _stage(sample_project, "sampleext--0.2.0.sql")
    _stage(sample_project, "sampleext--0.1.0--0.2.0.sql")
    cat = _catalog(sample_project)
    p = plan(cat, source="0.1.0", target="0.2.0")
    assert p.bootstrap_base is None
    assert [(s.from_version, s.to_version) for s in p.steps] == [("0.1.0", "0.2.0")]


def test_plan_fresh_install_walks_edges_when_target_has_no_base(sample_project: Path):
    _stage(sample_project, "sampleext--0.1.0.sql")
    _stage(sample_project, "sampleext--0.1.0--0.2.0.sql")
    cat = _catalog(sample_project)
    p = plan(cat, source=None, target="0.2.0")
    assert p.bootstrap_base is not None
    assert p.bootstrap_base.name == "sampleext--0.1.0.sql"
    assert [(s.from_version, s.to_version) for s in p.steps] == [("0.1.0", "0.2.0")]


def test_plan_shortest_path(sample_project: Path):
    # 0.1 -> 0.2 -> 0.3; also direct 0.1 -> 0.3
    for n in [
        "sampleext--0.1.0.sql",
        "sampleext--0.2.0.sql",
        "sampleext--0.3.0.sql",
        "sampleext--0.1.0--0.2.0.sql",
        "sampleext--0.2.0--0.3.0.sql",
        "sampleext--0.1.0--0.3.0.sql",
    ]:
        _stage(sample_project, n)
    cat = _catalog(sample_project)
    p = plan(cat, source="0.1.0", target="0.3.0")
    assert [(s.from_version, s.to_version) for s in p.steps] == [("0.1.0", "0.3.0")]


def test_plan_unreachable(sample_project: Path):
    _stage(sample_project, "sampleext--0.1.0.sql")
    _stage(sample_project, "sampleext--0.2.0.sql")
    cat = _catalog(sample_project)
    with pytest.raises(PlanError):
        plan(cat, source="0.1.0", target="0.2.0")


def test_plan_source_equals_target(sample_project: Path):
    _stage(sample_project, "sampleext--0.1.0.sql")
    cat = _catalog(sample_project)
    p = plan(cat, source="0.1.0", target="0.1.0")
    assert p.steps == []
    assert p.bootstrap_base is None


def test_plan_unknown_target(sample_project: Path):
    _stage(sample_project, "sampleext--0.1.0.sql")
    cat = _catalog(sample_project)
    with pytest.raises(PlanError):
        plan(cat, source="0.1.0", target="0.2.0")


def test_render_graph_text(sample_project: Path):
    _stage(sample_project, "sampleext--0.1.0.sql")
    _stage(sample_project, "sampleext--0.2.0.sql")
    _stage(sample_project, "sampleext--0.1.0--0.2.0.sql")
    cat = _catalog(sample_project)
    text = render_graph_text(cat)
    assert "0.1.0" in text and "0.2.0" in text
    assert "->" in text


def test_render_graph_dot(sample_project: Path):
    _stage(sample_project, "sampleext--0.1.0.sql")
    cat = _catalog(sample_project)
    assert "digraph" in render_graph_dot(cat)
