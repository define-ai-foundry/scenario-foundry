"""Tests for scenario_foundry.sapient.builder."""

import pytest

from sapient_msg.bsi_flex_335_v2_0 import location_pb2, range_bearing_pb2
from scenario_foundry.sapient import builder


def test_make_location_rounds_and_sets_constants():
    loc = builder.make_location(62.1234567, 29.7654321, 123.456)
    assert loc.y == 62.123457
    assert loc.x == 29.765432
    assert loc.z == 123.5
    assert loc.coordinate_system == location_pb2.LocationCoordinateSystem.Value(
        builder.SAP_COORD_LAT_LNG_DEG_M
    )
    assert loc.datum == location_pb2.LocationDatum.Value(builder.SAP_DATUM_WGS84)


def test_make_velocity_defaults():
    vel = builder.make_velocity(3.14, 2.72)
    assert vel.east_rate == 3.1
    assert vel.north_rate == 2.7
    assert vel.up_rate == 0.0
    assert vel.east_rate_error == 1.0
    assert vel.north_rate_error == 1.0
    assert vel.up_rate_error == 0.5


def test_make_velocity_custom_errors():
    vel = builder.make_velocity(1.0, 2.0, up=3.56, east_error=4.42, north_error=5.57, up_error=6.61)
    assert vel.up_rate == 3.6
    assert vel.east_rate_error == 4.4
    assert vel.north_rate_error == 5.6
    assert vel.up_rate_error == 6.6


def test_make_range_bearing_default_elevation():
    rb = builder.make_range_bearing(123.456, 789.012)
    assert rb.azimuth == 123.5
    assert rb.range == 789.0
    assert rb.elevation == 0.0
    assert rb.azimuth_error == 3.5
    assert rb.range_error == 50.0
    assert rb.elevation_error == 5.0
    assert rb.coordinate_system == range_bearing_pb2.RangeBearingCoordinateSystem.Value(
        builder.SAP_RANGE_BEARING_COORD_SYSTEM
    )
    assert rb.datum == range_bearing_pb2.RangeBearingDatum.Value(builder.SAP_RANGE_BEARING_DATUM)


def test_make_range_bearing_custom_elevation():
    rb = builder.make_range_bearing(10.0, 20.0, elevation=45.67)
    assert rb.elevation == 45.7


def test_add_classification_single_level_has_no_sub_class():
    report = builder.DetectionReport()
    entry = builder.add_classification(report, ["UAV_KAMIKAZE"], 0.83)
    assert len(report.classification) == 1
    assert entry.type == "UAV_KAMIKAZE"
    assert entry.confidence == pytest.approx(0.83, abs=1e-6)
    assert len(entry.sub_class) == 0


def test_add_classification_three_levels_nest_recursively():
    report = builder.DetectionReport()
    entry = builder.add_classification(report, ["Air vehicle", "UAV rotary wing", "Military"], 0.83)
    assert entry.type == "Air vehicle"
    assert entry.confidence == pytest.approx(0.83, abs=1e-6)
    assert len(entry.sub_class) == 1

    level1 = entry.sub_class[0]
    assert level1.type == "UAV rotary wing"
    assert level1.level == 1
    assert level1.HasField("confidence") is False
    assert len(level1.sub_class) == 1

    level2 = level1.sub_class[0]
    assert level2.type == "Military"
    assert level2.level == 2
    assert level2.HasField("confidence") is False
    assert len(level2.sub_class) == 0


def test_add_object_info_appends_entry():
    report = builder.DetectionReport()
    entry = builder.add_object_info(report, "estimatedSwarmCount", 8)
    assert len(report.object_info) == 1
    assert entry.type == "estimatedSwarmCount"
    assert entry.value == "8"


def test_serialize_report_camel_case_and_extra_merge():
    report = builder.DetectionReport(state="ACTIVE")
    report.object_id = "A-01-SWM-SW_DIVE"
    report.location.CopyFrom(builder.make_location(62.5, 29.5, 100.0))
    payload = builder.serialize_report(report, {"measuredAttributes": {"estimatedSwarmCount": 8}})
    assert payload["state"] == "ACTIVE"
    assert payload["objectId"] == "A-01-SWM-SW_DIVE"
    assert payload["location"]["coordinateSystem"] == builder.SAP_COORD_LAT_LNG_DEG_M
    assert payload["objectInfo"] == [{"type": "estimatedSwarmCount", "value": "8"}]


def test_serialize_report_without_extra_attributes():
    report = builder.DetectionReport(state="ACTIVE")
    payload = builder.serialize_report(report)
    assert payload["state"] == "ACTIVE"
    assert payload["objectInfo"] == []
