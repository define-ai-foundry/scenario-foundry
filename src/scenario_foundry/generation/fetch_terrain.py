# Copyright 2026 Lempea Edge Oy / DEFINE AI Foundry
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import math
import os
import re
import ssl
import urllib.request

from scenario_foundry import config

DEFAULT_CACHE_DIR = str(config.TERRAIN_DIR)


def parse_wkt_points(wkt_str):
    points = []
    line_match = re.search(r"LINESTRING\s*\((.*)\)", wkt_str, re.IGNORECASE)
    if line_match:
        for pair in line_match.group(1).split(","):
            lon, lat = map(float, pair.strip().split())
            points.append((lat, lon))
    return points


def extract_required_tiles(scenario_data):
    tiles = set()
    all_coordinates = []
    for wave in scenario_data.get("threat_profiles", {}).values():
        all_coordinates.extend(parse_wkt_points(wave.get("wkt_linestring", "")))
    for lat, lon in all_coordinates:
        lat_floor = math.floor(lat)
        lon_floor = math.floor(lon)
        lat_pfx = f"N{lat_floor:02d}" if lat_floor >= 0 else f"S{abs(lat_floor):02d}"
        lon_pfx = f"E{lon_floor:03d}" if lon_floor >= 0 else f"W{abs(lon_floor):03d}"
        tiles.add((lat_floor, lon_floor, f"{lat_pfx}{lon_pfx}"))
    return sorted(tiles, key=lambda x: x[2])


def fetch_tile_from_opentopography(lat_min, lon_min, tile_name, cache_dir, api_key):
    lat_max = lat_min + 1.0
    lon_max = lon_min + 1.0

    # Shifting outputFormat to AAIGrid completely avoids binary tile offset extraction traps
    url = (
        f"https://portal.opentopography.org/API/globaldem"
        f"?demtype=AW3D30"
        f"&south={lat_min}&north={lat_max}"
        f"&west={lon_min}&east={lon_max}"
        f"&outputFormat=AAIGrid"
        f"&API_Key={api_key}"
    )

    print(f"  [API GATEWAY] Fetching plaintext AAIGrid dataset for tile: {tile_name}")
    try:
        ssl_context = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "SAPIENT-Generation-Engine"})  # noqa: S310
        with urllib.request.urlopen(req, timeout=65, context=ssl_context) as response:  # noqa: S310
            raw_data = response.read()
            if b"Error" in raw_data[:100] or len(raw_data) < 2000:
                return False

            target_path = os.path.join(cache_dir, f"{tile_name}.asc")
            with open(target_path, "wb") as f:
                f.write(raw_data)
            print(
                f"  [SUCCESS] Staged plaintext grid node -> {tile_name}.asc ({len(raw_data) / (1024 * 1024):.2f} MB)"
            )
            return True
    except Exception as e:
        print(f"  [FAIL] Payload transfer error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--cache", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--api-key", default="")
    args = parser.parse_args()

    with open(args.scenario, encoding="utf-8") as f:
        scenario = json.load(f)

    api_key = args.api_key if args.api_key else config.OPENTOPOGRAPHY_API_KEY

    if not api_key:
        print(
            "Error: OpenTopography API key is required. Provide it via --api-key or set OPENTOPOGRAPHY_API_KEY in .env"
        )
        return

    required_tiles = extract_required_tiles(scenario)
    os.makedirs(args.cache, exist_ok=True)

    for lat_min, lon_min, tile_name in required_tiles:
        expected_file_path = os.path.join(args.cache, f"{tile_name}.asc")
        if os.path.exists(expected_file_path):
            print(f"  [CACHE] Tile {tile_name}.asc already exists. Skipping download.")
            continue

        fetch_tile_from_opentopography(lat_min, lon_min, tile_name, args.cache, api_key)


if __name__ == "__main__":
    main()
