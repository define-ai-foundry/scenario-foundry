"""Tests for scenario_foundry.validation.validate."""

import json

import pytest

from scenario_foundry import config, constants
from scenario_foundry.validation import validate as v

SCHEMA_PATH = config.SCHEMA_DIR / "scenario.schema.json"
JOENSUU_PATH = config.SCENARIOS_DIR / "joensuu.json"

TAXONOMY = v.load_taxonomy()
VALID_PATHS = v.taxonomy_classification_paths(TAXONOMY)


def _threat(**overrides):
    base = {
        "count": 5,
        "speed_kmh": 100,
        "alt_m": 50.0,
        "classification": ["Air vehicle", "UAV rotary wing", "Military"],
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
    v.validate_threat_profiles({"W1": _threat()}, VALID_PATHS)


def test_validate_threat_profiles_bad_count():
    with pytest.raises(v.ScenarioValidationError, match="count must be positive"):
        v.validate_threat_profiles({"W1": _threat(count=0)}, VALID_PATHS)


def test_validate_threat_profiles_bad_speed():
    with pytest.raises(v.ScenarioValidationError, match="speed must be positive"):
        v.validate_threat_profiles({"W1": _threat(speed_kmh=0)}, VALID_PATHS)


def test_validate_threat_profiles_negative_alt():
    with pytest.raises(v.ScenarioValidationError, match="negative altitude"):
        v.validate_threat_profiles({"W1": _threat(alt_m=-1.0)}, VALID_PATHS)


def test_validate_threat_profiles_unparseable_wkt():
    with pytest.raises(v.ScenarioValidationError, match="invalid WKT LineString"):
        v.validate_threat_profiles({"W1": _threat(wkt_linestring="NOT WKT AT ALL")}, VALID_PATHS)


def test_validate_threat_profiles_not_linestring():
    with pytest.raises(v.ScenarioValidationError, match="must be LineString"):
        v.validate_threat_profiles({"W1": _threat(wkt_linestring="POINT (1 2)")}, VALID_PATHS)


def test_validate_threat_profiles_too_few_points():
    with pytest.raises(v.ScenarioValidationError, match="at least two points"):
        v.validate_threat_profiles({"W1": _threat(wkt_linestring="LINESTRING EMPTY")}, VALID_PATHS)


def test_validate_threat_profiles_level3_path_accepted():
    v.validate_threat_profiles(
        {"W1": _threat(classification=["Equipment", "Weapon", "Missile"])}, VALID_PATHS
    )


def test_validate_threat_profiles_partial_path_accepted():
    v.validate_threat_profiles({"W1": _threat(classification=["Air vehicle"])}, VALID_PATHS)


def test_validate_threat_profiles_unknown_top_level_rejected():
    with pytest.raises(v.ScenarioValidationError, match="unknown classification path"):
        v.validate_threat_profiles({"W1": _threat(classification=["Spaceship"])}, VALID_PATHS)


def test_validate_threat_profiles_valid_top_level_invalid_child_rejected():
    with pytest.raises(v.ScenarioValidationError, match="unknown classification path"):
        v.validate_threat_profiles(
            {"W1": _threat(classification=["Air vehicle", "Submarine"])}, VALID_PATHS
        )


def _sensor(**overrides):
    base = {
        "id": "S1",
        "type": "RADAR_TACTICAL",
        "lat": 62.0,
        "lon": 29.0,
        "range_m": 1000,
        "update_rate_sec": 10,
    }
    base.update(overrides)
    return base


def test_validate_sensor_network_ok():
    v.validate_sensor_network([_sensor(), _sensor(id="S2")])


@pytest.mark.parametrize("sensor_type", [t.value for t in constants.SensorType])
def test_validate_sensor_network_accepts_every_known_type(sensor_type):
    v.validate_sensor_network([_sensor(type=sensor_type)])


def test_validate_sensor_network_unknown_type():
    with pytest.raises(v.ScenarioValidationError, match="unknown sensor type") as excinfo:
        v.validate_sensor_network([_sensor(type="ELINT_PASSIVE")])

    message = str(excinfo.value)
    assert "S1" in message
    assert "ELINT_PASSIVE" in message
    # The point of the guard is that the bad name looked plausible: list the real ones.
    for sensor_type in constants.SensorType:
        assert sensor_type.value in message


def test_schema_rejects_unknown_sensor_type():
    scenario = v.load_json(JOENSUU_PATH)
    scenario["sensor_network"][0]["type"] = "ELINT_PASSIVE"
    with pytest.raises(v.ScenarioValidationError, match="Schema validation failed"):
        v.validate_schema(scenario, SCHEMA_PATH)


def test_schema_sensor_type_enum_matches_constants():
    # The schema duplicates the enum for editor completion; keep the copies in step.
    schema = v.load_json(SCHEMA_PATH)
    schema_types = schema["properties"]["sensor_network"]["items"]["properties"]["type"]["enum"]
    assert set(schema_types) == {t.value for t in constants.SensorType}


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


def test_validate_scenario_bad_classification(tmp_path):
    scenario = v.load_json(JOENSUU_PATH)
    scenario["threat_profiles"]["W1_DECOY"]["classification"] = ["Not a real class"]
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(scenario), encoding="utf-8")

    with pytest.raises(v.ScenarioValidationError, match="unknown classification path"):
        v.validate_scenario(bad_path, SCHEMA_PATH)


def test_load_taxonomy_default_version():
    taxonomy = v.load_taxonomy()
    assert "classifications" in taxonomy


def test_load_taxonomy_missing_file_raises_real_error(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SCHEMA_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        v.load_taxonomy(version="does_not_exist")


def test_taxonomy_classification_paths_includes_all_three_levels():
    assert ("Equipment", "Weapon", "Missile") in VALID_PATHS
    assert ("Air vehicle", "Manned rotary wing", "Military") in VALID_PATHS
    assert ("Equipment", "Weapon") in VALID_PATHS
    assert ("Equipment",) in VALID_PATHS


def test_taxonomy_classification_paths_keeps_repeated_other_distinct():
    assert ("Land vehicle", "Other") in VALID_PATHS
    assert ("Sea vessel", "Other") in VALID_PATHS
    # "Other" under Equipment resolves via the level-2 dict (empty leaf list),
    # so only the level-2 path exists, not a level-3 leaf under it.
    assert ("Equipment", "Other") in VALID_PATHS
    assert ("Equipment", "Other", "Other") not in VALID_PATHS
    # top-level "Other" is its own path, distinct from any nested "Other".
    assert ("Other",) in VALID_PATHS


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
