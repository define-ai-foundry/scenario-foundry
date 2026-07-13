"""Shared fixtures and determinism guards for the scenario_foundry test suite."""

import random

import pytest

from scenario_foundry.generation import generate_sensor_data, optimize_vectors


@pytest.fixture(autouse=True)
def _determinism():
    """Seed RNG and clear module-level elevation caches before every test."""
    random.seed(1234)
    optimize_vectors.GRID_CACHE.clear()
    generate_sensor_data.SIM_GRID_CACHE.clear()
    yield
    optimize_vectors.GRID_CACHE.clear()
    generate_sensor_data.SIM_GRID_CACHE.clear()


def _write_asc(
    path, *, ncols=3, nrows=3, xll=29.0, yll=62.0, cellsize=0.5, nodata=-9999, matrix=None
):
    """Write a minimal ESRI Arc ASCII Grid tile."""
    if matrix is None:
        matrix = [[100, 100, 100], [100, 250, 100], [100, 100, 100]]
    lines = [
        f"ncols {ncols}",
        f"nrows {nrows}",
        f"xllcorner {xll}",
        f"yllcorner {yll}",
        f"cellsize {cellsize}",
        f"NODATA_value {nodata}",
    ]
    lines.extend(" ".join(str(v) for v in row) for row in matrix)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def write_asc():
    """Factory writing a tile file into a cache dir, defaulting to N62E029.asc."""

    def _factory(cache_dir, name="N62E029.asc", **kwargs):
        return _write_asc(cache_dir / name, **kwargs)

    return _factory
