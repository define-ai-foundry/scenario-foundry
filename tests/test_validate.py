"""Tests for scenario_foundry.validation.validate."""

import pytest

from scenario_foundry import config
from scenario_foundry.validation import validate as v

SCHEMA_PATH = config.SCHEMA_DIR / "scenario.schema.json"
JOENSUU_PATH = config.SCENARIOS_DIR / "joensuu.json"


def _threat(**overrides):
    base = {
        "count": 5,
        "speed_kmh": 100,
        "alt_m": 50.0,
        "wkt_linestring": "LINESTRING (30.0 62.0, 30.1 62.1)",
    }
    base.update(overrides)
    return base


def test_load_json(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"a": 1}', encoding="utf-8")
    assert v.load_json(p) == {"a": 1}


def test_validate_schema_pass():
    cfg = v.load_json(JOENSUU_PATH)
    v.validate_schema(cfg, SCHEMA_PATH)


def test_validate_schema_fail():
    with pytest.raises(v.ScenarioValidationError, match="Schema validation failed"):
        v.validate_schema({"not": "valid"}, SCHEMA_PATH)


def test_validate_coordinates_ok():
    v.validate_coordinates(62.0, 29.0)


@pytest.mark.parametrize(
    ("lat", "lon", "msg"),
    [
        (91.0, 29.0, "invalid latitude"),
        (-91.0, 29.0, "invalid latitude"),
        (62.0, 181.0, "invalid longitude"),
        (62.0, -181.0, "invalid longitude"),
    ],
)
def test_validate_coordinates_bad(lat, lon, msg):
    with pytest.raises(v.ScenarioValidationError, match=msg):
        v.validate_coordinates(lat, lon)


def test_validate_scenario_meta_ok():
    v.validate_scenario_meta(
        {"start_time_iso": "2026-11-15T02:45:00Z", "duration_seconds": 100, "time_step_seconds": 20}
    )


def test_validate_scenario_meta_bad_time():
    with pytest.raises(v.ScenarioValidationError, match="Invalid start_time_iso"):
        v.validate_scenario_meta(
            {"start_time_iso": "not-a-time", "duration_seconds": 100, "time_step_seconds": 20}
        )


def test_validate_scenario_meta_bad_division():
    with pytest.raises(v.ScenarioValidationError, match="divide evenly"):
        v.validate_scenario_meta(
            {
                "start_time_iso": "2026-11-15T02:45:00Z",
                "duration_seconds": 101,
                "time_step_seconds": 20,
            }
        )


def test_validate_targets_ok():
    v.validate_targets({"T1": {"lat": 62.0, "lon": 29.0, "alt": 10.0}})


def test_validate_targets_negative_alt():
    with pytest.raises(v.ScenarioValidationError, match="negative altitude"):
        v.validate_targets({"T1": {"lat": 62.0, "lon": 29.0, "alt": -1.0}})


def test_validate_threat_profiles_ok():
    v.validate_threat_profiles({"W1": _threat()})


def test_validate_threat_profiles_bad_count():
    with pytest.raises(v.ScenarioValidationError, match="count must be positive"):
        v.validate_threat_profiles({"W1": _threat(count=0)})


def test_validate_threat_profiles_bad_speed():
    with pytest.raises(v.ScenarioValidationError, match="speed must be positive"):
        v.validate_threat_profiles({"W1": _threat(speed_kmh=0)})


def test_validate_threat_profiles_negative_alt():
    with pytest.raises(v.ScenarioValidationError, match="negative altitude"):
        v.validate_threat_profiles({"W1": _threat(alt_m=-1.0)})


def test_validate_threat_profiles_unparseable_wkt():
    with pytest.raises(v.ScenarioValidationError, match="invalid WKT LineString"):
        v.validate_threat_profiles({"W1": _threat(wkt_linestring="NOT WKT AT ALL")})


def test_validate_threat_profiles_not_linestring():
    with pytest.raises(v.ScenarioValidationError, match="must be LineString"):
        v.validate_threat_profiles({"W1": _threat(wkt_linestring="POINT (1 2)")})


def test_validate_threat_profiles_too_few_points():
    with pytest.raises(v.ScenarioValidationError, match="at least two points"):
        v.validate_threat_profiles({"W1": _threat(wkt_linestring="LINESTRING EMPTY")})


def _sensor(**overrides):
    base = {"id": "S1", "lat": 62.0, "lon": 29.0, "range_m": 1000, "update_rate_sec": 10}
    base.update(overrides)
    return base


def test_validate_sensor_network_ok():
    v.validate_sensor_network([_sensor(), _sensor(id="S2")])


def test_validate_sensor_network_duplicate_id():
    with pytest.raises(v.ScenarioValidationError, match="Duplicate sensor id"):
        v.validate_sensor_network([_sensor(), _sensor()])


def test_validate_sensor_network_bad_range():
    with pytest.raises(v.ScenarioValidationError, match="invalid range"):
        v.validate_sensor_network([_sensor(range_m=0)])


def test_validate_sensor_network_bad_update_rate():
    with pytest.raises(v.ScenarioValidationError, match="invalid update rate"):
        v.validate_sensor_network([_sensor(update_rate_sec=0)])


def test_validate_terrain_ok():
    v.validate_terrain([{"name": "A", "lat": 62.0, "lon": 29.0}])


def test_validate_terrain_bad():
    with pytest.raises(v.ScenarioValidationError):
        v.validate_terrain([{"name": "A", "lat": 999.0, "lon": 29.0}])


def test_validate_scenario_full():
    assert v.validate_scenario(JOENSUU_PATH, SCHEMA_PATH) is True


def test_main_location(monkeypatch):
    monkeypatch.setattr("sys.argv", ["validate.py", "--location", "joensuu"])
    v.main()


def test_main_append_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["validate.py", "--scenario", "joensuu"])
    v.main()
    assert "Scenario validation OK" in capsys.readouterr().out


def test_main_not_found(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["validate.py", "--scenario", "does_not_exist.json"])
    v.main()
    assert "not found" in capsys.readouterr().out


def test_main_success_with_schema(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv", ["validate.py", "--scenario", "joensuu.json", "--schema", str(SCHEMA_PATH)]
    )
    v.main()
    assert "Scenario validation OK" in capsys.readouterr().out
