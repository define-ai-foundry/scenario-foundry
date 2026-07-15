"""Tests for scenario_foundry.generation.optimize_vectors."""

import json

import pytest

from scenario_foundry.generation import optimize_vectors as ov


def test_read_elevation_missing_file(tmp_path):
    assert ov.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) == 80.0


def test_read_elevation_hit(tmp_path, write_asc):
    write_asc(tmp_path)  # center cell 250 at (62.75, 29.75)
    assert ov.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) == 250.0


def test_read_elevation_cache_reuse(tmp_path, write_asc):
    p = write_asc(tmp_path)
    assert ov.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) == 250.0
    # Overwrite the file; a cached read must still yield the original value.
    write_asc(tmp_path, matrix=[[1, 1, 1], [1, 1, 1], [1, 1, 1]])
    assert p.exists()
    assert ov.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) == 250.0


def test_read_elevation_nodata_sentinel(tmp_path, write_asc):
    write_asc(tmp_path, matrix=[[100, 100, 100], [100, -9999, 100], [100, 100, 100]])
    assert ov.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) == 80.0


def test_read_elevation_malformed_header(tmp_path):
    (tmp_path / "N62E029.asc").write_text("garbage\n", encoding="utf-8")
    assert ov.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) == 80.0


def test_read_elevation_blank_matrix_line(tmp_path):
    content = (
        "ncols 3\nnrows 3\nxllcorner 29.0\nyllcorner 62.0\ncellsize 0.5\nNODATA_value -9999\n"
        "100 100 100\n\n100 250 100\n100 100 100\n"
    )
    (tmp_path / "N62E029.asc").write_text(content, encoding="utf-8")
    assert ov.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) == 250.0


def test_read_elevation_index_error(tmp_path):
    content = (
        "ncols 3\nnrows 3\nxllcorner 29.0\nyllcorner 62.0\ncellsize 0.5\nNODATA_value -9999\n"
        "100\n100\n100\n"
    )
    (tmp_path / "N62E029.asc").write_text(content, encoding="utf-8")
    assert ov.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) == 80.0


def test_read_elevation_cached_none_entry(tmp_path, write_asc):
    write_asc(tmp_path)
    ov.GRID_CACHE["N62E029"] = None
    assert ov.read_elevation_from_local_asc(62.75, 29.75, str(tmp_path)) == 80.0


def test_parse_wkt_points_match():
    assert ov.parse_wkt_points("LINESTRING (29.0 62.0, 30.0 62.5)") == [(62.0, 29.0), (62.5, 30.0)]


def test_parse_wkt_points_no_match():
    assert ov.parse_wkt_points("nope") == []


def test_get_distance_meters():
    d = ov.get_distance_meters(62.0, 29.0, 63.0, 29.0)
    assert d == pytest.approx(111195, rel=0.001)


def test_optimize_track_too_few_waypoints():
    assert ov.optimize_track([(62.0, 29.0)], "irrelevant") == [(62.0, 29.0)]


def test_optimize_track_flat(tmp_path):
    pts = ov.optimize_track([(62.5, 29.5), (62.5, 29.503)], str(tmp_path))
    assert pts[0] == (62.5, 29.5)
    assert pts[-1] == (62.5, 29.503)
    assert len(pts) > 2


def test_optimize_track_repulsion(tmp_path, write_asc):
    # Fine grid (~111 m cells): a tall northern band triggers the repulsion +
    # force-clamping branches during the 200 m obstacle scan.
    n = 30
    matrix = [[3000.0 if r <= 19 else 80.0 for _ in range(n)] for r in range(n)]
    write_asc(tmp_path, ncols=n, nrows=n, xll=29.49, yll=62.49, cellsize=0.001, matrix=matrix)
    pts = ov.optimize_track([(62.5, 29.5), (62.5, 29.503)], str(tmp_path))
    assert pts[0] == (62.5, 29.5)
    assert pts[-1] == (62.5, 29.503)


def test_optimize_track_multi_leg():
    # Three waypoints -> a second leg (i != 0) so the start-append guard is skipped.
    pts = ov.optimize_track(
        [(62.5, 29.5), (62.5, 29.505), (62.5, 29.51)], "irrelevant_no_cache_dir"
    )
    assert pts[0] == (62.5, 29.5)
    assert pts[-1] == (62.5, 29.51)


def test_optimize_track_hits_iteration_cap():
    # A leg far longer than 15000*60 m never converges -> natural while-loop exit.
    pts = ov.optimize_track([(62.0, 29.0), (62.0, 48.0)], "irrelevant_no_cache_dir")
    assert pts[-1] == (62.0, 48.0)


def _scenario(tmp_path, profiles):
    p = tmp_path / "scen.json"
    p.write_text(
        json.dumps({"scenario_meta": {"name": "T"}, "threat_profiles": profiles}),
        encoding="utf-8",
    )
    return p


def test_main_default_output_and_empty_wkt(tmp_path, monkeypatch, capsys):
    scen = _scenario(
        tmp_path,
        {
            "W1": {"wkt_linestring": "LINESTRING (29.5 62.5, 29.503 62.5)"},
            "W2": {"wkt_linestring": ""},
        },
    )
    monkeypatch.setattr(
        "sys.argv", ["optimize_vectors.py", "--scenario", str(scen), "--cache", str(tmp_path)]
    )
    ov.main()
    out_path = tmp_path / "scen_tactical.json"
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["threat_profiles"]["W1"]["wkt_linestring"].startswith("LINESTRING (")
    assert data["threat_profiles"]["W2"]["wkt_linestring"] == ""
    assert "SUCCESS" in capsys.readouterr().out


def test_main_explicit_output(tmp_path, monkeypatch):
    scen = _scenario(tmp_path, {"W1": {"wkt_linestring": "LINESTRING (29.5 62.5, 29.503 62.5)"}})
    out = tmp_path / "custom.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "optimize_vectors.py",
            "--scenario",
            str(scen),
            "--cache",
            str(tmp_path),
            "--output",
            str(out),
        ],
    )
    ov.main()
    assert out.exists()


def test_main_seed_forwarded_to_seed_all(tmp_path, monkeypatch):
    scen = _scenario(tmp_path, {"W1": {"wkt_linestring": "LINESTRING (29.5 62.5, 29.503 62.5)"}})
    seen = []
    monkeypatch.setattr(ov, "seed_all", seen.append)
    monkeypatch.setattr(
        "sys.argv",
        ["optimize_vectors.py", "--scenario", str(scen), "--cache", str(tmp_path), "--seed", "42"],
    )
    ov.main()
    assert seen == [42]


def test_main_without_seed_skips_seed_all(tmp_path, monkeypatch):
    scen = _scenario(tmp_path, {"W1": {"wkt_linestring": "LINESTRING (29.5 62.5, 29.503 62.5)"}})
    seen = []
    monkeypatch.setattr(ov, "seed_all", seen.append)
    monkeypatch.setattr(
        "sys.argv", ["optimize_vectors.py", "--scenario", str(scen), "--cache", str(tmp_path)]
    )
    ov.main()
    assert seen == []
