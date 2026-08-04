# Copyright 2026 Lempea Edge Oy / DEFINE AI Foundry
# SPDX-License-Identifier: Apache-2.0

"""Construct BSI Flex 335 DetectionReport protos directly, without dict round-trips.

Core SAPIENT fields are set on the proto message itself, so protobuf enforces field
names, types and enum values at assembly time. Custom simulation attributes that are
not part of the ICD (measuredAttributes, opticalAttributes, ...) have no proto home of
their own, so `serialize_report` folds them into the proto's repeated `object_info`
(TrackObjectInfo) field before serialization.
"""

from google.protobuf import json_format

from sapient_msg.bsi_flex_335_v2_0 import (
    detection_report_pb2,
    location_pb2,
    range_bearing_pb2,
    velocity_pb2,
)
from scenario_foundry.constants import (
    SAP_COORD_LAT_LNG_DEG_M,
    SAP_DATUM_WGS84,
    SAP_RANGE_BEARING_COORD_SYSTEM,
    SAP_RANGE_BEARING_DATUM,
)

DetectionReport = detection_report_pb2.DetectionReport

# Serialization options; kept in one place so every emitted report matches byte-for-byte.
_TO_DICT_OPTS = {
    "preserving_proto_field_name": False,
    "always_print_fields_with_no_presence": True,
}


def make_location(lat, lon, elevation_m):
    """
    Flex 335 Location:
    x = longitude
    y = latitude
    z = altitude
    """

    return location_pb2.Location(
        x=round(lon, 6),
        y=round(lat, 6),
        z=round(elevation_m, 1),
        coordinate_system=location_pb2.LocationCoordinateSystem.Value(SAP_COORD_LAT_LNG_DEG_M),
        datum=location_pb2.LocationDatum.Value(SAP_DATUM_WGS84),
    )


def make_velocity(east, north, up=0.0, east_error=1.0, north_error=1.0, up_error=0.5):

    return velocity_pb2.ENUVelocity(
        east_rate=round(east, 1),
        north_rate=round(north, 1),
        up_rate=round(up, 1),
        east_rate_error=round(east_error, 1),
        north_rate_error=round(north_error, 1),
        up_rate_error=round(up_error, 1),
    )


def make_range_bearing(azimuth, distance, elevation=0.0):

    return range_bearing_pb2.RangeBearing(
        azimuth=round(azimuth, 1),
        range=round(distance, 1),
        elevation=round(elevation, 1),
        azimuth_error=3.5,
        range_error=50.0,
        elevation_error=5.0,
        coordinate_system=range_bearing_pb2.RangeBearingCoordinateSystem.Value(
            SAP_RANGE_BEARING_COORD_SYSTEM
        ),
        datum=range_bearing_pb2.RangeBearingDatum.Value(SAP_RANGE_BEARING_DATUM),
    )


def add_classification(report, class_path, confidence):
    """Append one classification entry, nesting `class_path[1:]` as SubClass levels."""
    entry = report.classification.add()
    entry.type = class_path[0]
    entry.confidence = confidence
    node = entry
    for level, class_type in enumerate(class_path[1:], start=1):
        node = node.sub_class.add()
        node.type = class_type
        node.level = level
    return entry


def add_object_info(report, info_type, value):
    """Append one object_info entry (TrackObjectInfo) to a DetectionReport."""
    entry = report.object_info.add()
    entry.type = info_type
    entry.value = str(value)
    return entry


def serialize_report(report, extra_attributes=None):
    """Serialize a DetectionReport proto to its SAPIENT camelCase dict.

    Non-ICD simulation attributes (measuredAttributes, opticalAttributes, ...) have no
    place in the strict proto schema, so each leaf key/value from every group in
    `extra_attributes` is folded into the proto's repeated `object_info` field
    (TrackObjectInfo{type, value}) before serialization.
    """
    if extra_attributes:
        for group in extra_attributes.values():
            for key, value in group.items():
                add_object_info(report, key, value)
    return json_format.MessageToDict(report, **_TO_DICT_OPTS)
