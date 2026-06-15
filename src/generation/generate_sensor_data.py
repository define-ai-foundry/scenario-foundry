# Copyright 2026 Lempea Edge Oy / DEFINE AI Foundry
# SPDX-License-Identifier: Apache-2.0

import json
import math
import os
import re
import argparse
from datetime import datetime, timedelta
import random
import src.config

# --- GEOSPATIAL & CELESTIAL MATH LIBRARY ---
def haversine_dist(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def calc_bearing(lat1, lon1, lat2, lon2):
    lat1, lat2, lon1, lon2 = map(math.radians, [lat1, lat2, lon1, lon2])
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def add_metric_noise_to_wgs84(lat, lon, error_north_m, error_east_m):
    R = 6371000.0
    delta_lat = (error_north_m / R) * (180.0 / math.pi)
    delta_lon = (error_east_m / (R * math.cos(math.radians(lat)))) * (180.0 / math.pi)
    return lat + delta_lat, lon + delta_lon

def calculate_solar_elevation(lat, lon, dt):
    day_of_year = dt.timetuple().tm_yday
    hour_utc = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    declination = 23.45 * math.sin(math.radians((360 / 365) * (day_of_year - 80)))
    b = math.radians((360 / 364) * (day_of_year - 81))
    eq_of_time = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
    local_solar_time = hour_utc * 60.0 + eq_of_time + (4.0 * lon)
    hour_angle = (local_solar_time - 720.0) / 4.0
    
    lat_rad, dec_rad, ha_rad = map(math.radians, [lat, declination, hour_angle])
    sin_sol = math.sin(lat_rad) * math.sin(dec_rad) + math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad)
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_sol))))

# --- UPGRADED: HIGH-PERFORMANCE MEMORY CACHED ARC ASCII GRID ENGINE ---
SIM_GRID_CACHE = {}

def read_elevation_from_local_asc(lat, lon, cache_dir=str(src.config.TERRAIN_DIR)):
    """
    High-Performance Plaintext Arc ASCII Grid Parser.
    Keeps the generation engine 100% offline and perfectly aligned with optimize_vectors.py
    """
    lat_floor = int(math.floor(lat))
    lon_floor = int(math.floor(lon))
    lat_pfx = f"N{lat_floor:02d}" if lat_floor >= 0 else f"S{abs(lat_floor):02d}"
    lon_pfx = f"E{lon_floor:03d}" if lon_floor >= 0 else f"W{abs(lon_floor):03d}"
    asc_name = f"{lat_pfx}{lon_pfx}"
    asc_path = os.path.join(cache_dir, f"{asc_name}.asc")
    
    if not os.path.exists(asc_path):
        return None
        
    # Ingest file contents into memory on first call to maximize step loop performance
    if asc_name not in SIM_GRID_CACHE:
        try:
            with open(asc_path, "r", encoding="utf-8") as f:
                header = {}
                # Parse standard ESRI Arc ASCII 6-line metadata blocks
                for _ in range(6):
                    line_tokens = f.readline().strip().split()
                    header[line_tokens[0].lower()] = float(line_tokens[1])
                
                matrix = []
                for line in f:
                    if line.strip():
                        matrix.append([float(v) for v in line.split()])
                
                SIM_GRID_CACHE[asc_name] = {"header": header, "matrix": matrix}
        except Exception:
            return None
            
    data = SIM_GRID_CACHE.get(asc_name)
    if not data: 
        return None
        
    hdr = data["header"]
    mat = data["matrix"]
    
    cell_size = hdr["cellsize"]
    nrows = int(hdr["nrows"])
    ncols = int(hdr["ncols"])
    
    # Calculate column index relative to Western edge
    col = int((lon - hdr["xllcorner"]) / cell_size)
    
    # Correct North-to-South row index calculation matching ESRI ASCII specifications
    y_top = hdr["yllcorner"] + (nrows * cell_size)
    row = int((y_top - lat) / cell_size)
    
    # Secure array boundaries via clamp safety nets
    row = max(0, min(row, nrows - 1))
    col = max(0, min(col, ncols - 1))
    
    try:
        val = mat[row][col]
        return val if val > -500 else None
    except Exception:
        return None

def get_terrain_elevation(lat, lon, scenario_config):
    """
    100% OFFLINE HYBRID ELEVATION PIPELINE:
    Samples verified plaintext ASCII data grids from local cache.
    If files are missing, falls back to local Inverse Distance Weighting (IDW) anchors.
    """
    raster_alt = read_elevation_from_local_asc(lat, lon, cache_dir=str(src.config.TERRAIN_DIR))
    if raster_alt is not None:
        return raster_alt

    # Fallback Mode: IDW Mathematical Matrix
    anchors = scenario_config.get("terrain_elevation_anchors", [])
    if not anchors: return 80.0
    total_weight, weighted_elevation = 0.0, 0.0
    for anchor in anchors:
        dist = max(haversine_dist(lat, lon, anchor["lat"], anchor["lon"]), 1.0)
        weight = 1.0 / (dist ** 2)
        total_weight += weight
        weighted_elevation += anchor["elevation_msl"] * weight
    return weighted_elevation / total_weight

# --- TELEMETRY & SIGNAL PROCESSING ---
def parse_wkt(wkt_str):
    points = []
    match = re.search(r'LINESTRING\s*\((.*)\)', wkt_str, re.IGNORECASE)
    if match:
        for pair in match.group(1).split(','):
            lon, lat = pair.strip().split()
            points.append({"lat": float(lat), "lon": float(lon)})
    return points

def get_position(waypoints, distance_traveled):
    accum_dist = 0.0
    for i in range(len(waypoints) - 1):
        w1, w2 = waypoints[i], waypoints[i+1]
        d = haversine_dist(w1["lat"], w1["lon"], w2["lat"], w2["lon"])
        if accum_dist + d >= distance_traveled:
            ratio = (distance_traveled - accum_dist) / d
            c_lat = w1["lat"] + ratio * (w2["lat"] - w1["lat"])
            c_lon = w1["lon"] + ratio * (w2["lon"] - w1["lon"])
            bearing = calc_bearing(c_lat, c_lon, w2["lat"], w2["lon"])
            is_final_leg = (i == len(waypoints) - 2)
            return c_lat, c_lon, bearing, ratio, is_final_leg, False
        accum_dist += d
    return waypoints[-1]["lat"], waypoints[-1]["lon"], 0.0, 1.0, True, True

def calculate_dynamic_confidence(dist, max_range, sensor_type):
    proximity_ratio = max(0.0, min(1.0, 1.0 - (dist / max_range)))
    scintillation = random.uniform(-0.03, 0.03)
    if "RADAR" in sensor_type:
        base_conf = 0.45 + (0.50 * proximity_ratio)
    elif sensor_type in ["THERMAL_CAM", "VISUAL_CAM"]:
        base_conf = 0.30 + (0.68 * (proximity_ratio ** 2))
    elif sensor_type == "ACOUSTIC":
        base_conf = 0.35 + (0.50 * proximity_ratio)
    else:
        base_conf = 0.50 + (0.45 * proximity_ratio)
    return round(max(0.10, min(0.99, base_conf + scintillation)), 2)

# --- MAIN GENEATION ENGINE ---
def main():
    parser = argparse.ArgumentParser(description="Synchronized Plaintext ASC SAPIENT Telemetry Generator")
    parser.add_argument("--scenario", required=True, help="Path to tactical optimized scenario json file")
    parser.add_argument("--output", default=str(src.config.GENERATED_DIR), help="Output telemetry log file path")
    args = parser.parse_args()

    if not os.path.exists(args.scenario):
        print(f"ERROR: Target tactical scenario file '{args.scenario}' not found.")
        return

    with open(args.scenario, 'r', encoding='utf-8') as f:
        scenario = json.load(f)

    meta = scenario["scenario_meta"]
    start_dt = datetime.fromisoformat(meta["start_time_iso"].replace("Z", ""))
    duration = meta["duration_seconds"]

    print(f"Executing Synchronized Generation Engine Theater: {meta['name']}")
    
    threat_waves = {}
    for wave_id, config in scenario["threat_profiles"].items():
        config["waypoints"] = parse_wkt(config["wkt_linestring"])
        threat_waves[wave_id] = config

    json_log = []

    for sens in scenario["sensor_network"]:
        scan_interval = sens.get("update_rate_sec", meta.get("time_step_seconds", 20.0))
        steps = int(duration / scan_interval)
        
        for step in range(steps + 1):
            elapsed_time = step * scan_interval
            jitter_sec = random.uniform(-0.05, 0.05)
            adjusted_elapsed = max(0.0, elapsed_time + jitter_sec)
            
            current_sim_time = start_dt + timedelta(seconds=adjusted_elapsed)
            ts_str = current_sim_time.isoformat() + "Z"
            
            for wave_id, wave in threat_waves.items():
                if adjusted_elapsed < wave["launch_delay_sec"]: continue
                
                mps = (wave["speed_kmh"] * 1000) / 3600
                dist_traveled = mps * (adjusted_elapsed - wave["launch_delay_sec"])
                lat, lon, brg, ratio, is_final_leg, impacted = get_position(wave["waypoints"], dist_traveled)
                if impacted: continue
                
                dist = haversine_dist(sens["lat"], sens["lon"], lat, lon)
                if dist > sens["range_m"]: continue
                
                # Resolves natively via cached plaintext .asc row matrix elements
                ground_height_msl = get_terrain_elevation(lat, lon, scenario)
                current_agl = wave["alt_m"]
                if is_final_leg and wave["classification"] != "UAV_Decoy":
                    current_agl = wave["alt_m"] * (1.0 - ratio)
                
                absolute_altitude_msl = ground_height_msl + current_agl
                if sens["type"] == "RADAR_STRATEGIC" and absolute_altitude_msl < 100: continue
                
                # Apply geodetic track logging noise
                noisy_lat, noisy_lon = lat, lon
                if "RADAR" in sens["type"]:
                    sigma_meters = 5.0 + (30.0 * (dist / sens["range_m"]))
                    noisy_lat, noisy_lon = add_metric_noise_to_wgs84(lat, lon, random.gauss(0, sigma_meters), random.gauss(0, sigma_meters))
                elif sens["type"] in ["THERMAL_CAM", "VISUAL_CAM"]:
                    sigma_meters = 2.0 + (15.0 * ((dist / sens["range_m"]) ** 2))
                    noisy_lat, noisy_lon = add_metric_noise_to_wgs84(lat, lon, random.gauss(0, sigma_meters), random.gauss(0, sigma_meters))
                elif sens["type"] == "MICRO_DOPPLER":
                    sigma_m = random.gauss(0, 1.5)
                    noisy_lat, noisy_lon = add_metric_noise_to_wgs84(lat, lon, sigma_m, sigma_m)

                calculated_conf = calculate_dynamic_confidence(dist, sens["range_m"], sens["type"])
                if sens["type"] == "VISUAL_CAM":
                    solar_elevation = calculate_solar_elevation(sens["lat"], sens["lon"], current_sim_time)
                    if solar_elevation <= -6.0: calculated_conf = 0.12

                msg = {
                    "sapientMessage": {
                        "header": {"timestamp": ts_str, "nodeId": sens["id"], "messageType": "DetectionReport"},
                        "detectionReport": {"state": "Active", "classificationList": [{"type": wave["classification"], "confidence": calculated_conf}]}
                    }
                }
                rep = msg["sapientMessage"]["detectionReport"]
                s_code = f"A-0{sens['id'][-1:] if sens['id'][-1:].isdigit() else '1'}"
                pfx = wave_id[:2]
                is_diving = (is_final_leg and wave["classification"] != "UAV_Decoy")

                if "RADAR" in sens["type"] and dist > 8000:
                    rep["trackId"] = f"{s_code}-SWM-{pfx}_{wave['id_suffix']}"
                    rep["locationList"] = {"coordinateSystem": "WGS84", "location": {"latitude": round(noisy_lat, 5), "longitude": round(noisy_lon, 5), "elevation": round(absolute_altitude_msl, 1)}}
                    rep["measuredAttributes"] = {"estimatedSwarmCount": wave["count"]}
                    if is_diving: rep["measuredAttributes"]["tacticalState"] = "Terminal_Dive"
                    
                elif sens["type"] in ["MICRO_DOPPLER", "RADAR_TACTICAL"] and dist <= 8000:
                    rep["trackId"] = f"{s_code}-IND-{pfx}_{wave['id_suffix']}_0{wave['count'] - 2}"
                    rep["locationList"] = {"coordinateSystem": "WGS84", "location": {"latitude": round(noisy_lat, 6), "longitude": round(noisy_lon, 6), "elevation": round(absolute_altitude_msl, 1)}}
                    v_up = -15.0 if is_diving else 0.0
                    rep["velocity"] = {"east": round(mps * math.sin(math.radians(brg)), 1), "north": round(mps * math.cos(math.radians(brg)), 1), "up": v_up}
                    if sens["type"] == "MICRO_DOPPLER":
                        rep["measuredAttributes"] = {"microDopplerRotorSpeedRps": 220.0 if "FPV" in wave["classification"] else 75.0}
                        if is_diving: rep["measuredAttributes"]["maneuverState"] = "High_G_Dive"
                        
                elif sens["type"] == "ACOUSTIC":
                    rep["trackId"] = f"ACU-{s_code}_{pfx}_{wave['id_suffix']}"
                    noisy_bearing = (calc_bearing(sens["lat"], sens["lon"], lat, lon) + random.gauss(0, 3.5)) % 360
                    rep["bearingOnlyLocation"] = {"coordinateSystem": "WGS84", "sensorLatitude": sens["lat"], "sensorLongitude": sens["lon"], "azimuthDegrees": round(noisy_bearing, 1)}
                    
                elif sens["type"] == "THERMAL_CAM" and dist <= 4000:
                    rep["trackId"] = f"CAM-{s_code}_{pfx}_{wave['id_suffix']}"
                    rep["locationList"] = {"coordinateSystem": "WGS84", "location": {"latitude": round(noisy_lat, 6), "longitude": round(noisy_lon, 6), "elevation": round(absolute_altitude_msl, 1)}}
                    rep["opticalAttributes"] = {"spectrumChannel": "LWIR_Thermal", "visualConfirmation": "Positive", "targetThermalIntensity": "High"}
                
                elif sens["type"] == "VISUAL_CAM" and dist <= 3000:
                    solar_elevation = calculate_solar_elevation(sens["lat"], sens["lon"], current_sim_time)
                    rep["trackId"] = f"CAM-{s_code}_{pfx}_{wave['id_suffix']}"
                    rep["locationList"] = {"coordinateSystem": "WGS84", "location": {"latitude": round(noisy_lat, 6), "longitude": round(noisy_lon, 6), "elevation": round(absolute_altitude_msl, 1)}}
                    if solar_elevation > -6.0:
                        rep["opticalAttributes"] = {"spectrumChannel": "Visible_Color", "visualConfirmation": "Positive", "illuminationStatus": "Optimal"}
                    else:
                        rep["opticalAttributes"] = {"spectrumChannel": "Visible_Color", "visualConfirmation": "Unconfirmed", "illuminationStatus": "Poor_Blind"}

                json_log.append(msg)

    json_log.sort(key=lambda x: x["sapientMessage"]["header"]["timestamp"])

    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(json_log, f, indent=2)
    print(f"SUCCESS: Synchronized generation payload metrics compiled flawlessly -> {args.output}")

if __name__ == "__main__":
    main()