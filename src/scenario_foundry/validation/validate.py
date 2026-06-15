# Copyright 2026 Lempea Edge Oy / DEFINE AI Foundry
# SPDX-License-Identifier: Apache-2.0

"""
Scenario configuration validator.

Validates:
- JSON schema compliance
- coordinate ranges
- WKT route geometry
- simulation timing consistency
- threat profiles
- sensor network definitions
"""

import json
import pathlib
import datetime
import argparse
from scenario_foundry import config

from jsonschema import validate, ValidationError
from shapely import wkt


class ScenarioValidationError(Exception):
    pass


def load_json(path: str | pathlib.Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_schema(config: dict, schema_path: str | pathlib.Path):
    schema = load_json(schema_path)

    try:
        validate(
            instance=config,
            schema=schema
        )
    except ValidationError as e:
        raise ScenarioValidationError(
            f"Schema validation failed: {e.message}"
        )


def validate_coordinates(lat, lon, context="coordinate"):

    if not -90 <= lat <= 90:
        raise ScenarioValidationError(
            f"{context}: invalid latitude {lat}"
        )

    if not -180 <= lon <= 180:
        raise ScenarioValidationError(
            f"{context}: invalid longitude {lon}"
        )


def validate_scenario_meta(meta):

    try:
        datetime.datetime.fromisoformat(
            meta["start_time_iso"].replace("Z", "+00:00")
        )

    except ValueError:
        raise ScenarioValidationError(
            "Invalid start_time_iso format"
        )

    duration = meta["duration_seconds"]
    timestep = meta["time_step_seconds"]

    if duration % timestep != 0:
        raise ScenarioValidationError(
            "duration_seconds must divide evenly by time_step_seconds"
        )


def validate_targets(targets):

    for name, target in targets.items():

        validate_coordinates(
            target["lat"],
            target["lon"],
            f"target {name}"
        )

        if target["alt"] < 0:
            raise ScenarioValidationError(
                f"target {name}: negative altitude"
            )


def validate_threat_profiles(threats):

    for name, threat in threats.items():

        if threat["count"] <= 0:
            raise ScenarioValidationError(
                f"{name}: count must be positive"
            )

        if threat["speed_kmh"] <= 0:
            raise ScenarioValidationError(
                f"{name}: speed must be positive"
            )

        if threat["alt_m"] < 0:
            raise ScenarioValidationError(
                f"{name}: negative altitude"
            )

        try:
            geometry = wkt.loads(
                threat["wkt_linestring"]
            )

        except Exception:
            raise ScenarioValidationError(
                f"{name}: invalid WKT LineString"
            )

        if geometry.geom_type != "LineString":
            raise ScenarioValidationError(
                f"{name}: WKT must be LineString"
            )

        if len(geometry.coords) < 2:
            raise ScenarioValidationError(
                f"{name}: route requires at least two points"
            )


def validate_sensor_network(sensors):

    ids = set()

    for sensor in sensors:

        if sensor["id"] in ids:
            raise ScenarioValidationError(
                f"Duplicate sensor id: {sensor['id']}"
            )

        ids.add(sensor["id"])

        validate_coordinates(
            sensor["lat"],
            sensor["lon"],
            f"sensor {sensor['id']}"
        )

        if sensor["range_m"] <= 0:
            raise ScenarioValidationError(
                f"{sensor['id']}: invalid range"
            )

        if sensor["update_rate_sec"] <= 0:
            raise ScenarioValidationError(
                f"{sensor['id']}: invalid update rate"
            )


def validate_terrain(anchors):

    for anchor in anchors:

        validate_coordinates(
            anchor["lat"],
            anchor["lon"],
            f"terrain {anchor['name']}"
        )


def validate_scenario(
    scenario_path: str | pathlib.Path,
    schema_path: str | pathlib.Path
):

    config = load_json(scenario_path)

    validate_schema(
        config,
        schema_path
    )

    validate_scenario_meta(
        config["scenario_meta"]
    )

    validate_targets(
        config["targets"]
    )

    validate_threat_profiles(
        config["threat_profiles"]
    )

    validate_sensor_network(
        config["sensor_network"]
    )

    validate_terrain(
        config["terrain_elevation_anchors"]
    )

    return True

def main():
    parser = argparse.ArgumentParser(description="Validate a scenario file against its schema")
    parser.add_argument("--scenario", default=None, help="Path to the scenario file")
    parser.add_argument("--location", default=None, help="Optional location name used in place of --scenario")
    parser.add_argument("--schema", default=config.SCHEMA_DIR / "scenario.schema.json", help="Path to the schema file")
    args = parser.parse_args()

    # 1. If location argument is provided, use it to resolve the scenario path
    if args.location:
        args.scenario = args.location

    # 2. If scenario argument is missing .json extension, append it
    if not args.scenario.endswith(".json"):
        args.scenario += ".json"

    # 3. Resolve the absolute path for the input coarse scenario
    coarse_scenario_path = config.SCENARIOS_DIR / args.scenario
    if not coarse_scenario_path.exists():
        print(f"[ERROR] Scenario configuration file not found at: {coarse_scenario_path}")
        return

    validate_scenario(
        scenario_path=coarse_scenario_path,
        schema_path=args.schema
    )

    print("Scenario validation OK")

if __name__ == "__main__":
    main()