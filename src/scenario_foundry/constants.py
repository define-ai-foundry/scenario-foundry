# Copyright 2026 Lempea Edge Oy / DEFINE AI Foundry
# SPDX-License-Identifier: Apache-2.0

"""Centralized SAPIENT constants, enum strings, and default detection thresholds.

Runtime paths and environment live in `config`; this module holds the
domain-level magic values shared across the generation pipeline.
"""

from enum import Enum

# --- Geospatial ---
EARTH_RADIUS_M = 6371000.0

# --- SAPIENT BSI Flex 335 coordinate systems & datums ---
SAP_COORD_LAT_LNG_DEG_M = "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M"
SAP_DATUM_WGS84 = "LOCATION_DATUM_WGS84_E"
SAP_RANGE_BEARING_COORD_SYSTEM = "RANGE_BEARING_COORDINATE_SYSTEM_DEGREES_M"
SAP_RANGE_BEARING_DATUM = "RANGE_BEARING_DATUM_TRUE"

# --- SAPIENT message header ---
ICD_VERSION = "2.0"
NODE_TYPE_CHILD = "CHILD"

# --- Detection report enum strings ---
DETECTION_STATE_ACTIVE = "ACTIVE"
TACTICAL_STATE_TERMINAL_DIVE = "TERMINAL_DIVE"
MANEUVER_STATE_HIGH_G_DIVE = "HIGH_G_DIVE"

# --- Optical attribute strings ---
SPECTRUM_LWIR_THERMAL = "LWIR_THERMAL"
SPECTRUM_VISIBLE_COLOR = "VISIBLE_COLOR"
VISUAL_CONFIRMATION_POSITIVE = "POSITIVE"
VISUAL_CONFIRMATION_UNCONFIRMED = "UNCONFIRMED"
ILLUMINATION_OPTIMAL = "OPTIMAL"
ILLUMINATION_POOR_BLIND = "POOR_BLIND"
THERMAL_INTENSITY_HIGH = "HIGH"


# --- Sensor types ---
# str-based so raw scenario-JSON strings compare equal to members and still
# serialize as plain strings through protobuf/JSON.
class SensorType(str, Enum):
    """SAPIENT sensor node types used across the generation pipeline."""

    RADAR_STRATEGIC = "RADAR_STRATEGIC"
    RADAR_TACTICAL = "RADAR_TACTICAL"
    MICRO_DOPPLER = "MICRO_DOPPLER"
    ACOUSTIC = "ACOUSTIC"
    THERMAL_CAM = "THERMAL_CAM"
    VISUAL_CAM = "VISUAL_CAM"

    @classmethod
    def is_radar(cls, sensor_type):
        """True for any radar variant (strategic/tactical)."""
        return "RADAR" in sensor_type


# --- Threat classification tokens ---
CLASSIFICATION_DECOY = "UAV_Decoy"
# Substring flagging first-person-view rotary threats.
CLASSIFICATION_FPV_MARKER = "FPV"

# --- Terrain elevation ---
DEFAULT_TERRAIN_ELEVATION_M = 80.0
# Raster values at or below this are treated as no-data.
ELEVATION_NODATA_THRESHOLD_M = -500.0

# --- Micro-doppler rotor speeds (rev/s) ---
ROTOR_SPEED_FPV_RPS = 220.0
ROTOR_SPEED_DEFAULT_RPS = 75.0

# --- Default detection thresholds ---
# Overridable per scenario via a top-level `detection_thresholds` object;
# see `resolve_detection_thresholds`.
DEFAULT_RADAR_SWARM_INDICATOR_SWITCH_M = 8000.0
DEFAULT_THERMAL_CAM_MAX_RANGE_M = 4000.0
DEFAULT_VISUAL_CAM_MAX_RANGE_M = 3000.0
DEFAULT_RADAR_STRATEGIC_MIN_ALTITUDE_M = 100.0
DEFAULT_CIVIL_TWILIGHT_ELEVATION_DEG = -6.0

DETECTION_THRESHOLD_DEFAULTS = {
    "radar_swarm_indicator_switch_m": DEFAULT_RADAR_SWARM_INDICATOR_SWITCH_M,
    "thermal_cam_max_range_m": DEFAULT_THERMAL_CAM_MAX_RANGE_M,
    "visual_cam_max_range_m": DEFAULT_VISUAL_CAM_MAX_RANGE_M,
    "radar_strategic_min_altitude_m": DEFAULT_RADAR_STRATEGIC_MIN_ALTITUDE_M,
    "civil_twilight_elevation_deg": DEFAULT_CIVIL_TWILIGHT_ELEVATION_DEG,
}


def resolve_detection_thresholds(scenario):
    """Merge a scenario's optional `detection_thresholds` over the defaults."""
    resolved = dict(DETECTION_THRESHOLD_DEFAULTS)
    resolved.update(scenario.get("detection_thresholds", {}))
    return resolved
