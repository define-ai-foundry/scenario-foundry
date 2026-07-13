"""Tests for the scenario_foundry.generate_scenario orchestrator."""

import pytest

from scenario_foundry import generate_scenario as gs


@pytest.fixture
def spies(monkeypatch):
    calls = []
    for name in ("run_fetch_terrain", "run_optimize_vectors", "run_generate_sensor_data"):
        monkeypatch.setattr(gs, name, lambda n=name: calls.append(n))
    return calls


def test_main_not_found(monkeypatch, capsys, spies):
    monkeypatch.setattr("sys.argv", ["generate_scenario.py", "--scenario", "no_such_scenario"])
    gs.main()
    assert "not found" in capsys.readouterr().out
    assert spies == []


def test_main_happy_path_appends_json(monkeypatch, capsys, spies):
    monkeypatch.setattr("sys.argv", ["generate_scenario.py", "--scenario", "joensuu"])
    gs.main()
    out = capsys.readouterr().out
    assert "COMPLETED SUCCESSFULLY" in out
    assert spies == ["run_fetch_terrain", "run_optimize_vectors", "run_generate_sensor_data"]


def test_main_step_raises(monkeypatch, capsys):
    def boom():
        raise RuntimeError("terrain blew up")

    monkeypatch.setattr(gs, "run_fetch_terrain", boom)
    monkeypatch.setattr(gs, "run_optimize_vectors", lambda: None)
    monkeypatch.setattr(gs, "run_generate_sensor_data", lambda: None)
    monkeypatch.setattr("sys.argv", ["generate_scenario.py", "--scenario", "joensuu.json"])
    gs.main()
    out = capsys.readouterr().out
    assert "Step 1 (Terrain Fetch) failed" in out
    assert "COMPLETED SUCCESSFULLY" not in out


def test_main_step2_raises(monkeypatch, capsys):
    monkeypatch.setattr(gs, "run_fetch_terrain", lambda: None)
    monkeypatch.setattr(
        gs, "run_optimize_vectors", lambda: (_ for _ in ()).throw(RuntimeError("x"))
    )
    monkeypatch.setattr(gs, "run_generate_sensor_data", lambda: None)
    monkeypatch.setattr("sys.argv", ["generate_scenario.py", "--scenario", "joensuu"])
    gs.main()
    assert "Step 2 (Vector Optimization) failed" in capsys.readouterr().out


def test_main_step3_raises(monkeypatch, capsys):
    monkeypatch.setattr(gs, "run_fetch_terrain", lambda: None)
    monkeypatch.setattr(gs, "run_optimize_vectors", lambda: None)
    monkeypatch.setattr(
        gs, "run_generate_sensor_data", lambda: (_ for _ in ()).throw(RuntimeError("x"))
    )
    monkeypatch.setattr("sys.argv", ["generate_scenario.py", "--scenario", "joensuu"])
    gs.main()
    assert "Step 3 (Sensor Generation) failed" in capsys.readouterr().out
