# Copyright 2026 Lempea Edge Oy / DEFINE AI Foundry
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import math
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from scenario_foundry import config, constants
from scenario_foundry.rng import seed_all
from scenario_foundry.sapient import builder
from scenario_foundry.sapient.builder import (
    add_classification,
    make_location,
    make_range_bearing,
    make_velocity,
)


# --- GEOSPATIAL & CELESTIAL MATH LIBRARY ---
def haversine_dist(lat1, lon1, lat2, lon2):
    R = constants.EARTH_RADIUS_M
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calc_bearing(lat1, lon1, lat2, lon2):
    lat1, lat2, lon1, lon2 = map(math.radians, [lat1, lat2, lon1, lon2])
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def add_metric_noise_to_wgs84(lat, lon, error_north_m, error_east_m):
    R = constants.EARTH_RADIUS_M
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
    sin_sol = math.sin(lat_rad) * math.sin(dec_rad) + math.cos(lat_rad) * math.cos(
        dec_rad
    ) * math.cos(ha_rad)
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_sol))))


def make_wgs84_location(lat, lon, alt):
    return {
        "x": round(lon, 6),
        "y": round(lat, 6),
        "z": round(alt, 1),
        "coordinateSystem": constants.SAP_COORD_LAT_LNG_DEG_M,
        "datum": constants.SAP_DATUM_WGS84,
    }


# --- UPGRADED: HIGH-PERFORMANCE MEMORY CACHED ARC ASCII GRID ENGINE ---
SIM_GRID_CACHE = {}


def read_elevation_from_local_asc(lat, lon, cache_dir=str(config.TERRAIN_DIR)):
    lat_floor = math.floor(lat)
    lon_floor = math.floor(lon)
    lat_pfx = f"N{lat_floor:02d}" if lat_floor >= 0 else f"S{abs(lat_floor):02d}"
    lon_pfx = f"E{lon_floor:03d}" if lon_floor >= 0 else f"W{abs(lon_floor):03d}"
    asc_name = f"{lat_pfx}{lon_pfx}"
    asc_path = os.path.join(cache_dir, f"{asc_name}.asc")

    if not os.path.exists(asc_path):
        return None

    if asc_name not in SIM_GRID_CACHE:
        try:
            with open(asc_path, encoding="utf-8") as f:
                header = {}
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

    col = int((lon - hdr["xllcorner"]) / cell_size)
    y_top = hdr["yllcorner"] + (nrows * cell_size)
    row = int((y_top - lat) / cell_size)

    row = max(0, min(row, nrows - 1))
    col = max(0, min(col, ncols - 1))

    try:
        val = mat[row][col]
        return val if val > constants.ELEVATION_NODATA_THRESHOLD_M else None
    except Exception:
        return None


def get_terrain_elevation(lat, lon, scenario_config):
    raster_alt = read_elevation_from_local_asc(lat, lon, cache_dir=str(config.TERRAIN_DIR))
    if raster_alt is not None:
        return raster_alt

    anchors = scenario_config.get("terrain_elevation_anchors", [])
    if not anchors:
        return constants.DEFAULT_TERRAIN_ELEVATION_M
    total_weight, weighted_elevation = 0.0, 0.0
    for anchor in anchors:
        dist = max(haversine_dist(lat, lon, anchor["lat"], anchor["lon"]), 1.0)
        weight = 1.0 / (dist**2)
        total_weight += weight
        weighted_elevation += anchor["elevation_msl"] * weight
    return weighted_elevation / total_weight


def parse_wkt(wkt_str):
    points = []
    match = re.search(r"LINESTRING\s*\((.*)\)", wkt_str, re.IGNORECASE)
    if match:
        for pair in match.group(1).split(","):
            lon, lat = pair.strip().split()
            points.append({"lat": float(lat), "lon": float(lon)})
    return points


def get_position(waypoints, distance_traveled):
    accum_dist = 0.0
    for i in range(len(waypoints) - 1):
        w1, w2 = waypoints[i], waypoints[i + 1]
        d = haversine_dist(w1["lat"], w1["lon"], w2["lat"], w2["lon"])
        if accum_dist + d >= distance_traveled:
            ratio = (distance_traveled - accum_dist) / d
            c_lat = w1["lat"] + ratio * (w2["lat"] - w1["lat"])
            c_lon = w1["lon"] + ratio * (w2["lon"] - w1["lon"])
            bearing = calc_bearing(c_lat, c_lon, w2["lat"], w2["lon"])
            is_final_leg = i == len(waypoints) - 2
            return c_lat, c_lon, bearing, ratio, is_final_leg, False
        accum_dist += d
    return waypoints[-1]["lat"], waypoints[-1]["lon"], 0.0, 1.0, True, True


def calculate_dynamic_confidence(dist, max_range, sensor_type):
    proximity_ratio = max(0.0, min(1.0, 1.0 - (dist / max_range)))
    scintillation = random.uniform(-0.03, 0.03)
    if constants.SensorType.is_radar(sensor_type):
        base_conf = 0.45 + (0.50 * proximity_ratio)
    elif sensor_type in [constants.SensorType.THERMAL_CAM, constants.SensorType.VISUAL_CAM]:
        base_conf = 0.30 + (0.68 * (proximity_ratio**2))
    elif sensor_type == constants.SensorType.ACOUSTIC:
        base_conf = 0.35 + (0.50 * proximity_ratio)
    else:
        base_conf = 0.50 + (0.45 * proximity_ratio)
    return round(max(0.10, min(0.99, base_conf + scintillation)), 2)


# --- SCENARIO MODEL ---
@dataclass(frozen=True)
class ThreatWave:
    """A parsed threat-profile entry: kinematics, classification, and its flight path."""

    wave_id: str
    id_suffix: str
    count: int
    speed_kmh: float
    alt_m: float
    classification: str
    launch_delay_sec: float
    waypoints: list

    @classmethod
    def from_config(cls, wave_id, cfg):
        """Build a ThreatWave from a threat_profiles config entry, parsing its WKT linestring."""
        return cls(
            wave_id=wave_id,
            id_suffix=cfg["id_suffix"],
            count=cfg["count"],
            speed_kmh=cfg["speed_kmh"],
            alt_m=cfg["alt_m"],
            classification=cfg["classification"],
            launch_delay_sec=cfg["launch_delay_sec"],
            waypoints=parse_wkt(cfg["wkt_linestring"]),
        )

    @property
    def prefix(self):
        """Two-letter objectId prefix derived from the wave id."""
        return self.wave_id[:2]


@dataclass(frozen=True)
class Sensor:
    """A parsed sensor-network entry: identity, position, and detection range."""

    id: str
    type: str
    lat: float
    lon: float
    range_m: float
    update_rate_sec: float | None = None

    @classmethod
    def from_config(cls, cfg):
        """Build a Sensor from a sensor_network config entry."""
        return cls(
            id=cfg["id"],
            type=cfg["type"],
            lat=cfg["lat"],
            lon=cfg["lon"],
            range_m=cfg["range_m"],
            update_rate_sec=cfg.get("update_rate_sec"),
        )

    @property
    def code(self):
        """Short sensor code derived from the trailing id digit (fallback '1')."""
        return f"A-0{self.id[-1:] if self.id[-1:].isdigit() else '1'}"


# --- DETECTION REPORT ASSEMBLY ---
class DetectionReportBuilder:
    """Builds the sensor-type-specific BSI Flex 335 payload for one detection."""

    def __init__(
        self,
        sensor,
        wave,
        thresholds,
        *,
        lat,
        lon,
        noisy_lat,
        noisy_lon,
        absolute_altitude_msl,
        dist,
        mps,
        brg,
        is_diving,
        calculated_conf,
        current_sim_time,
    ):
        self.sensor = sensor
        self.wave = wave
        self.thresholds = thresholds
        self.lat = lat
        self.lon = lon
        self.noisy_lat = noisy_lat
        self.noisy_lon = noisy_lon
        self.absolute_altitude_msl = absolute_altitude_msl
        self.dist = dist
        self.mps = mps
        self.brg = brg
        self.is_diving = is_diving
        self.calculated_conf = calculated_conf
        self.current_sim_time = current_sim_time

    def build(self):
        """Return (report, extra_attributes): the DetectionReport proto plus non-ICD attributes."""
        sensor, wave, thresholds = self.sensor, self.wave, self.thresholds

        # 1. Core report: strict ICD fields set directly on the proto.
        report = builder.DetectionReport(state=constants.DETECTION_STATE_ACTIVE)
        add_classification(report, wave.classification.upper(), self.calculated_conf)

        pfx = wave.prefix
        s_code = sensor.code

        # Custom simulation attributes live outside the strict proto schema.
        extra_attributes = {}

        # 2. Attach the sensor-type-specific payload to the proto.
        switch_m = thresholds["radar_swarm_indicator_switch_m"]
        if constants.SensorType.is_radar(sensor.type) and self.dist > switch_m:
            report.object_id = f"{s_code}-SWM-{pfx}_{wave.id_suffix}"
            report.location.CopyFrom(
                make_location(self.noisy_lat, self.noisy_lon, self.absolute_altitude_msl)
            )
            extra_attributes["measuredAttributes"] = {"estimatedSwarmCount": wave.count}
            if self.is_diving:
                extra_attributes["measuredAttributes"]["tacticalState"] = (
                    constants.TACTICAL_STATE_TERMINAL_DIVE
                )

        elif (
            sensor.type in [constants.SensorType.MICRO_DOPPLER, constants.SensorType.RADAR_TACTICAL]
            and self.dist <= switch_m
        ):
            report.object_id = f"{s_code}-IND-{pfx}_{wave.id_suffix}_0{wave.count - 2}"
            report.location.CopyFrom(
                make_location(self.noisy_lat, self.noisy_lon, self.absolute_altitude_msl)
            )
            v_up = -15.0 if self.is_diving else 0.0

            east = self.mps * math.sin(math.radians(self.brg))
            north = self.mps * math.cos(math.radians(self.brg))

            report.enu_velocity.CopyFrom(make_velocity(east, north, v_up))

            if sensor.type == constants.SensorType.MICRO_DOPPLER:
                extra_attributes["measuredAttributes"] = {
                    "microDopplerRotorSpeedRps": constants.ROTOR_SPEED_FPV_RPS
                    if constants.CLASSIFICATION_FPV_MARKER in wave.classification
                    else constants.ROTOR_SPEED_DEFAULT_RPS
                }
                if self.is_diving:
                    extra_attributes["measuredAttributes"]["maneuverState"] = (
                        constants.MANEUVER_STATE_HIGH_G_DIVE
                    )

        elif sensor.type == constants.SensorType.ACOUSTIC:
            report.object_id = f"ACU-{s_code}_{pfx}_{wave.id_suffix}"
            noisy_bearing = (
                calc_bearing(sensor.lat, sensor.lon, self.lat, self.lon) + random.gauss(0, 3.5)
            ) % 360

            report.range_bearing.CopyFrom(make_range_bearing(noisy_bearing, self.dist))

        elif (
            sensor.type == constants.SensorType.THERMAL_CAM
            and self.dist <= thresholds["thermal_cam_max_range_m"]
        ):
            report.object_id = f"CAM-{s_code}_{pfx}_{wave.id_suffix}"
            report.location.CopyFrom(
                make_location(self.noisy_lat, self.noisy_lon, self.absolute_altitude_msl)
            )
            extra_attributes["opticalAttributes"] = {
                "spectrumChannel": constants.SPECTRUM_LWIR_THERMAL,
                "visualConfirmation": constants.VISUAL_CONFIRMATION_POSITIVE,
                "targetThermalIntensity": constants.THERMAL_INTENSITY_HIGH,
            }

        elif (
            sensor.type == constants.SensorType.VISUAL_CAM
            and self.dist <= thresholds["visual_cam_max_range_m"]
        ):
            solar_elevation = calculate_solar_elevation(
                sensor.lat, sensor.lon, self.current_sim_time
            )
            report.object_id = f"CAM-{s_code}_{pfx}_{wave.id_suffix}"
            report.location.CopyFrom(
                make_location(self.noisy_lat, self.noisy_lon, self.absolute_altitude_msl)
            )
            if solar_elevation > thresholds["civil_twilight_elevation_deg"]:
                extra_attributes["opticalAttributes"] = {
                    "spectrumChannel": constants.SPECTRUM_VISIBLE_COLOR,
                    "visualConfirmation": constants.VISUAL_CONFIRMATION_POSITIVE,
                    "illuminationStatus": constants.ILLUMINATION_OPTIMAL,
                }
            else:
                extra_attributes["opticalAttributes"] = {
                    "spectrumChannel": constants.SPECTRUM_VISIBLE_COLOR,
                    "visualConfirmation": constants.VISUAL_CONFIRMATION_UNCONFIRMED,
                    "illuminationStatus": constants.ILLUMINATION_POOR_BLIND,
                }

        return report, extra_attributes


def compute_noisy_position(sensor, lat, lon, dist):
    """Apply sensor-type-specific Gaussian position noise (radar/optical/micro-doppler)."""
    if constants.SensorType.is_radar(sensor.type):
        sigma_meters = 5.0 + (30.0 * (dist / sensor.range_m))
        return add_metric_noise_to_wgs84(
            lat, lon, random.gauss(0, sigma_meters), random.gauss(0, sigma_meters)
        )
    elif sensor.type in [constants.SensorType.THERMAL_CAM, constants.SensorType.VISUAL_CAM]:
        sigma_meters = 2.0 + (15.0 * ((dist / sensor.range_m) ** 2))
        return add_metric_noise_to_wgs84(
            lat, lon, random.gauss(0, sigma_meters), random.gauss(0, sigma_meters)
        )
    elif sensor.type == constants.SensorType.MICRO_DOPPLER:
        sigma_m = random.gauss(0, 1.5)
        return add_metric_noise_to_wgs84(lat, lon, sigma_m, sigma_m)
    return lat, lon


def serialize_and_wrap(report, extra_attributes, sensor, ts_str, step):
    """Serialize the DetectionReport proto and wrap it in a top-level sapientMessage."""
    try:
        detection_report = builder.serialize_report(report, extra_attributes)

        # Manually stitch into the required top-level SAPIENT JSON structure
        return {
            "sapientMessage": {
                "header": {
                    "icdVersion": constants.ICD_VERSION,
                    "timestamp": ts_str,
                    "sourceNode": {
                        "nodeId": str(sensor.id),
                        "type": constants.NODE_TYPE_CHILD,
                    },
                },
                "detectionReport": detection_report,
            }
        }
    except Exception as e:
        print(f"CRITICAL PROTOC SERIALIZATION ERROR at step {step}: {e}")
        raise


def generate_detection_for_sensor(
    sensor, wave, adjusted_elapsed, current_sim_time, ts_str, scenario, thresholds, step
):
    """Compute one sensor/wave detection entry for the current step, or None if a guard rejects it."""
    if adjusted_elapsed < wave.launch_delay_sec:
        return None

    mps = (wave.speed_kmh * 1000) / 3600
    dist_traveled = mps * (adjusted_elapsed - wave.launch_delay_sec)
    lat, lon, brg, ratio, is_final_leg, impacted = get_position(wave.waypoints, dist_traveled)
    if impacted:
        return None

    dist = haversine_dist(sensor.lat, sensor.lon, lat, lon)
    if dist > sensor.range_m:
        return None

    ground_height_msl = get_terrain_elevation(lat, lon, scenario)
    current_agl = wave.alt_m
    if is_final_leg and wave.classification != constants.CLASSIFICATION_DECOY:
        current_agl = wave.alt_m * (1.0 - ratio)

    absolute_altitude_msl = ground_height_msl + current_agl
    if (
        sensor.type == constants.SensorType.RADAR_STRATEGIC
        and absolute_altitude_msl < thresholds["radar_strategic_min_altitude_m"]
    ):
        return None

    noisy_lat, noisy_lon = compute_noisy_position(sensor, lat, lon, dist)

    calculated_conf = calculate_dynamic_confidence(dist, sensor.range_m, sensor.type)
    if sensor.type == constants.SensorType.VISUAL_CAM:
        solar_elevation = calculate_solar_elevation(sensor.lat, sensor.lon, current_sim_time)
        if solar_elevation <= thresholds["civil_twilight_elevation_deg"]:
            calculated_conf = 0.12

    is_diving = is_final_leg and wave.classification != constants.CLASSIFICATION_DECOY

    report_builder = DetectionReportBuilder(
        sensor,
        wave,
        thresholds,
        lat=lat,
        lon=lon,
        noisy_lat=noisy_lat,
        noisy_lon=noisy_lon,
        absolute_altitude_msl=absolute_altitude_msl,
        dist=dist,
        mps=mps,
        brg=brg,
        is_diving=is_diving,
        calculated_conf=calculated_conf,
        current_sim_time=current_sim_time,
    )
    report, extra_attributes = report_builder.build()
    return serialize_and_wrap(report, extra_attributes, sensor, ts_str, step)


def generate_detections_for_sensor(sensor, waves, scenario, meta, thresholds, start_dt, duration):
    """Step through a sensor's scan schedule, collecting one entry per wave that passes guards."""
    entries = []
    scan_interval = (
        sensor.update_rate_sec
        if sensor.update_rate_sec is not None
        else meta.get("time_step_seconds", 20.0)
    )
    steps = int(duration / scan_interval)

    for step in range(steps + 1):
        elapsed_time = step * scan_interval
        jitter_sec = random.uniform(-0.05, 0.05)
        adjusted_elapsed = max(0.0, elapsed_time + jitter_sec)

        current_sim_time = start_dt + timedelta(seconds=adjusted_elapsed)
        ts_str = current_sim_time.isoformat() + "Z"

        for wave in waves:
            entry = generate_detection_for_sensor(
                sensor, wave, adjusted_elapsed, current_sim_time, ts_str, scenario, thresholds, step
            )
            if entry is not None:
                entries.append(entry)

    return entries


# --- CLI / SCENARIO LOADING ---
def parse_args(argv=None):
    """Parse CLI args: --scenario (required), --output, --seed."""
    parser = argparse.ArgumentParser(
        description="Synchronized Plaintext ASC SAPIENT Telemetry Generator"
    )
    parser.add_argument(
        "--scenario", required=True, help="Path to tactical optimized scenario json file"
    )
    parser.add_argument(
        "--output", default=str(config.GENERATED_DIR), help="Output telemetry log file path"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Integer RNG seed for reproducible output. Omit for non-deterministic runs.",
    )
    return parser.parse_args(argv)


def load_scenario(path):
    """Load and return the scenario JSON, or print an error and return None if missing."""
    if not os.path.exists(path):
        print(f"ERROR: Target tactical scenario file '{path}' not found.")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def prepare_threat_waves(scenario):
    """Parse threat_profiles into ThreatWave objects, preserving config order."""
    return [
        ThreatWave.from_config(wave_id, wave_cfg)
        for wave_id, wave_cfg in scenario["threat_profiles"].items()
    ]


# --- MAIN GENERATION ENGINE ---
def main():
    """CLI entrypoint: load a scenario, simulate detections, write the sorted SAPIENT JSON log."""
    args = parse_args()

    if args.seed is not None:
        seed_all(args.seed)

    scenario = load_scenario(args.scenario)
    if scenario is None:
        return

    meta = scenario["scenario_meta"]
    thresholds = constants.resolve_detection_thresholds(scenario)
    start_dt = datetime.fromisoformat(meta["start_time_iso"].replace("Z", ""))
    duration = meta["duration_seconds"]

    print(f"Executing Synchronized Generation Engine Theater: {meta['name']}")

    threat_waves = prepare_threat_waves(scenario)
    sensors = [Sensor.from_config(cfg) for cfg in scenario["sensor_network"]]

    json_log = []
    for sensor in sensors:
        json_log.extend(
            generate_detections_for_sensor(
                sensor, threat_waves, scenario, meta, thresholds, start_dt, duration
            )
        )

    json_log.sort(key=lambda x: x["sapientMessage"]["header"]["timestamp"])

    os.makedirs(
        os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True
    )
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(json_log, f, indent=2)
    print(f"SUCCESS: Synchronized generation payload metrics compiled flawlessly -> {args.output}")


if __name__ == "__main__":
    main()
