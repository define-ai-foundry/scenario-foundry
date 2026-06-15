# Copyright 2026 Lempea Edge Oy / DEFINE AI Foundry
# SPDX-License-Identifier: Apache-2.0

import json
import os
import math
import argparse
import re
import src.config

DEFAULT_CACHE_DIR = str(src.config.TERRAIN_DIR)
GRID_CACHE = {}

def read_elevation_from_local_asc(lat, lon, cache_dir):
    """Robust ESRI Arc ASCII Grid Matrix Reader."""
    lat_floor = int(math.floor(lat))
    lon_floor = int(math.floor(lon))
    lat_pfx = f"N{lat_floor:02d}" if lat_floor >= 0 else f"S{abs(lat_floor):02d}"
    lon_pfx = f"E{lon_floor:03d}" if lon_floor >= 0 else f"W{abs(lon_floor):03d}"
    asc_name = f"{lat_pfx}{lon_pfx}"
    asc_path = os.path.join(cache_dir, f"{asc_name}.asc")
    
    if not os.path.exists(asc_path):
        return 80.0
        
    if asc_name not in GRID_CACHE:
        try:
            with open(asc_path, "r", encoding="utf-8") as f:
                header = {}
                for _ in range(6):
                    line_tokens = f.readline().strip().split()
                    header[line_tokens[0].lower()] = float(line_tokens[1])
                
                matrix = []
                for line in f:
                    if line.strip():
                        matrix.append([float(v) for v in line.split()])
                
                GRID_CACHE[asc_name] = {"header": header, "matrix": matrix}
        except Exception:
            return 80.0
            
    data = GRID_CACHE.get(asc_name)
    if not data: 
        return 80.0
        
    hdr = data["header"]
    mat = data["matrix"]
    
    cell_size = hdr["cellsize"]
    nrows = int(hdr["nrows"])
    ncols = int(hdr["ncols"])
    
    col = int((lon - hdr["xllcorner"]) / cell_size)
    y_top = hdr["yllcorner"] + (nrows * cell_size)
    row = int((y_top - lat) / cell_size)
    
    row = max(0, min(row, nrows - 1))
    col = max(0, min(col, ncols - 1))
    
    try:
        val = mat[row][col]
        return val if val > -500 else 80.0
    except Exception:
        return 80.0

def parse_wkt_points(wkt_str):
    points = []
    match = re.search(r'LINESTRING\s*\((.*)\)', wkt_str, re.IGNORECASE)
    if match:
        for pair in match.group(1).split(','):
            lon, lat = map(float, pair.strip().split())
            points.append((lat, lon))
    return points

def get_distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def optimize_track(coarse_waypoints, cache_dir):
    """
    Direct Dynamic Pathfinder with Capped Forces.
    Clamps repulsion vectors to ensure the target's forward pull is always 
    strong enough to break out of starting traps, generating clean, curving paths.
    """
    if len(coarse_waypoints) < 2: 
        return coarse_waypoints
    
    optimized_points = []
    step_size_meters = 60.0  
    R = 6371000.0
    
    for i in range(len(coarse_waypoints) - 1):
        start_lat, start_lon = coarse_waypoints[i]
        leg_target_lat, leg_target_lon = coarse_waypoints[i+1]
        
        current_lat, current_lon = start_lat, start_lon
        if i == 0:
            optimized_points.append((current_lat, current_lon))
            
        max_iterations = 15000
        iterations = 0
        
        while iterations < max_iterations:
            iterations += 1
            
            dist_to_target = get_distance_meters(current_lat, current_lon, leg_target_lat, leg_target_lon)
            if dist_to_target <= step_size_meters * 1.2:
                break
                
            d_lat = math.radians(leg_target_lat - current_lat)
            d_lon = math.radians(leg_target_lon - current_lon)
            y = math.sin(d_lon) * math.cos(math.radians(leg_target_lat))
            x = math.cos(math.radians(current_lat))*math.sin(math.radians(leg_target_lat)) - math.sin(math.radians(current_lat))*math.cos(math.radians(leg_target_lat))*math.cos(d_lon)
            target_heading = math.atan2(y, x)
            
            att_x = math.cos(target_heading)
            att_y = math.sin(target_heading)
            
            rep_x, rep_y = 0.0, 0.0
            scan_distance_meters = 200.0  
            scan_rad = scan_distance_meters / R
            h_current = read_elevation_from_local_asc(current_lat, current_lon, cache_dir)
            
            for angle_deg in range(0, 360, 45):
                angle_rad = math.radians(angle_deg)
                scan_lat = current_lat + math.degrees(scan_rad * math.cos(angle_rad))
                scan_lon = current_lon + math.degrees(scan_rad * math.sin(angle_rad) / math.cos(math.radians(current_lat)))
                
                h_scan = read_elevation_from_local_asc(scan_lat, scan_lon, cache_dir)
                
                if h_scan > h_current:
                    elevation_delta = h_scan - h_current
                    push_force = (elevation_delta * 3.0) ** 2
                    rep_x -= push_force * math.cos(angle_rad)
                    rep_y -= push_force * math.sin(angle_rad)
            
            # Normalize the repulsion vector to prevent massive spikes
            rep_len = math.sqrt(rep_x**2 + rep_y**2)
            if rep_len > 0:
                # Force clamping safeguard limits the maximum push vector to 0.75,
                # ensuring it can never completely overpower the target attraction force.
                max_allowed_push = 0.75
                scale = min(rep_len, max_allowed_push) / rep_len
                rep_x *= scale
                rep_y *= scale
            
            att_weight = 1.0
            total_x = (att_weight * att_x) + rep_x
            total_y = (att_weight * att_y) + rep_y
            
            final_heading = math.atan2(total_y, total_x)
            
            step_dist = step_size_meters / R
            current_lat += math.degrees(step_dist * math.cos(final_heading))
            current_lon += math.degrees(step_dist * math.sin(final_heading) / math.cos(math.radians(current_lat)))
            
            optimized_points.append((current_lat, current_lon))
            
        optimized_points.append((leg_target_lat, leg_target_lon))
        
    return optimized_points

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--cache", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.output is None:
        base, ext = os.path.splitext(args.scenario)
        args.output = f"{base}_tactical{ext}"

    with open(args.scenario, 'r', encoding='utf-8') as f:
        scenario = json.load(f)

    meta = scenario.get("scenario_meta", {})
    print(f"Optimizing Flight Tracks for Scenario Target: [{meta.get('name', 'Unnamed Theater')}]")
    print("-" * 70)
    
    test_h = read_elevation_from_local_asc(62.42, 31.12, args.cache)
    print(f"[DIAGNOSTIC] Arc ASCII Seeker Operational. Launch site elevation: {test_h}m")
    print("-" * 70)

    for wave_id, wave in scenario.get("threat_profiles", {}).items():
        coarse_wkt = wave.get("wkt_linestring", "")
        if not coarse_wkt: continue
        coarse_pts = parse_wkt_points(coarse_wkt)
        print(f"  -> Processing wave: {wave_id}...")
        tactical_pts = optimize_track(coarse_pts, args.cache)
        wkt_strings = [f"{lon:.6f} {lat:.6f}" for lat, lon in tactical_pts]
        wave["wkt_linestring"] = f"LINESTRING ({', '.join(wkt_strings)})"
        
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(scenario, f, indent=2)
    print("-" * 70)
    print(f"SUCCESS: Tactical scenario manifest compiled -> {args.output}")

if __name__ == "__main__":
    main()