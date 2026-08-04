"""Tests for scenario_foundry.generation.generate_sensor_data."""

import json
from datetime import datetime

import pytest

from scenario_foundry import config, constants
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
def _wave(
    start,
    end,
    *,
    speed,
    alt,
    cls,
    suffix,
    count=8,
    delay=0,
    terminal_dive=None,
    rotor_speed_rps=None,
):
    (la1, lo1), (la2, lo2) = start, end
    cfg = {
        "count": count,
        "speed_kmh": speed,
        "alt_m": alt,
        "classification": cls if isinstance(cls, list) else [cls],
        "launch_delay_sec": delay,
        "id_suffix": suffix,
        "wkt_linestring": f"LINESTRING ({lo1} {la1}, {lo2} {la2})",
    }
    if terminal_dive is not None:
        cfg["terminal_dive"] = terminal_dive
    if rotor_speed_rps is not None:
        cfg["rotor_speed_rps"] = rotor_speed_rps
    return cfg


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
                cls=["Air vehicle", "UAV fixed wing", "Military"],
                suffix="DIVE",
            ),
            # Low-alt -> strategic radar altitude<100 -> continue.
            "LO_alt": _wave(
                (62.50, 29.50), (62.49, 29.49), speed=20, alt=5, cls="UAV_Low", suffix="LOW"
            ),
            # Decoy with launch delay -> launch-delay + terminal_dive=False branches.
            "DE_coy": _wave(
                (62.50, 29.50),
                (62.49, 29.49),
                speed=20,
                alt=1500,
                cls="UAV_Decoy",
                suffix="DECOY",
                delay=30,
                terminal_dive=False,
            ),
            # Close to tactical radar -> IND + velocity.
            "TA_ctic": _wave(
                (62.50, 29.70), (62.49, 29.69), speed=20, alt=500, cls="UAV_Kamikaze", suffix="TAC"
            ),
            # FPV -> micro-doppler rotor 220 branch (explicit rotor_speed_rps).
            "FP_v": _wave(
                (62.50, 29.70),
                (62.49, 29.69),
                speed=20,
                alt=100,
                cls="UAV_Rotary_FPV",
                suffix="FPV",
                count=6,
                rotor_speed_rps=220.0,
            ),
            # Non-FPV, no override -> default micro-doppler rotor 75 branch.
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
        if m["sapientMessage"]["nodeId"] == "RAD-TAC-2"
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


def _object_info_dict(report):
    return {oi["type"]: oi["value"] for oi in report.get("objectInfo", [])}


def _optical_statuses(msgs):
    statuses = set()
    for m in msgs:
        info = _object_info_dict(m["sapientMessage"]["detectionReport"])
        if "illuminationStatus" in info:
            statuses.add(info["illuminationStatus"])
    return statuses


def test_main_night_run(tmp_path, monkeypatch):
    msgs = _run_main(tmp_path, "2026-11-15T02:45:00Z", monkeypatch)
    assert isinstance(msgs, list) and msgs
    # sorted ascending by timestamp
    timestamps = [m["sapientMessage"]["timestamp"] for m in msgs]
    assert timestamps == sorted(timestamps)

    m0 = msgs[0]["sapientMessage"]
    assert m0["nodeId"]
    assert m0["timestamp"]
    assert m0["detectionReport"]["state"] == "ACTIVE"
    assert m0["detectionReport"]["classification"]

    nodes = {m["sapientMessage"]["nodeId"] for m in msgs}
    assert {"RAD-STRAT-1", "RAD-TAC-2", "MDOP-A", "ACU-X", "THERM-1", "VIS-1"} <= nodes

    # swarm + terminal-dive from strategic radar
    swarm = [
        r
        for m in msgs
        if "estimatedSwarmCount" in _object_info_dict(r := m["sapientMessage"]["detectionReport"])
    ]
    assert any(_object_info_dict(r).get("tacticalState") == "TERMINAL_DIVE" for r in swarm)

    # SW_dive's three-level path is emitted as nested subClass levels
    top = swarm[0]["classification"][0]
    assert top["type"] == "Air vehicle"
    level1 = top["subClass"][0]
    assert (level1["type"], level1["level"]) == ("UAV fixed wing", 1)
    level2 = level1["subClass"][0]
    assert (level2["type"], level2["level"]) == ("Military", 2)

    # micro-doppler rotor branches (both FPV=220 and plain=75)
    rotor_speeds = {
        _object_info_dict(r)["microDopplerRotorSpeedRps"]
        for m in msgs
        if "microDopplerRotorSpeedRps"
        in _object_info_dict(r := m["sapientMessage"]["detectionReport"])
    }
    assert rotor_speeds == {"220.0", "75.0"}

    # HIGH_G_DIVE maneuver state present
    maneuvers = {
        _object_info_dict(m["sapientMessage"]["detectionReport"]).get("maneuverState") for m in msgs
    }
    assert "HIGH_G_DIVE" in maneuvers

    # acoustic range-bearing report present
    assert any("rangeBearing" in m["sapientMessage"]["detectionReport"] for m in msgs)

    # night -> visual cam blind
    assert "POOR_BLIND" in _optical_statuses(msgs)


def test_every_generated_report_carries_a_position(tmp_path, monkeypatch):
    # A report without location or rangeBearing is unusable downstream, so the
    # stream must never contain one.
    msgs = _run_main(tmp_path, "2026-11-15T02:45:00Z", monkeypatch)
    assert msgs
    positionless = [
        m
        for m in msgs
        if "location" not in (r := m["sapientMessage"]["detectionReport"])
        and "rangeBearing" not in r
    ]
    assert positionless == []


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

    monkeypatch.setattr(g.builder, "serialize_report", boom)
    monkeypatch.setattr("sys.argv", ["g", "--scenario", str(scen), "--output", str(out)])
    with pytest.raises(ValueError, match="bad proto"):
        g.main()
    assert "CRITICAL PROTOC SERIALIZATION ERROR" in capsys.readouterr().out


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


# --- Sensor ---
def test_sensor_from_config_without_update_rate():
    sensor = g.Sensor.from_config(
        {"id": "RAD-TAC-2", "type": "RADAR_TACTICAL", "lat": 62.5, "lon": 29.7, "range_m": 25000}
    )
    assert sensor.id == "RAD-TAC-2"
    assert sensor.type == "RADAR_TACTICAL"
    assert sensor.lat == 62.5
    assert sensor.lon == 29.7
    assert sensor.range_m == 25000
    assert sensor.update_rate_sec is None


def test_sensor_from_config_with_update_rate():
    sensor = g.Sensor.from_config(
        {
            "id": "RAD-TAC-2",
            "type": "RADAR_TACTICAL",
            "lat": 62.5,
            "lon": 29.7,
            "range_m": 25000,
            "update_rate_sec": 15,
        }
    )
    assert sensor.update_rate_sec == 15


def test_sensor_code_trailing_digit():
    sensor = g.Sensor.from_config(
        {"id": "RAD-TAC-2", "type": "RADAR_TACTICAL", "lat": 0, "lon": 0, "range_m": 1}
    )
    assert sensor.code == "A-02"


def test_sensor_code_trailing_non_digit():
    sensor = g.Sensor.from_config(
        {"id": "ACU-X", "type": "ACOUSTIC", "lat": 0, "lon": 0, "range_m": 1}
    )
    assert sensor.code == "A-01"


# --- ThreatWave ---
def test_threat_wave_from_config():
    cfg = {
        "id_suffix": "DIVE",
        "count": 8,
        "speed_kmh": 20,
        "alt_m": 2000,
        "classification": ["Air vehicle", "UAV rotary wing", "Military"],
        "launch_delay_sec": 0,
        "wkt_linestring": "LINESTRING (29.50 62.50, 29.49 62.49)",
    }
    wave = g.ThreatWave.from_config("SW_dive", cfg)
    assert wave.wave_id == "SW_dive"
    assert wave.id_suffix == "DIVE"
    assert wave.count == 8
    assert wave.speed_kmh == 20
    assert wave.alt_m == 2000
    assert wave.classification == ["Air vehicle", "UAV rotary wing", "Military"]
    assert wave.launch_delay_sec == 0
    assert wave.waypoints == [{"lat": 62.50, "lon": 29.50}, {"lat": 62.49, "lon": 29.49}]
    assert wave.terminal_dive is True
    assert wave.rotor_speed_rps == constants.ROTOR_SPEED_DEFAULT_RPS


def test_threat_wave_from_config_behaviour_overrides():
    cfg = {
        "id_suffix": "DECOY",
        "count": 8,
        "speed_kmh": 20,
        "alt_m": 2000,
        "classification": ["UAV_Decoy"],
        "launch_delay_sec": 0,
        "wkt_linestring": "LINESTRING (29.50 62.50, 29.49 62.49)",
        "terminal_dive": False,
        "rotor_speed_rps": 220.0,
    }
    wave = g.ThreatWave.from_config("DE_coy", cfg)
    assert wave.terminal_dive is False
    assert wave.rotor_speed_rps == 220.0


def test_threat_wave_prefix():
    cfg = {
        "id_suffix": "DIVE",
        "count": 8,
        "speed_kmh": 20,
        "alt_m": 2000,
        "classification": ["UAV_Kamikaze"],
        "launch_delay_sec": 0,
        "wkt_linestring": "LINESTRING (29.50 62.50, 29.49 62.49)",
    }
    wave = g.ThreatWave.from_config("SW_dive", cfg)
    assert wave.prefix == "SW"


# --- parse_args ---
def test_parse_args_defaults():
    args = g.parse_args(["--scenario", "x.json"])
    assert args.scenario == "x.json"
    assert args.output == str(config.GENERATED_DIR)
    assert args.seed is None


def test_parse_args_seed():
    args = g.parse_args(["--scenario", "x.json", "--seed", "5"])
    assert args.seed == 5


# --- load_scenario ---
def test_load_scenario_missing(tmp_path, capsys):
    missing = tmp_path / "nope.json"
    assert g.load_scenario(str(missing)) is None
    assert "not found" in capsys.readouterr().out


def test_load_scenario_hit(tmp_path):
    scen = tmp_path / "scen.json"
    data = {"a": 1, "b": [2, 3]}
    scen.write_text(json.dumps(data), encoding="utf-8")
    assert g.load_scenario(str(scen)) == data


# --- prepare_threat_waves ---
def test_prepare_threat_waves_order_and_parsing():
    scenario = {
        "threat_profiles": {
            "SW_dive": {
                "id_suffix": "DIVE",
                "count": 8,
                "speed_kmh": 20,
                "alt_m": 2000,
                "classification": ["UAV_Kamikaze"],
                "launch_delay_sec": 0,
                "wkt_linestring": "LINESTRING (29.50 62.50, 29.49 62.49)",
            },
            "FP_v": {
                "id_suffix": "FPV",
                "count": 6,
                "speed_kmh": 20,
                "alt_m": 100,
                "classification": ["UAV_Rotary_FPV"],
                "launch_delay_sec": 0,
                "wkt_linestring": "LINESTRING (29.70 62.50, 29.69 62.49)",
            },
        }
    }
    waves = g.prepare_threat_waves(scenario)
    assert [w.wave_id for w in waves] == ["SW_dive", "FP_v"]
    assert all(isinstance(w, g.ThreatWave) for w in waves)
    assert waves[0].waypoints == [{"lat": 62.50, "lon": 29.50}, {"lat": 62.49, "lon": 29.49}]
    assert waves[1].waypoints == [{"lat": 62.50, "lon": 29.70}, {"lat": 62.49, "lon": 29.69}]


# --- DetectionReportBuilder.build() ---
def _wave_obj(
    wave_id,
    id_suffix,
    count,
    classification,
    terminal_dive=True,
    rotor_speed_rps=constants.ROTOR_SPEED_DEFAULT_RPS,
):
    return g.ThreatWave(
        wave_id=wave_id,
        id_suffix=id_suffix,
        count=count,
        speed_kmh=20,
        alt_m=2000,
        classification=classification,
        launch_delay_sec=0,
        waypoints=[],
        terminal_dive=terminal_dive,
        rotor_speed_rps=rotor_speed_rps,
    )


def test_detection_report_builder_swarm_branch():
    thresholds = constants.resolve_detection_thresholds({})
    sensor = g.Sensor(id="RAD-STRAT-1", type="RADAR_STRATEGIC", lat=62.6, lon=29.5, range_m=150000)
    wave = _wave_obj("SW_dive", "DIVE", count=8, classification=["UAV_Kamikaze"])
    builder = g.DetectionReportBuilder(
        sensor,
        wave,
        thresholds,
        lat=62.5,
        lon=29.5,
        noisy_lat=62.5001,
        noisy_lon=29.5001,
        absolute_altitude_msl=2080.0,
        dist=9000,
        mps=5.5,
        brg=45.0,
        is_diving=True,
        calculated_conf=0.8,
        current_sim_time=datetime(2026, 1, 1),
    )
    report, extra = builder.build()
    assert "-SWM-" in report.object_id
    assert report.HasField("location")
    assert extra["measuredAttributes"]["estimatedSwarmCount"] == wave.count
    assert extra["measuredAttributes"]["tacticalState"] == "TERMINAL_DIVE"


def test_detection_report_builder_micro_doppler_diving_branch():
    thresholds = constants.resolve_detection_thresholds({})
    sensor = g.Sensor(id="MDOP-A", type="MICRO_DOPPLER", lat=62.505, lon=29.70, range_m=3500)
    wave = _wave_obj(
        "FP_v", "FPV", count=6, classification=["UAV_Rotary_FPV"], rotor_speed_rps=220.0
    )
    builder = g.DetectionReportBuilder(
        sensor,
        wave,
        thresholds,
        lat=62.5,
        lon=29.7,
        noisy_lat=62.5001,
        noisy_lon=29.7001,
        absolute_altitude_msl=100.0,
        dist=100,
        mps=5.5,
        brg=45.0,
        is_diving=True,
        calculated_conf=0.8,
        current_sim_time=datetime(2026, 1, 1),
    )
    report, extra = builder.build()
    assert "-IND-" in report.object_id
    assert report.HasField("enu_velocity")
    assert extra["measuredAttributes"]["microDopplerRotorSpeedRps"] == 220.0
    assert extra["measuredAttributes"]["maneuverState"] == "HIGH_G_DIVE"


def test_detection_report_builder_acoustic_branch():
    thresholds = constants.resolve_detection_thresholds({})
    sensor = g.Sensor(id="ACU-X", type="ACOUSTIC", lat=62.50, lon=29.70, range_m=3000)
    wave = _wave_obj("SW_dive", "DIVE", count=8, classification=["UAV_Kamikaze"])
    builder = g.DetectionReportBuilder(
        sensor,
        wave,
        thresholds,
        lat=62.501,
        lon=29.701,
        noisy_lat=62.501,
        noisy_lon=29.701,
        absolute_altitude_msl=100.0,
        dist=150.0,
        mps=5.5,
        brg=45.0,
        is_diving=False,
        calculated_conf=0.8,
        current_sim_time=datetime(2026, 1, 1),
    )
    report, _extra = builder.build()
    assert report.object_id.startswith("ACU-")
    assert report.HasField("range_bearing")


def _payload_less_builder(sensor_type):
    """A detection inside sensor range but past every payload branch's own threshold."""
    sensor = g.Sensor(id="THERM-1", type=sensor_type, lat=62.50, lon=29.70, range_m=20000)
    return g.DetectionReportBuilder(
        sensor,
        _wave_obj("SW_dive", "DIVE", count=8, classification=["UAV_Kamikaze"]),
        constants.resolve_detection_thresholds({}),
        lat=62.58,
        lon=29.70,
        noisy_lat=62.58,
        noisy_lon=29.70,
        absolute_altitude_msl=200.0,
        dist=9000.0,
        mps=5.5,
        brg=45.0,
        is_diving=False,
        calculated_conf=0.8,
        current_sim_time=datetime(2026, 1, 1),
    )


def test_detection_report_builder_returns_none_beyond_camera_threshold():
    assert _payload_less_builder(constants.SensorType.THERMAL_CAM).build() is None


def test_detection_report_builder_unknown_sensor_type_raises():
    with pytest.raises(ValueError, match="no detection payload branch"):
        _payload_less_builder("ELINT_PASSIVE").build()


def test_detection_report_builder_unhandled_known_sensor_type_raises(monkeypatch):
    # A SensorType member the builder forgot is a bug, not a scenario condition.
    monkeypatch.setattr(g, "PAYLOAD_SENSOR_TYPES", frozenset())
    with pytest.raises(ValueError, match="THERMAL_CAM"):
        _payload_less_builder(constants.SensorType.THERMAL_CAM).build()


def test_payload_sensor_types_covers_every_sensor_type():
    assert {t.value for t in constants.SensorType} == g.PAYLOAD_SENSOR_TYPES


# --- generate_detection_for_sensor() terminal descent ---
def _final_leg_detection(monkeypatch, *, terminal_dive):
    """One micro-doppler detection halfway along a single-leg route, at ground level 0 m."""
    monkeypatch.setattr(g, "read_elevation_from_local_asc", lambda *a, **k: 0.0)
    wave = g.ThreatWave(
        wave_id="SW_dive",
        id_suffix="DIVE",
        count=8,
        speed_kmh=360,
        alt_m=1000,
        classification=["UAV_Kamikaze"],
        launch_delay_sec=0,
        waypoints=g.parse_wkt("LINESTRING (29.70 62.50, 29.69 62.49)"),
        terminal_dive=terminal_dive,
        rotor_speed_rps=constants.ROTOR_SPEED_DEFAULT_RPS,
    )
    sensor = g.Sensor(id="MDOP-A", type="MICRO_DOPPLER", lat=62.495, lon=29.695, range_m=3500)
    entry = g.generate_detection_for_sensor(
        sensor,
        wave,
        6.0,
        datetime(2026, 1, 1),
        "2026-01-01T00:00:00Z",
        {},
        constants.resolve_detection_thresholds({}),
        0,
    )
    return entry["sapientMessage"]["detectionReport"]


def _thermal_detection(monkeypatch, thermal_cam_max_range_m):
    """One thermal-cam detection ~10 km out: inside sensor range, past the camera default."""
    monkeypatch.setattr(g, "read_elevation_from_local_asc", lambda *a, **k: 0.0)
    wave = g.ThreatWave(
        wave_id="SW_dive",
        id_suffix="DIVE",
        count=8,
        speed_kmh=360,
        alt_m=1000,
        classification=["UAV_Kamikaze"],
        launch_delay_sec=0,
        waypoints=g.parse_wkt("LINESTRING (29.70 62.60, 29.70 62.59)"),
        terminal_dive=False,
        rotor_speed_rps=constants.ROTOR_SPEED_DEFAULT_RPS,
    )
    sensor = g.Sensor(id="THERM-1", type="THERMAL_CAM", lat=62.50, lon=29.70, range_m=20000)
    thresholds = constants.resolve_detection_thresholds(
        {"detection_thresholds": {"thermal_cam_max_range_m": thermal_cam_max_range_m}}
    )
    return g.generate_detection_for_sensor(
        sensor, wave, 6.0, datetime(2026, 1, 1), "2026-01-01T00:00:00Z", {}, thresholds, 0
    )


def test_detection_without_payload_yields_no_message(monkeypatch):
    assert _thermal_detection(monkeypatch, 4000.0) is None


def test_same_detection_inside_camera_threshold_is_emitted(monkeypatch):
    # Same geometry, threshold raised past it: proves the drop is the threshold's doing.
    entry = _thermal_detection(monkeypatch, 20000.0)
    assert "location" in entry["sapientMessage"]["detectionReport"]


def test_terminal_dive_descends_on_final_leg(monkeypatch):
    report = _final_leg_detection(monkeypatch, terminal_dive=True)
    assert report["location"]["z"] < 1000.0
    assert report["enuVelocity"]["upRate"] == -15.0
    assert _object_info_dict(report)["maneuverState"] == "HIGH_G_DIVE"


def test_terminal_dive_disabled_holds_altitude(monkeypatch):
    report = _final_leg_detection(monkeypatch, terminal_dive=False)
    assert report["location"]["z"] == 1000.0
    assert report["enuVelocity"]["upRate"] == 0.0
    assert "maneuverState" not in _object_info_dict(report)
