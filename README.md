# SAPIENT Synthetic Data Generator (SDG)

The SAPIENT Synthetic Data Generator (SDG) is a configurable, data-driven simulation framework for generating realistic multi-sensor surveillance and tracking data across arbitrary operational scenarios.

By combining user-defined environments, simulated entities, and advanced sensor error models, SDG produces synthetic, SAPIENT-compatible sensor streams that emulate how real-world surveillance systems detect, track, classify, and report activity.

High-quality multi-sensor datasets are often difficult to obtain due to cost, operational constraints, limited availability, or sensitivity of real-world deployments. SDG addresses this challenge by enabling rapid generation of realistic synthetic datasets without dependence on specific geographic locations, sensor hardware, or live operational data.

The generated data can be used to develop, test, and validate:

- Command-and-control (C2) systems
- Sensor fusion pipelines
- Autonomous systems
- Situational awareness applications
- Machine learning and AI models

SDG enables repeatable simulation, scalable experimentation, and accelerated development of SAPIENT-based surveillance and autonomy solutions.

## Key Features

* **Single-Source Configuration**
Define entire complex scenarios—including geography, assets, and sensor layouts—within a single, human-readable `.json` file.
* **Terrain-Aware Simulation**
Ingests real-world Digital Elevation Models (DEM) via OpenTopography to ensure entity paths and line-of-sight calculations adapt realistically to local geography.
* **High-Fidelity Kinematics**
Propagates entity movement using physics-backed behavioral profiles, establishing a mathematically precise absolute "Ground Truth."
* **Realistic Sensor Degradation**
Emulates true-to-life surveillance limitations by actively injecting measurement noise, tracking errors, and horizon/visibility constraints.
* **Native SAPIENT Compliance**
Outputs an asynchronous, real-time data stream fully formatted to the SAPIENT message protocol for seamless integration with downstream command and control systems.

## Getting Started

Follow these instructions to configure, run, and export your sensor simulation scenario.

### Prerequisites

Ensure your host machine has Python 3.8+ installed. Clone this repository and install the required dependencies:

### Clone the repository
```bash
git clone https://github.com/DEFINE-AI-Foundry/scenario-generator.git
cd scenario-generator
```

### Install Python requirements
```bash
pip install -r requirements.txt
```

### Do a test run
```bash
python -m src.generate_scenario --scenario joensuu
```
This accumulates:
- tactical_vectors
- output_messages

### Repository Directory Structure

The workspace is organized into modular directories following standard  development patterns:
```text
scenario-generator/
├── config/
│   ├── scenarios/            # Scenario configuration templates (.json)
│   └── schemas/              # Schema files needed for validations
├── data/
│   ├── export_output/        # Exported data for external consumption (.csv) (not committed)
│   ├── generated_output/     # Simulation output messages (.json) (not committed)
│   ├── tactical_scenarios/   # Scenarios with enhanced features (.json) (not committed)
│   └── terrain/              # Terrain data from OpenTopography (.asc) (not committed)
├── src/
│   ├── generation/           # Modules of scenario generation pipeline
│   ├── validation/           # Validation scripts, e.g. for templates
│   ├── config.py             # Global run parameter setups
│   ├── export_scenario.py    # Exports CSV files for scenario layers
│   └── generate_scenario.py  # Scenario generation pipeline code
├── tests/                    # Test automation
├── LICENSE                   # Licensing legal terms
├── README.md                 # System documentation
└── requirements.txt          # Project requirements manifest
```

## Execution Pipeline (Step-by-Step)

The synthetic data generation workflow consists of two simple steps and optional export:
```text
  [ Scenario Config ] ---> ( Run Simulation ) ---> [ SAPIENT Messages ] ---> ( Export Layers ) ---> [ GIS Maps ]
```

### Step 1: Scenario Configuration Setup

Create or modify a manually planned attack scenario (e.g., `data/config/joensuu.json`). Define targets, baseline drone attack flight lines, sensor positions, and terrain anchor elevations inside this file.

### Step 2: Execute the Generation Engine

Run the main generator to parse your scenario config, refine flight vectors using terrain elevations, emulate target detections, and generate SAPIENT-compliant real-time outputs:
```bash
# Runs the simulation using input config, fetches terrain, and dumps tactical and message streams
python -m src.generate_scenario --scenario joensuu
```

Outputs Generated:

`joensuu_messages.json`: A chronological database of simulated sensor detection reports formatted in compliance with SAPIENT message standards.

### Step 3: Run the GIS Layer Exporter (optional)

Transform tactical data and sensor message outputs into map-ready CSV files:
```bash
python ./src/export_scenario.py \
  --scenario data/tactical_scenarios/joensuu_tactical.json \
  --messages data/generated_output/joensuu_messages.json \
  --outdir data/export_output/ \
  --sample-rate 10
```
OR
```bash
python -m src.export_scenario --location joensuu
```

## Geospatial Layer Visualization

- Once exported, you can instantly visualize your tactical layers on Google My Maps or standard GIS tools (QGIS, ArcGIS):

- Open Google My Maps and create a new custom map.

- For each generated CSV layer inside data/export_output/, click Add Layer and select Import:

| Layer Source CSV | Spatial Column Selection | Label / Title Column | Visual Styling Tips |
| :--- | :--- | :--- | :--- |
| `targets_layer.csv` | Latitude, Longitude | `Target_Name` | Red Flags (🏢) for critical structures. |
| `flight_vectors_layer.csv` | WKT (Well-Known Text) | `Vector_ID` | Group styles by classification (solid lines). |
| `sensor_network_layer.csv` | Latitude, Longitude | `Sensor_Node_ID` | Blue Radar/Shield icons showing sensor nodes. |
| `sensor_detections_layer.csv` | Latitude, Longitude | `Track_ID` | Small point clusters grouped by Tracking State. |