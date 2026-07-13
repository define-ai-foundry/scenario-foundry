"""Tests for scenario_foundry.sapient.builder."""

from scenario_foundry.sapient import builder


def test_make_location_rounds_and_sets_constants():
    loc = builder.make_location(62.1234567, 29.7654321, 123.456)
    assert loc["y"] == 62.123457
    assert loc["x"] == 29.765432
    assert loc["z"] == 123.5
    assert loc["coordinateSystem"] == builder.SAP_COORD_LAT_LNG_DEG_M
    assert loc["datum"] == builder.SAP_DATUM_WGS84


def test_make_velocity_defaults():
    vel = builder.make_velocity(3.14, 2.72)
    assert vel == {
        "eastRate": 3.1,
        "northRate": 2.7,
        "upRate": 0.0,
        "eastRateError": 1.0,
        "northRateError": 1.0,
        "upRateError": 0.5,
    }


def test_make_velocity_custom_errors():
    vel = builder.make_velocity(1.0, 2.0, up=3.56, east_error=4.42, north_error=5.57, up_error=6.61)
    assert vel["upRate"] == 3.6
    assert vel["eastRateError"] == 4.4
    assert vel["northRateError"] == 5.6
    assert vel["upRateError"] == 6.6


def test_make_range_bearing_default_elevation():
    rb = builder.make_range_bearing(123.456, 789.012)
    assert rb["azimuth"] == 123.5
    assert rb["range"] == 789.0
    assert rb["elevation"] == 0.0
    assert rb["azimuthError"] == 3.5
    assert rb["rangeError"] == 50.0
    assert rb["elevationError"] == 5.0
    assert rb["coordinateSystem"] == builder.SAP_RANGE_BEARING_COORD_SYSTEM
    assert rb["datum"] == builder.SAP_RANGE_BEARING_DATUM


def test_make_range_bearing_custom_elevation():
    rb = builder.make_range_bearing(10.0, 20.0, elevation=45.67)
    assert rb["elevation"] == 45.7
