"""Tests for scenario_foundry.generation.generate_sensor_data."""

import json
from datetime import datetime

import pytest

from scenario_foundry.generation import generate_sensor_data as g


# --- geospatial / celestial helpers ---
def test_haversine_dist():
    assert g.haversine_dist(62.0, 29.0, 63.0, 29.0) == pytest.approx(111195, rel=0.001)
    assert g.haversine_dist(62.0, 29.0, 62.0, 29.0) == pytest.approx(0.0, abs=1e-6)


def test_calc_bearing_cardinal():
    assert g.calc_bearing(62.0, 29.0, 63.0, 29.0) == pytest.approx(0.0, abs=0.01)
    assert g.calc_bearing(62.0, 29.0, 62.0, 30.0) == pytest.approx(90.0, abs=0.5)


def test_add_metric_noise():
    lat, lon = g.add_metric_noise_to_wgs84(62.0, 29.0, 111.32, 0.0)
    assert lat > 62.0
    assert lon == 29.0
    lat2, lon2 = g.add_metric_noise_to_wgs84(62.0, 29.0, 0.0, 100.0)
    assert lat2 == 62.0
    assert lon2 > 29.0


def test_calculate_solar_elevation_day_vs_night():
    day = g.calculate_solar_elevation(62.5, 29.8, datetime(2026, 6, 21, 10, 0, 0))
    night = g.calculate_solar_elevation(62.5, 29.8, datetime(2026, 11, 15, 2, 45, 0))
    assert day > 0
    assert night < 0


def test_make_wgs84_location():
    loc = g.make_wgs84_location(62.1234567, 29.7654321, 123.45)
    assert loc["x"] == 29.765432
    assert loc["y"] == 62.123457
    assert loc["z"] == 123.5
    assert loc["coordinateSystem"] == "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M"
    assert loc["datum"] == "LOCATION_DATUM_WGS84_E"


# --- read_elevation_from_local_asc (returns None when missing) ---
def test_read_elevation_missing_returns_none(tmp_path):
    assert g.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) is None


def test_read_elevation_hit(tmp_path, write_asc):
    write_asc(tmp_path)
    assert g.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) == 250.0


def test_read_elevation_cache_reuse(tmp_path, write_asc):
    write_asc(tmp_path)
    assert g.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) == 250.0
    write_asc(tmp_path, matrix=[[1, 1, 1], [1, 1, 1], [1, 1, 1]])
    assert g.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) == 250.0


def test_read_elevation_nodata_sentinel_returns_none(tmp_path, write_asc):
    write_asc(tmp_path, matrix=[[100, 100, 100], [100, -9999, 100], [100, 100, 100]])
    assert g.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) is None


def test_read_elevation_malformed_returns_none(tmp_path):
    (tmp_path / "N62E029.asc").write_text("garbage\n", encoding="utf-8")
    assert g.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) is None


def test_read_elevation_blank_matrix_line(tmp_path):
    # Blank line inside the matrix exercises the `if line.strip()` false branch.
    content = (
        "ncols 3\nnrows 3\nxllcorner 29.0\nyllcorner 62.0\ncellsize 0.5\nNODATA_value -9999\n"
        "100 100 100\n\n100 250 100\n100 100 100\n"
    )
    (tmp_path / "N62E029.asc").write_text(content, encoding="utf-8")
    assert g.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) == 250.0


def test_read_elevation_index_error_returns_none(tmp_path):
    # Header claims 3 cols but rows have 1 -> mat[row][col] raises -> None.
    content = (
        "ncols 3\nnrows 3\nxllcorner 29.0\nyllcorner 62.0\ncellsize 0.5\nNODATA_value -9999\n"
        "100\n100\n100\n"
    )
    (tmp_path / "N62E029.asc").write_text(content, encoding="utf-8")
    assert g.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) is None


def test_read_elevation_cached_none_entry(tmp_path, write_asc):
    # A cached None entry short-circuits to None (defensive `if not data`).
    write_asc(tmp_path)
    g.SIM_GRID_CACHE["N62E029"] = None
    assert g.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) is None


# --- get_terrain_elevation ---
def test_get_terrain_elevation_raster_hit(monkeypatch):
    monkeypatch.setattr(g, "read_elevation_from_local_asc", lambda *a, **k: 321.0)
    assert g.get_terrain_elevation(62.5, 29.8, {}) == 321.0


def test_get_terrain_elevation_anchors_idw(monkeypatch):
    monkeypatch.setattr(g, "read_elevation_from_local_asc", lambda *a, **k: None)
    cfg = {
        "terrain_elevation_anchors": [
            {"lat": 62.5, "lon": 29.8, "elevation_msl": 100.0},
            {"lat": 63.5, "lon": 30.8, "elevation_msl": 200.0},
        ]
    }
    elev = g.get_terrain_elevation(62.5, 29.8, cfg)
    # Nearest anchor dominates the inverse-distance weighting.
    assert 100.0 <= elev < 101.0


def test_get_terrain_elevation_no_anchors(monkeypatch):
    monkeypatch.setattr(g, "read_elevation_from_local_asc", lambda *a, **k: None)
    assert g.get_terrain_elevation(62.5, 29.8, {}) == 80.0


# --- parse_wkt ---
def test_parse_wkt_match():
    pts = g.parse_wkt("LINESTRING (29.0 62.0, 30.0 62.5)")
    assert pts == [{"lat": 62.0, "lon": 29.0}, {"lat": 62.5, "lon": 30.0}]


def test_parse_wkt_no_match():
    assert g.parse_wkt("nope") == []


# --- get_position ---
def _wps():
    return [
        {"lat": 62.0, "lon": 29.0},
        {"lat": 62.0, "lon": 29.01},
        {"lat": 62.0, "lon": 29.02},
    ]


def test_get_position_mid_leg():
    _lat, lon, _brg, ratio, is_final, impacted = g.get_position(_wps(), 100.0)
    assert impacted is False
    assert is_final is False
    assert 29.0 < lon < 29.01
    assert 0.0 < ratio < 1.0


def test_get_position_final_leg():
    # Past the first leg (~522 m) but before the end -> final leg, not impacted.
    *_, is_final, impacted = g.get_position(_wps(), 700.0)
    assert is_final is True
    assert impacted is False


def test_get_position_past_end_impacted():
    lat, lon, _brg, _ratio, is_final, impacted = g.get_position(_wps(), 1_000_000.0)
    assert impacted is True
    assert is_final is True
    assert (lat, lon) == (62.0, 29.02)


# --- calculate_dynamic_confidence ---
@pytest.mark.parametrize(
    "sensor_type",
    ["RADAR_STRATEGIC", "THERMAL_CAM", "VISUAL_CAM", "ACOUSTIC", "MICRO_DOPPLER"],
)
def test_calculate_dynamic_confidence_branches(sensor_type):
    conf = g.calculate_dynamic_confidence(1000.0, 5000.0, sensor_type)
    assert 0.10 <= conf <= 0.99


# --- main() end-to-end ---
def _wave(start, end, *, speed, alt, cls, suffix, count=8, delay=0):
    (la1, lo1), (la2, lo2) = start, end
    return {
        "count": count,
        "speed_kmh": speed,
        "alt_m": alt,
        "classification": cls,
        "launch_delay_sec": delay,
        "id_suffix": suffix,
        "wkt_linestring": f"LINESTRING ({lo1} {la1}, {lo2} {la2})",
    }


def _full_scenario(start_time):
    """Rich scenario exercising every sensor type and detection branch."""
    return {
        "scenario_meta": {
            "name": "TestTheater",
            "start_time_iso": start_time,
            "duration_seconds": 60,
            "time_step_seconds": 30,
        },
        "targets": {"T": {"lat": 62.5, "lon": 29.7, "alt": 10.0}},
        "threat_profiles": {
            # High-alt non-decoy far from strategic radar -> swarm + TERMINAL_DIVE.
            "SW_dive": _wave(
                (62.50, 29.50),
                (62.49, 29.49),
                speed=20,
                alt=2000,
                cls="UAV_Kamikaze",
                suffix="DIVE",
            ),
            # Low-alt -> strategic radar altitude<100 -> continue.
            "LO_alt": _wave(
                (62.50, 29.50), (62.49, 29.49), speed=20, alt=5, cls="UAV_Low", suffix="LOW"
            ),
            # Decoy with launch delay -> launch-delay + non-diving-decoy branches.
            "DE_coy": _wave(
                (62.50, 29.50),
                (62.49, 29.49),
                speed=20,
                alt=1500,
                cls="UAV_Decoy",
                suffix="DECOY",
                delay=30,
            ),
            # Close to tactical radar -> IND + velocity.
            "TA_ctic": _wave(
                (62.50, 29.70), (62.49, 29.69), speed=20, alt=500, cls="UAV_Kamikaze", suffix="TAC"
            ),
            # FPV -> micro-doppler rotor 220 branch.
            "FP_v": _wave(
                (62.50, 29.70),
                (62.49, 29.69),
                speed=20,
                alt=100,
                cls="UAV_Rotary_FPV",
                suffix="FPV",
                count=6,
            ),
            # Non-FPV -> micro-doppler rotor 75 branch.
            "MP_lain": _wave(
                (62.50, 29.70), (62.49, 29.69), speed=20, alt=100, cls="UAV_Prop", suffix="PLAIN"
            ),
            # Fast on a tiny path -> impacts -> continue.
            "IM_pact": _wave(
                (62.50, 29.70),
                (62.5001, 29.7001),
                speed=300,
                alt=100,
                cls="UAV_Decoy",
                suffix="IMP",
            ),
            # High-alt close to strategic radar (dist<=8000) -> no report elif matches.
            "SC_lose": _wave(
                (62.595, 29.50),
                (62.594, 29.49),
                speed=20,
                alt=2000,
                cls="UAV_Kamikaze",
                suffix="SCLOSE",
            ),
        },
        "sensor_network": [
            {
                "id": "RAD-STRAT-1",
                "type": "RADAR_STRATEGIC",
                "lat": 62.60,
                "lon": 29.50,
                "range_m": 150000,
                "update_rate_sec": 30,
            },
            {
                "id": "RAD-TAC-2",
                "type": "RADAR_TACTICAL",
                "lat": 62.505,
                "lon": 29.70,
                "range_m": 25000,
                "update_rate_sec": 30,
            },
            {
                "id": "MDOP-A",
                "type": "MICRO_DOPPLER",
                "lat": 62.505,
                "lon": 29.70,
                "range_m": 3500,
                "update_rate_sec": 30,
            },
            # id ending in a non-digit -> s_code fallback '1' branch.
            {
                "id": "ACU-X",
                "type": "ACOUSTIC",
                "lat": 62.50,
                "lon": 29.70,
                "range_m": 3000,
                "update_rate_sec": 30,
            },
            {
                "id": "THERM-1",
                "type": "THERMAL_CAM",
                "lat": 62.50,
                "lon": 29.70,
                "range_m": 4000,
                "update_rate_sec": 30,
            },
            {
                "id": "VIS-1",
                "type": "VISUAL_CAM",
                "lat": 62.50,
                "lon": 29.70,
                "range_m": 3000,
                "update_rate_sec": 30,
            },
        ],
        "terrain_elevation_anchors": [
            {"name": "A", "lat": 62.5, "lon": 29.6, "elevation_msl": 80.0},
            {"name": "B", "lat": 62.6, "lon": 29.7, "elevation_msl": 90.0},
        ],
    }


def _run_main(tmp_path, start_time, monkeypatch, *, mutate=None):
    scenario = _full_scenario(start_time)
    if mutate is not None:
        mutate(scenario)
    scen = tmp_path / "scen.json"
    scen.write_text(json.dumps(scenario), encoding="utf-8")
    out = tmp_path / "out.json"
    monkeypatch.setattr("sys.argv", ["g", "--scenario", str(scen), "--output", str(out)])
    g.main()
    return json.loads(out.read_text(encoding="utf-8"))


def _tactical_radar_object_ids(msgs):
    # Object ids for the TA_TAC wave, which sits right next to RAD-TAC-2 (a
    # near detection, so it straddles the swarm/indicator switch distance).
    return [
        oid
        for m in msgs
        if m["sapientMessage"]["header"]["sourceNode"]["nodeId"] == "RAD-TAC-2"
        and "TA_TAC" in (oid := m["sapientMessage"]["detectionReport"].get("objectId", ""))
    ]


def test_radar_switch_threshold_is_configurable(tmp_path, monkeypatch):
    # Default 8000 m switch: the nearby wave reports as indicators.
    default_ids = _tactical_radar_object_ids(
        _run_main(tmp_path, "2026-11-15T02:45:00Z", monkeypatch)
    )
    assert default_ids
    assert all("-IND-" in oid for oid in default_ids)

    # Lowering the switch flips the same detections to the swarm branch.
    lowered_ids = _tactical_radar_object_ids(
        _run_main(
            tmp_path,
            "2026-11-15T02:45:00Z",
            monkeypatch,
            mutate=lambda s: s.update(
                {"detection_thresholds": {"radar_swarm_indicator_switch_m": 10}}
            ),
        )
    )
    assert lowered_ids
    assert all("-SWM-" in oid for oid in lowered_ids)


def _optical_statuses(msgs):
    statuses = set()
    for m in msgs:
        opt = m["sapientMessage"]["detectionReport"].get("opticalAttributes", {})
        if "illuminationStatus" in opt:
            statuses.add(opt["illuminationStatus"])
    return statuses


def test_main_night_run(tmp_path, monkeypatch):
    msgs = _run_main(tmp_path, "2026-11-15T02:45:00Z", monkeypatch)
    assert isinstance(msgs, list) and msgs
    # sorted ascending by timestamp
    timestamps = [m["sapientMessage"]["header"]["timestamp"] for m in msgs]
    assert timestamps == sorted(timestamps)

    m0 = msgs[0]["sapientMessage"]
    assert m0["header"]["icdVersion"] == "2.0"
    assert m0["header"]["sourceNode"]["type"] == "CHILD"
    assert m0["detectionReport"]["state"] == "ACTIVE"
    assert m0["detectionReport"]["classification"]

    nodes = {m["sapientMessage"]["header"]["sourceNode"]["nodeId"] for m in msgs}
    assert {"RAD-STRAT-1", "RAD-TAC-2", "MDOP-A", "ACU-X", "THERM-1", "VIS-1"} <= nodes

    # swarm + terminal-dive from strategic radar
    swarm = [
        r
        for m in msgs
        if "estimatedSwarmCount"
        in (r := m["sapientMessage"]["detectionReport"]).get("measuredAttributes", {})
    ]
    assert any(
        a.get("tacticalState") == "TERMINAL_DIVE" for a in (r["measuredAttributes"] for r in swarm)
    )

    # micro-doppler rotor branches (both FPV=220 and plain=75)
    rotor_speeds = {
        r["measuredAttributes"]["microDopplerRotorSpeedRps"]
        for m in msgs
        if "microDopplerRotorSpeedRps"
        in (r := m["sapientMessage"]["detectionReport"]).get("measuredAttributes", {})
    }
    assert rotor_speeds == {220.0, 75.0}

    # HIGH_G_DIVE maneuver state present
    maneuvers = {
        m["sapientMessage"]["detectionReport"].get("measuredAttributes", {}).get("maneuverState")
        for m in msgs
    }
    assert "HIGH_G_DIVE" in maneuvers

    # acoustic range-bearing report present
    assert any("rangeBearing" in m["sapientMessage"]["detectionReport"] for m in msgs)

    # night -> visual cam blind
    assert "POOR_BLIND" in _optical_statuses(msgs)


def test_main_day_run(tmp_path, monkeypatch):
    msgs = _run_main(tmp_path, "2026-06-21T10:00:00Z", monkeypatch)
    assert "OPTIMAL" in _optical_statuses(msgs)


def test_main_scenario_not_found(tmp_path, monkeypatch, capsys):
    missing = tmp_path / "nope.json"
    monkeypatch.setattr("sys.argv", ["g", "--scenario", str(missing)])
    g.main()
    assert "not found" in capsys.readouterr().out


def test_main_proto_validation_error(tmp_path, monkeypatch, capsys):
    scen = tmp_path / "scen.json"
    scen.write_text(json.dumps(_full_scenario("2026-11-15T02:45:00Z")), encoding="utf-8")
    out = tmp_path / "out.json"

    def boom(*args, **kwargs):
        raise ValueError("bad proto")

    monkeypatch.setattr(g.json_format, "ParseDict", boom)
    monkeypatch.setattr("sys.argv", ["g", "--scenario", str(scen), "--output", str(out)])
    with pytest.raises(ValueError, match="bad proto"):
        g.main()
    assert "CRITICAL PROTOC VALIDATION ERROR" in capsys.readouterr().out


def test_main_seed_forwarded_to_seed_all(tmp_path, monkeypatch):
    scen = tmp_path / "scen.json"
    scen.write_text(json.dumps(_full_scenario("2026-11-15T02:45:00Z")), encoding="utf-8")
    out = tmp_path / "out.json"
    seen = []
    monkeypatch.setattr(g, "seed_all", seen.append)
    monkeypatch.setattr(
        "sys.argv", ["g", "--scenario", str(scen), "--output", str(out), "--seed", "42"]
    )
    g.main()
    assert seen == [42]


def test_main_same_seed_is_reproducible(tmp_path, monkeypatch):
    scen = tmp_path / "scen.json"
    scen.write_text(json.dumps(_full_scenario("2026-11-15T02:45:00Z")), encoding="utf-8")

    def _run():
        out = tmp_path / "out.json"
        monkeypatch.setattr(
            "sys.argv", ["g", "--scenario", str(scen), "--output", str(out), "--seed", "7"]
        )
        g.main()
        return out.read_text(encoding="utf-8")

    assert _run() == _run()
