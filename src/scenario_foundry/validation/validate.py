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

import argparse
import datetime
import json
import pathlib

from jsonschema import ValidationError, validate
from shapely import wkt

from scenario_foundry import config, constants


class ScenarioValidationError(Exception):
    pass


def load_json(path: str | pathlib.Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_taxonomy(version: str = "v2_0") -> dict:
    """Load the BSI Flex 335 SAPIENT core taxonomy for the given version.

    Load errors are left to propagate; masking them would resurface as a
    misleading "unknown classification path" on the first threat profile.
    """
    taxonomy_path = config.SCHEMA_DIR / f"taxonomies/sapient_core_{version}.json"
    return load_json(taxonomy_path)


def taxonomy_classification_paths(taxonomy: dict) -> set[tuple[str, ...]]:
    """Flatten a taxonomy's `classifications` tree into the set of valid paths.

    Every prefix counts, so a partially resolved class like ("Air vehicle",) is
    valid. `subclasses` is absent, a list of level-2 names, or a dict mapping
    level-2 names to their level-3 names.
    """
    paths = set()

    for level1, node in taxonomy["classifications"].items():
        paths.add((level1,))

        subclasses = node.get("subclasses")
        if subclasses is None:
            continue

        if isinstance(subclasses, dict):
            for level2, level3_names in subclasses.items():
                paths.add((level1, level2))
                for level3 in level3_names:
                    paths.add((level1, level2, level3))
        else:
            for level2 in subclasses:
                paths.add((level1, level2))

    return paths


def validate_schema(scenario: dict, schema_path: str | pathlib.Path):
    schema = load_json(schema_path)

    try:
        validate(instance=scenario, schema=schema)
    except ValidationError as e:
        raise ScenarioValidationError(f"Schema validation failed: {e.message}") from e


def validate_coordinates(lat, lon, context="coordinate"):

    if not -90 <= lat <= 90:
        raise ScenarioValidationError(f"{context}: invalid latitude {lat}")

    if not -180 <= lon <= 180:
        raise ScenarioValidationError(f"{context}: invalid longitude {lon}")


def validate_scenario_meta(meta):

    try:
        datetime.datetime.fromisoformat(meta["start_time_iso"].replace("Z", "+00:00"))

    except ValueError as e:
        raise ScenarioValidationError("Invalid start_time_iso format") from e

    duration = meta["duration_seconds"]
    timestep = meta["time_step_seconds"]

    if duration % timestep != 0:
        raise ScenarioValidationError("duration_seconds must divide evenly by time_step_seconds")


def validate_targets(targets):

    for name, target in targets.items():
        validate_coordinates(target["lat"], target["lon"], f"target {name}")

        if target["alt"] < 0:
            raise ScenarioValidationError(f"target {name}: negative altitude")


def validate_threat_profiles(threats, valid_classification_paths):

    for name, threat in threats.items():
        if threat["count"] <= 0:
            raise ScenarioValidationError(f"{name}: count must be positive")

        if threat["speed_kmh"] <= 0:
            raise ScenarioValidationError(f"{name}: speed must be positive")

        if threat["alt_m"] < 0:
            raise ScenarioValidationError(f"{name}: negative altitude")

        classification = tuple(threat["classification"])
        if classification not in valid_classification_paths:
            raise ScenarioValidationError(
                f"{name}: unknown classification path {list(classification)}"
            )

        try:
            geometry = wkt.loads(threat["wkt_linestring"])

        except Exception as e:
            raise ScenarioValidationError(f"{name}: invalid WKT LineString") from e

        if geometry.geom_type != "LineString":
            raise ScenarioValidationError(f"{name}: WKT must be LineString")

        if len(geometry.coords) < 2:
            raise ScenarioValidationError(f"{name}: route requires at least two points")


def validate_sensor_network(sensors):

    ids = set()
    known_types = [t.value for t in constants.SensorType]

    for sensor in sensors:
        if sensor["id"] in ids:
            raise ScenarioValidationError(f"Duplicate sensor id: {sensor['id']}")

        ids.add(sensor["id"])

        if sensor["type"] not in known_types:
            raise ScenarioValidationError(
                f"{sensor['id']}: unknown sensor type {sensor['type']!r}; "
                f"expected one of {', '.join(known_types)}"
            )

        validate_coordinates(sensor["lat"], sensor["lon"], f"sensor {sensor['id']}")

        if sensor["range_m"] <= 0:
            raise ScenarioValidationError(f"{sensor['id']}: invalid range")

        if sensor["update_rate_sec"] <= 0:
            raise ScenarioValidationError(f"{sensor['id']}: invalid update rate")


def validate_terrain(anchors):

    for anchor in anchors:
        validate_coordinates(anchor["lat"], anchor["lon"], f"terrain {anchor['name']}")


def validate_scenario(scenario_path: str | pathlib.Path, schema_path: str | pathlib.Path):

    scenario = load_json(scenario_path)

    validate_schema(scenario, schema_path)

    validate_scenario_meta(scenario["scenario_meta"])

    validate_targets(scenario["targets"])

    taxonomy = load_taxonomy()
    valid_classification_paths = taxonomy_classification_paths(taxonomy)
    validate_threat_profiles(scenario["threat_profiles"], valid_classification_paths)

    validate_sensor_network(scenario["sensor_network"])

    validate_terrain(scenario["terrain_elevation_anchors"])

    return True


def main():
    parser = argparse.ArgumentParser(description="Validate a scenario file against its schema")
    parser.add_argument("--scenario", default=None, help="Path to the scenario file")
    parser.add_argument(
        "--location", default=None, help="Optional location name used in place of --scenario"
    )
    parser.add_argument(
        "--schema",
        default=config.SCHEMA_DIR / "scenario.schema.json",
        help="Path to the schema file",
    )
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

    validate_scenario(scenario_path=coarse_scenario_path, schema_path=args.schema)

    print("Scenario validation OK")


if __name__ == "__main__":
    main()
