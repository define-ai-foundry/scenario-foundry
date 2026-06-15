# Copyright 2026 Lempea Edge Oy / DEFINE AI Foundry
# SPDX-License-Identifier: Apache-2.0

import json
import os
import sys
import re
import csv
import argparse
from pathlib import Path
from src.scenario_foundry import config

# Ensure Python can discover modules inside the src/ directory
sys.path.append(str(Path(__file__).resolve().parent.parent))

TACTICAL_DIR = str(config.TACTICAL_DIR)
MESSAGES_DIR = str(config.GENERATED_DIR)
OUTPUT_DIR = str(config.EXPORT_DIR)

# --- GEOSPATIAL HELPER FUNCTIONS ---
def decimate_wkt_linestring(wkt_str, sample_rate=10):
    """
    Parses a WKT LINESTRING, samples every N-th point to prevent Google Maps lag,
    while strictly preserving the absolute start and end points.
    """
    if not wkt_str:
        return ""
    match = re.search(r'LINESTRING\s*\((.*)\)', wkt_str, re.IGNORECASE)
    if not match:
        return wkt_str.strip().upper()
        
    raw_coords = match.group(1).split(',')
    clean_coords = [c.strip() for c in raw_coords if c.strip()]
    
    if len(clean_coords) <= 2:
        return wkt_str.strip().upper()
        
    decimated_list = []
    for idx, coord in enumerate(clean_coords):
        if idx == 0 or idx == len(clean_coords) - 1 or (idx % sample_rate == 0):
            decimated_list.append(coord)
            
    return f"LINESTRING ({', '.join(decimated_list)})"

# --- LAYER EXPORTERS ---
def export_targets(tactical_data, output_dir):
    """Generates the static target infrastructure layer."""
    output_path = os.path.join(output_dir, "targets_layer.csv")
    targets = tactical_data.get("targets", {})
    
    headers = ["Target_Name", "Latitude", "Longitude", "Base_Elevation_M"]
    
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for name, coords in targets.items():
            writer.writerow([
                name,
                coords.get("lat"),
                coords.get("lon"),
                coords.get("alt", 0.0)
            ])
    print(f"[SUCCESS] Exported Targets Layer: {output_path}")

def export_flight_vectors(tactical_data, output_dir, sample_rate):
    """Generates the continuous flight path vector layer using unquoted headers for Google Maps WKT validation."""
    output_path = os.path.join(output_dir, "flight_vectors_layer.csv")
    threat_profiles = tactical_data.get("threat_profiles", {})
    
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        f.write("Vector_ID,Classification,Target,Speed_KMH,Planned_Altitude_M,WKT\n")
        
        writer = csv.writer(f, lineterminator='\n', quoting=csv.QUOTE_ALL)
        for profile_id, profile in threat_profiles.items():
            wkt_string = profile.get("wkt_linestring", "")
            if not wkt_string:
                continue
                
            compact_wkt = decimate_wkt_linestring(wkt_string, sample_rate=sample_rate)
            writer.writerow([
                profile_id,
                profile.get("classification", "UNKNOWN"),
                profile.get("target", "UNKNOWN"),
                profile.get("speed_kmh", 0),
                int(profile.get("alt_m", 0)),
                compact_wkt
            ])
    print(f"[SUCCESS] Exported Flight Vectors Layer: {output_path}")

def export_sensor_network(tactical_data, output_dir):
    """Generates the defensive sensor node location layer."""
    output_path = os.path.join(output_dir, "sensor_network_layer.csv")
    sensors = tactical_data.get("sensor_network", [])
    
    headers = ["Sensor_Node_ID", "Sensor_Type", "Latitude", "Longitude", "Coverage_Range_M", "Update_Rate_Sec"]
    
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for sensor in sensors:
            writer.writerow([
                sensor.get("id"),
                sensor.get("type"),
                sensor.get("lat"),
                sensor.get("lon"),
                sensor.get("range_m"),
                sensor.get("update_rate_sec")
            ])
    print(f"[SUCCESS] Exported Sensor Network Layer: {output_path}")

def export_sensor_detections(messages_data, output_dir):
    """Flattens incoming SAPIENT sensor data messages into a dynamic layer."""
    output_path = os.path.join(output_dir, "sensor_detections_layer.csv")
    
    fields = [
        'Timestamp', 'Sensor_Node_ID', 'Track_ID', 'Status', 'Drone_Type', 
        'Confidence', 'Latitude', 'Longitude', 'Elevation_M', 'Swarm_Count'
    ]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()
        
        for entry in messages_data:
            msg = entry.get("sapientMessage", {})
            header = msg.get("header", {})
            report = msg.get("detectionReport", {})
            
            class_list = report.get("classificationList", [])
            drone_type = "UNKNOWN"
            confidence = 0.0
            if isinstance(class_list, list) and len(class_list) > 0:
                drone_type = class_list[0].get("type", "UNKNOWN")
                confidence = class_list[0].get("confidence", 0.0)
            
            location = report.get("locationList", {}).get("location", {})
            bearing_loc = report.get("bearingList", {})
            
            lat = location.get('latitude') if location.get('latitude') is not None else bearing_loc.get('sensorLatitude')
            lon = location.get('longitude') if location.get('longitude') is not None else bearing_loc.get('sensorLongitude')
            alt = location.get('elevation', 0.0)
            
            attributes = report.get("measuredAttributes", {})
            
            writer.writerow({
                'Timestamp': header.get('timestamp'),
                'Sensor_Node_ID': header.get('nodeId'),
                'Track_ID': report.get('trackId'),
                'Status': report.get('state'),
                'Drone_Type': drone_type,
                'Confidence': confidence,
                'Latitude': lat,
                'Longitude': lon,
                'Elevation_M': alt,
                'Swarm_Count': attributes.get('estimatedSwarmCount', 1)
            })
    print(f"[SUCCESS] Exported Sensor Detections Layer: {output_path}")

#  --- INPUT RESOLVER ---
def resolve_input(value, directory, suffix, location=None):
    if value:
        path = Path(value)

        candidates = [path]

        if path.suffix == ".json":
            candidates.append(
                Path(path.stem + suffix)
            )
        else:
            candidates.append(
                Path(str(path) + suffix)
            )

        for c in candidates:
            if c.is_absolute() and c.exists():
                return str(c)

            local = Path(directory) / c
            if local.exists():
                return str(local)

    if location:
        candidate = Path(directory) / f"{location}{suffix}"
        if candidate.exists():
            return str(candidate)

    return None

# --- EXECUTION MOTOR ---
def main():
    parser = argparse.ArgumentParser(description="Production Scenario Geospatial Layer Generation Pipeline")
    parser.add_argument("--scenario", default=None, help="Path to enhanced tactical JSON profile")
    parser.add_argument("--messages", default=None, help="Path to simulated SAPIENT sensor stream JSON")
    parser.add_argument("--location", default=None, help="Optional location name for resolving input paths (e.g., 'joensuu')")
    parser.add_argument("--outdir", default=OUTPUT_DIR, help="Output directory for generated GIS layers")
    parser.add_argument("--sample-rate", type=int, default=10, help="Downsampling rate step index for dense WKT strings")
    
    args = parser.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    # Resolve input paths for scenario and messages using the provided arguments and resolution logic  
    args.scenario = resolve_input(
    args.scenario,
    TACTICAL_DIR,
    "_tactical.json",
    args.location
    )

    args.messages = resolve_input(
        args.messages,
        MESSAGES_DIR,
        "_messages.json",
        args.location
    )

    if not args.scenario:
        raise FileNotFoundError(
        "Could not resolve tactical scenario file"
    )

    if not args.messages:
        raise FileNotFoundError(
         "Could not resolve messages file"
    )

    # Load the tactical environment profile and the simulated SAPIENT message stream
    try:
        with open(args.scenario, 'r', encoding='utf-8') as f:
            tactical_data = json.load(f)
    except Exception as e:
        print(f"[CRITICAL] Error parsing tactical environment profile: {e}")
        return

    try:
        with open(args.messages, 'r', encoding='utf-8') as f:
            messages_data = json.load(f)
    except Exception as e:
        print(f"[CRITICAL] Error parsing simulation streams: {e}")
        return

    # Generate and export GIS layers for targets, flight vectors, sensor network, and sensor detections with clear logging
    print("=" * 65)
    print(" Compiling GIS Layers for Export Pipeline...")
    print("=" * 65)
    export_targets(tactical_data, args.outdir)
    export_flight_vectors(tactical_data, args.outdir, args.sample_rate)
    export_sensor_network(tactical_data, args.outdir)
    export_sensor_detections(messages_data, args.outdir)
    print("=" * 65)
    print("All layers built and formatted perfectly.")

if __name__ == "__main__":
    main()