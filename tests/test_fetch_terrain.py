"""Tests for scenario_foundry.generation.fetch_terrain."""

import json
from contextlib import contextmanager

from scenario_foundry.generation import fetch_terrain as ft


def test_parse_wkt_points_match():
    pts = ft.parse_wkt_points("LINESTRING (29.0 62.0, 30.0 62.5)")
    assert pts == [(62.0, 29.0), (62.5, 30.0)]


def test_parse_wkt_points_no_match():
    assert ft.parse_wkt_points("POINT (1 2)") == []


def test_extract_required_tiles_positive():
    data = {"threat_profiles": {"W1": {"wkt_linestring": "LINESTRING (29.5 62.5, 30.5 62.5)"}}}
    tiles = ft.extract_required_tiles(data)
    names = [t[2] for t in tiles]
    assert names == ["N62E029", "N62E030"]


def test_extract_required_tiles_negative():
    data = {"threat_profiles": {"W1": {"wkt_linestring": "LINESTRING (-5.5 -3.5, 29.0 62.0)"}}}
    tiles = ft.extract_required_tiles(data)
    names = [t[2] for t in tiles]
    assert "S04W006" in names
    assert "N62E029" in names


def _urlopen_returning(payload):
    @contextmanager
    def fake(*args, **kwargs):
        class Resp:
            def read(self):
                return payload

        yield Resp()

    return fake


def test_fetch_tile_success(tmp_path, monkeypatch, capsys):
    payload = b"ncols 3\n" + b"0" * 3000
    monkeypatch.setattr(ft.urllib.request, "urlopen", _urlopen_returning(payload))
    ok = ft.fetch_tile_from_opentopography(62, 29, "N62E029", str(tmp_path), "KEY")
    assert ok is True
    assert (tmp_path / "N62E029.asc").read_bytes() == payload
    assert "SUCCESS" in capsys.readouterr().out


def test_fetch_tile_error_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ft.urllib.request, "urlopen", _urlopen_returning(b"Error: bad" + b"x" * 3000)
    )
    assert ft.fetch_tile_from_opentopography(62, 29, "N62E029", str(tmp_path), "KEY") is False


def test_fetch_tile_too_small(tmp_path, monkeypatch):
    monkeypatch.setattr(ft.urllib.request, "urlopen", _urlopen_returning(b"tiny"))
    assert ft.fetch_tile_from_opentopography(62, 29, "N62E029", str(tmp_path), "KEY") is False


def test_fetch_tile_raises(tmp_path, monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr(ft.urllib.request, "urlopen", boom)
    assert ft.fetch_tile_from_opentopography(62, 29, "N62E029", str(tmp_path), "KEY") is False
    assert "FAIL" in capsys.readouterr().out


def _scenario_file(tmp_path):
    p = tmp_path / "scen.json"
    p.write_text(
        json.dumps(
            {"threat_profiles": {"W1": {"wkt_linestring": "LINESTRING (29.5 62.5, 29.6 62.6)"}}}
        ),
        encoding="utf-8",
    )
    return p


def test_main_no_api_key(tmp_path, monkeypatch, capsys):
    scen = _scenario_file(tmp_path)
    monkeypatch.setattr(ft.config, "OPENTOPOGRAPHY_API_KEY", None)
    monkeypatch.setattr(
        "sys.argv", ["fetch_terrain.py", "--scenario", str(scen), "--cache", str(tmp_path)]
    )
    ft.main()
    assert "API key is required" in capsys.readouterr().out


def test_main_cache_hit(tmp_path, monkeypatch, capsys):
    scen = _scenario_file(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "N62E029.asc").write_text("cached", encoding="utf-8")

    def fail(*args, **kwargs):
        raise AssertionError("should not fetch on cache hit")

    monkeypatch.setattr(ft, "fetch_tile_from_opentopography", fail)
    monkeypatch.setattr(
        "sys.argv",
        ["fetch_terrain.py", "--scenario", str(scen), "--cache", str(cache), "--api-key", "K"],
    )
    ft.main()
    assert "already exists" in capsys.readouterr().out


def test_main_fetches(tmp_path, monkeypatch):
    scen = _scenario_file(tmp_path)
    cache = tmp_path / "cache"
    calls = []

    def spy(lat_min, lon_min, tile_name, cache_dir, api_key):
        calls.append(tile_name)
        return True

    monkeypatch.setattr(ft, "fetch_tile_from_opentopography", spy)
    monkeypatch.setattr(
        "sys.argv",
        ["fetch_terrain.py", "--scenario", str(scen), "--cache", str(cache), "--api-key", "K"],
    )
    ft.main()
    assert calls == ["N62E029"]
