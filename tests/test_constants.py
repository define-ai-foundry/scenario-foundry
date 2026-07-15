"""Tests for scenario_foundry.constants."""

import pytest

from scenario_foundry import constants


def test_sensor_type_compares_equal_to_raw_string():
    # Raw scenario-JSON strings must interoperate with enum members.
    assert constants.SensorType.THERMAL_CAM == "THERMAL_CAM"
    assert "THERMAL_CAM" in [constants.SensorType.THERMAL_CAM, constants.SensorType.VISUAL_CAM]


@pytest.mark.parametrize(
    ("sensor_type", "expected"),
    [
        ("RADAR_STRATEGIC", True),
        ("RADAR_TACTICAL", True),
        ("MICRO_DOPPLER", False),
        ("ACOUSTIC", False),
        ("THERMAL_CAM", False),
        ("VISUAL_CAM", False),
    ],
)
def test_sensor_type_is_radar(sensor_type, expected):
    assert constants.SensorType.is_radar(sensor_type) is expected


def test_resolve_detection_thresholds_defaults():
    resolved = constants.resolve_detection_thresholds({})
    assert resolved == constants.DETECTION_THRESHOLD_DEFAULTS
    # A fresh copy, not the shared default dict.
    assert resolved is not constants.DETECTION_THRESHOLD_DEFAULTS


def test_resolve_detection_thresholds_override_merges():
    resolved = constants.resolve_detection_thresholds(
        {"detection_thresholds": {"radar_swarm_indicator_switch_m": 1234.0}}
    )
    assert resolved["radar_swarm_indicator_switch_m"] == 1234.0
    # Unspecified keys keep their defaults.
    assert resolved["thermal_cam_max_range_m"] == constants.DEFAULT_THERMAL_CAM_MAX_RANGE_M
    # Defaults untouched by the merge.
    assert (
        constants.DETECTION_THRESHOLD_DEFAULTS["radar_swarm_indicator_switch_m"]
        == constants.DEFAULT_RADAR_SWARM_INDICATOR_SWITCH_M
    )
