"""Tests for scenario_foundry.export_scenario."""

import csv
import json

import pytest

from scenario_foundry import export_scenario as es


def _read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


# --- decimate_wkt_linestring ---
def test_decimate_empty():
    assert es.decimate_wkt_linestring("") == ""


def test_decimate_no_match():
    assert es.decimate_wkt_linestring("point (1 2)") == "POINT (1 2)"


def test_decimate_two_coords_passthrough():
    assert es.decimate_wkt_linestring("linestring (1 2, 3 4)") == "LINESTRING (1 2, 3 4)"


def test_decimate_long_keeps_first_and_last():
    coords = ", ".join(f"{i}.0 {i}.0" for i in range(25))
    out = es.decimate_wkt_linestring(f"LINESTRING ({coords})", sample_rate=10)
    inner = out[len("LINESTRING (") : -1]
    kept = [c.strip() for c in inner.split(",")]
    assert kept[0] == "0.0 0.0"
    assert kept[-1] == "24.0 24.0"
    # first, indices 10 and 20 (sample_rate multiples), and last
    assert "10.0 10.0" in kept
    assert "20.0 20.0" in kept


# --- layer exporters ---
def _tactical():
    return {
        "targets": {
            "T1": {"lat": 62.0, "lon": 29.0, "alt": 40.0},
            "T2": {"lat": 62.1, "lon": 29.1},
        },
        "threat_profiles": {
            "W1": {
                "classification": "UAV_X",
                "target": "T1",
                "speed_kmh": 100,
                "alt_m": 50.0,
                "wkt_linestring": "LINESTRING (29.0 62.0, 29.1 62.1)",
            },
            "W2": {"wkt_linestring": ""},
        },
        "sensor_network": [
            {
                "id": "S1",
                "type": "RADAR",
                "lat": 62.0,
                "lon": 29.0,
                "range_m": 1000,
                "update_rate_sec": 10,
            }
        ],
    }


def test_export_targets(tmp_path):
    es.export_targets(_tactical(), str(tmp_path))
    rows = _read_csv(tmp_path / "targets_layer.csv")
    assert rows[0] == ["Target_Name", "Latitude", "Longitude", "Base_Elevation_M"]
    assert rows[1] == ["T1", "62.0", "29.0", "40.0"]
    assert rows[2] == ["T2", "62.1", "29.1", "0.0"]  # default alt


def test_export_flight_vectors_skips_empty_wkt(tmp_path):
    es.export_flight_vectors(_tactical(), str(tmp_path), sample_rate=10)
    rows = _read_csv(tmp_path / "flight_vectors_layer.csv")
    assert rows[0] == [
        "Vector_ID",
        "Classification",
        "Target",
        "Speed_KMH",
        "Planned_Altitude_M",
        "WKT",
    ]
    assert len(rows) == 2  # header + W1 only (W2 empty wkt skipped)
    assert rows[1][0] == "W1"


def test_export_sensor_network(tmp_path):
    es.export_sensor_network(_tactical(), str(tmp_path))
    rows = _read_csv(tmp_path / "sensor_network_layer.csv")
    assert rows[0][0] == "Sensor_Node_ID"
    assert rows[1] == ["S1", "RADAR", "62.0", "29.0", "1000", "10"]


def test_export_sensor_detections_full_and_defaults(tmp_path):
    messages = [
        {
            "sapientMessage": {
                "timestamp": "2026-01-01T00:00:00Z",
                "nodeId": "S1",
                "detectionReport": {
                    "objectId": "O1",
                    "state": "ACTIVE",
                    "classification": [{"type": "UAV_X", "confidence": 0.9}],
                    "location": {"x": 29.0, "y": 62.0, "z": 120.0},
                    "objectInfo": [{"type": "estimatedSwarmCount", "value": "7"}],
                },
            }
        },
        {"sapientMessage": {"detectionReport": {}}},
    ]
    es.export_sensor_detections(messages, str(tmp_path))
    with open(tmp_path / "sensor_detections_layer.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["Drone_Type"] == "UAV_X"
    assert rows[0]["Confidence"] == "0.9"
    assert rows[0]["Swarm_Count"] == "7"
    assert rows[0]["Elevation_M"] == "120.0"
    assert rows[1]["Drone_Type"] == "UNKNOWN"
    assert rows[1]["Confidence"] == "0.0"
    assert rows[1]["Swarm_Count"] == "1"
    assert rows[1]["Latitude"] == ""


# --- resolve_input ---
def test_resolve_input_absolute_json(tmp_path):
    p = tmp_path / "scen.json"
    p.write_text("{}", encoding="utf-8")
    assert es.resolve_input(str(p), str(tmp_path), "_tactical.json") == str(p)


def test_resolve_input_without_suffix_directory(tmp_path):
    (tmp_path / "foo_tactical.json").write_text("{}", encoding="utf-8")
    result = es.resolve_input("foo", str(tmp_path), "_tactical.json")
    assert result == str(tmp_path / "foo_tactical.json")


def test_resolve_input_location_fallback(tmp_path):
    (tmp_path / "joensuu_tactical.json").write_text("{}", encoding="utf-8")
    result = es.resolve_input(None, str(tmp_path), "_tactical.json", location="joensuu")
    assert result == str(tmp_path / "joensuu_tactical.json")


def test_resolve_input_returns_none(tmp_path):
    assert es.resolve_input(None, str(tmp_path), "_tactical.json") is None
    assert es.resolve_input("missing", str(tmp_path), "_tactical.json", location="nope") is None


# --- main ---
def _write_inputs(tmp_path):
    scen = tmp_path / "scen_tactical.json"
    scen.write_text(json.dumps(_tactical()), encoding="utf-8")
    msgs = tmp_path / "scen_messages.json"
    msgs.write_text(json.dumps([{"sapientMessage": {"detectionReport": {}}}]), encoding="utf-8")
    return scen, msgs


def test_main_happy_path(tmp_path, monkeypatch, capsys):
    scen, msgs = _write_inputs(tmp_path)
    outdir = tmp_path / "out"
    monkeypatch.setattr(
        "sys.argv",
        [
            "export_scenario.py",
            "--scenario",
            str(scen),
            "--messages",
            str(msgs),
            "--outdir",
            str(outdir),
        ],
    )
    es.main()
    for name in [
        "targets_layer.csv",
        "flight_vectors_layer.csv",
        "sensor_network_layer.csv",
        "sensor_detections_layer.csv",
    ]:
        assert (outdir / name).exists()
    assert "All layers built" in capsys.readouterr().out


def test_main_location(tmp_path, monkeypatch):
    _write_inputs(tmp_path)
    # scen/msgs named scen_tactical.json / scen_messages.json -> location "scen"
    monkeypatch.setattr(es, "TACTICAL_DIR", str(tmp_path))
    monkeypatch.setattr(es, "MESSAGES_DIR", str(tmp_path))
    outdir = tmp_path / "out"
    monkeypatch.setattr(
        "sys.argv", ["export_scenario.py", "--location", "scen", "--outdir", str(outdir)]
    )
    es.main()
    assert (outdir / "targets_layer.csv").exists()


def test_main_unresolved_scenario(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["export_scenario.py", "--outdir", str(tmp_path / "o")])
    with pytest.raises(FileNotFoundError, match="tactical scenario"):
        es.main()


def test_main_unresolved_messages(tmp_path, monkeypatch):
    scen, _ = _write_inputs(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["export_scenario.py", "--scenario", str(scen), "--outdir", str(tmp_path / "o")],
    )
    with pytest.raises(FileNotFoundError, match="messages file"):
        es.main()


def test_main_scenario_parse_error(tmp_path, monkeypatch, capsys):
    scen = tmp_path / "bad_tactical.json"
    scen.write_text("{not json", encoding="utf-8")
    msgs = tmp_path / "bad_messages.json"
    msgs.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "export_scenario.py",
            "--scenario",
            str(scen),
            "--messages",
            str(msgs),
            "--outdir",
            str(tmp_path / "o"),
        ],
    )
    es.main()
    assert "Error parsing tactical" in capsys.readouterr().out


def test_main_messages_parse_error(tmp_path, monkeypatch, capsys):
    scen, _ = _write_inputs(tmp_path)
    msgs = tmp_path / "scen_messages.json"
    msgs.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "export_scenario.py",
            "--scenario",
            str(scen),
            "--messages",
            str(msgs),
            "--outdir",
            str(tmp_path / "o"),
        ],
    )
    es.main()
    assert "Error parsing simulation" in capsys.readouterr().out
