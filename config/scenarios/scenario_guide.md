# Scenario Configuration  Guide

Every simulation is defined by a central JSON scenario file. Below is a structured documentation guide detailing all configurable parameters:

## 1. `scenario_meta` (Metadata & Timeline Control)

Defines basic operational scenario parameters, update rates, and execution time structures.

- `name` (String): The descriptive title of the simulation.

- `start_time_iso` (String - ISO 8601): The absolute starting timestamp of the simulation (e.g., `"2026-11-15T02:45:00Z"`).

- `duration_seconds` (Integer): The complete runtime duration of the simulation in seconds.

- `time_step_seconds` (Integer): The spatial calculation step interval in seconds. Defines the granularity of the Ground Truth calculation engine.

```json
"scenario_meta": {
  "name": "Joensuu Multi-Vector Saturation Attack Scenario",
  "start_time_iso": "2026-11-15T02:45:00Z",
  "duration_seconds": 4500,
  "time_step_seconds": 20
}
```

## 2. targets (Defensive Critical Assets)

Configures localized infrastructure asset points that threats approach and target.

- `lat` (Float): Geodetic latitude coordinate ($[-90.0, 90.0]$) in decimal degrees.

- `lon` (Float): Geodetic longitude coordinate ($[-180.0, 180.0]$) in decimal degrees.

- `alt` (Float): The altitude of the asset in meters relative to mean sea level (MSL).

```json
"targets": {
  "POWER_PLANT": {
    "lat": 62.59481,
    "lon": 29.832561,
    "alt": 40.0
  }
}
```

## 3. threat_profiles (Offensive Mission Vectors)

Defines kinematic, scheduling, and classification profiles for offensive entities.

- `count` (Integer): Number of active entities to spawn sequentially along this vector.

- `speed_kmh` (Integer): Operational cruise speed of spawned entities in kilometers per hour.

- `alt_m` (Float): Operational cruising altitude (defined as Above-Ground-Level [AGL] when terrain refinement is active).

- `classification` (String): SAPIENT-compliant classification label (e.g., "UAV_Decoy", "UAV_Propeller_Kamikaze", "Personnel").

- `launch_delay_sec` (Integer): Time-offset delay in seconds before the first entity in this profile launches.

- `id_suffix` (String): Unique tracking text identifier appended to entity track IDs.

- `wkt_linestring` (String - WKT LINESTRING): The geographic routing line representing the planned flight vector, moving from the launch coordinates to the target.

```json
"threat_profiles": {
  "W2_KMS_PLANT": {
    "count": 10,
    "speed_kmh": 185,
    "alt_m": 60.0,
    "classification": "UAV_Propeller_Kamikaze",
    "launch_delay_sec": 60,
    "id_suffix": "PLANT",
    "wkt_linestring": "LINESTRING (30.6900 62.1510, 30.2000 62.3000, 29.832561 62.594810)"
  }
}
```

## 4. sensor_network (Defensive Sensors)

Positions and calibrates the physical constraints of defensive sensors.

- `id` (String): Unique hardware tag identifier of the sensor node.

- `type` (String): Sensor classification type (e.g., "RADAR_STRATEGIC", "RADAR_TACTICAL", "ACOUSTIC", "THERMAL_CAM", "VISUAL_CAM").

- `lat` (Float): Geodetic latitude coordinate of the static sensor node location.

- `lon` (Float): Geodetic longitude coordinate of the static sensor node location.

- `range_m` (Integer): The maximum physical detection range of the sensor in meters.

- `update_rate_sec` (Float): The update and SAPIENT message dispatch interval of this sensor in seconds.

```json
"sensor_network": [
  {
    "id": "FI-MIL-RAD-ONTTOLA-01",
    "type": "RADAR_TACTICAL",
    "lat": 62.6600,
    "lon": 29.6200,
    "range_m": 40000,
    "update_rate_sec": 12.0
  }
]
```

## 5. terrain_elevation_anchors (Surface Topology Calibrators)

Supplies geographic surface elevation markers that anchor the terrain interpolation engine.

- `name` (String): Descriptive geographic anchor name (e.g., lake surface, airfield).

- `lat` (Float): Geodetic latitude coordinate of the anchor point.

- `lon` (Float): Geodetic longitude coordinate of the anchor point.

- `elevation_msl` (Float): Known surface elevation in meters above mean sea level.

```json
"terrain_elevation_anchors": [
  {
    "name": "Onttola Airfield Flat Zone",
    "lat": 62.6620,
    "lon": 29.6110,
    "elevation_msl": 114.0
  }
]
```