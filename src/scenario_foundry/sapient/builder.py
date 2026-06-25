# Copyright 2026 Lempea Edge Oy / DEFINE AI Foundry
# SPDX-License-Identifier: Apache-2.0

from sapient_msg.bsi_flex_335_v2_0 import location_pb2


SAP_COORD_LAT_LNG_DEG_M = (
    "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M"
)

SAP_DATUM_WGS84 = (
    "LOCATION_DATUM_WGS84_E"
)

SAP_RANGE_BEARING_COORD_SYSTEM = (
    "RANGE_BEARING_COORDINATE_SYSTEM_DEGREES_M"
)

SAP_RANGE_BEARING_DATUM = (
    "RANGE_BEARING_DATUM_TRUE"
)


def make_location(lat, lon, elevation_m):
    """
    Flex 335 Location:
    x = longitude
    y = latitude
    z = altitude
    """

    return {
        "x": round(lon, 6),
        "y": round(lat, 6),
        "z": round(elevation_m, 1),
        "coordinateSystem": SAP_COORD_LAT_LNG_DEG_M,
        "datum": SAP_DATUM_WGS84,
    }


def make_velocity(east, north, up=0.0,
                  east_error=1.0,
                  north_error=1.0,
                  up_error=0.5):

    return {
        "eastRate": round(east, 1),
        "northRate": round(north, 1),
        "upRate": round(up, 1),

        "eastRateError": round(east_error, 1),
        "northRateError": round(north_error, 1),
        "upRateError": round(up_error, 1),
    }


def make_range_bearing(
        azimuth,
        distance,
        elevation=0.0):

    return {

        "azimuth": round(azimuth, 1),
        "range": round(distance, 1),
        "elevation": round(elevation, 1),

        "azimuthError": 3.5,
        "rangeError": 50.0,
        "elevationError": 5.0,

        "coordinateSystem":
            SAP_RANGE_BEARING_COORD_SYSTEM,

        "datum":
            SAP_RANGE_BEARING_DATUM,
    }