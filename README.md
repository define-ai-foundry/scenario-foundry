SAPIENT Synthetic Data Generator (SDG)

The SAPIENT Synthetic Data Generator (SDG) is a data-driven, highly configurable simulation framework designed to generate realistic, multi-sensor surveillance and tracking data for arbitrary operational scenarios. By combining user-defined environmental inputs with advanced sensor error modeling, the platform generates synthetic, SAPIENT-compliant sensor streams that emulate how real-world surveillance networks observe, track, classify, and report physical activity.

High-quality multi-sensor datasets are often scarce, expensive to collect, operationally sensitive, or completely unavailable. The SDG addresses this critical bottleneck by decoupling data generation from specific geographic regions, threat models, or hardware deployments. It serves as an on-demand engine to rapidly build, test, and validate command-and-control (C2) systems, sensor fusion platforms, autonomy software, and machine learning models without dependence on live-field exercises or proprietary data networks.

🛠️ System Architecture & Framework Layers

The SDG engine splits data generation into a clear, three-tiered operational pipeline:
**` ```text `**
  +--------------------------------------------------------+
  |               Scenario Definition Layer                |
  |  - Geographic Coordinates   - Operational Timelines    |
  |  - Critical Infrastructure  - Sensor Deployments       |
  +---------------------------+----------------------------+
                              |
                              v
  +--------------------------------------------------------+
  |                Simulation Engine Layer                 |
  |  - Behavioral Profiles      - Terrain Refinement       |
  |  - Kinematic Propagation    - Ground Truth Engine      |
  +---------------------------+----------------------------+
                              |
                              v
  +--------------------------------------------------------+
  |                 Sensor Emulation Layer                 |
  |  - Measurement Noise        - Horizon Constraints      |
  |  - Asynchronous Schedules  - SAPIENT Message Export   |
  +--------------------------------------------------------+
**` ``` `**

Native Repository Diagram (Mermaid)

On GitHub, GitLab, and other modern Git platforms, this diagram renders natively as a crisp, interactive vector graphic:

**` ```mermaid `**
graph TD
    subgraph Scenario Definition Layer
        A[Geographic Coordinates & Timelines] --> D
        B[Critical Infrastructure & Assets] --> D
        C[Sensor Deployments & Coverage] --> D
    end

    subgraph Simulation Engine Layer
        D[Behavioral Profiles & Kinematics] --> E[OpenTopography DEM Ingest]
        E --> F[Terrain-Aware Path Refinement]
        F --> G[Absolute Ground Truth Engine]
    end

    subgraph Sensor Emulation Layer
        G --> H[Horizon & Visibility Constraints]
        H --> I[Perturbation & Error Injection]
        I --> J[Chronological SAPIENT Message Stream]
    end

    style G fill:#2d3748,stroke:#4a5568,stroke-width:2px,color:#fff
    style J fill:#1a365d,stroke:#2b6cb0,stroke-width:2px,color:#fff
**` ``` `**

Scenario Definition Layer: Reads a single configuration file (.json) that acts as the authoritative description of the environment. This includes geographic setups, infrastructure assets, environmental conditions, and sensor layouts.

Simulation Engine Layer: Digitally spawns and moves entities over time. It maintains the exact kinematic state (true location, speed, altitude) for all entities, establishing the scenario's absolute "Ground Truth".

Sensor Emulation Layer: Evaluates how individual surveillance assets perceive the ground truth. It filters reality through local constraints, degradation rules, and noise profiles to output an imperfect, realistic data stream.

⛰️ Terrain-Aware Path Refinement

The platform supports high-fidelity path adjustment using elevation data from OpenTopography terrain datasets. Instead of relying on rigid, geometric routes or flat-earth assumptions, the simulation builds geographic terrain environments using real-world coordinates.
**` ```text `**
  Manually Planned Approach (joensuu.json) 
                     |
                     v
    [ OpenTopography DEM Ingest Engine ]
                     |
                     v
      Terrain-Aware Path Refinement ---> Elevation Anchors Interpolation
                     |
                     v
   Enhanced Tactical Profiles (joensuu_tactical.json)
**` ``` `**

Core Capabilities

Elevation-Aware Route Refinement: Automatically adapts simple straight-line vector waypoints into terrain-conforming trajectories.

Above-Ground-Level (AGL) Altitude Estimation: Computes and locks threat movements to precise heights relative to the local surface topography, preventing subterranean clipping.

Realistic Terminal Trajectories: Simulates terrain-hugging approach vectors and terminal engagement dives against infrastructure assets.

Sensor Line-of-Sight (LoS) Validation: Provides surface profiles to the Sensor Emulation Layer to calculate physical visibility limits, terrain masking, and horizon blocking.

🚀 Getting Started

Follow these instructions to configure, run, and export your sensor simulation scenario.

📋 Prerequisites

Ensure your host machine has Python 3.8+ installed. Clone this repository and install the required dependencies:

# Clone the repository
git clone [https://github.com/DEFINE-AI-Foundry/scenario-generator.git](https://github.com/DEFINE-AI-Foundry/scenario-generator.git)
cd scenario-generator

# Install Python requirements
pip install -r requirements.txt


📦 Repository Directory Structure

The workspace is organized into modular directories following standard  development patterns:
**````text `**
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
**` ``` `**

🏃 Execution Pipeline (Step-by-Step)

The synthetic data generation workflow consists of three simple steps:
**` ```text `**
  [ Scenario Config ] ---> ( Run Simulation ) ---> [ SAPIENT Messages ] ---> ( Export Layers ) ---> [ GIS Maps ]
**` ``` `**

Step 1: Scenario Configuration Setup

Create or modify a manually planned attack scenario (e.g., data/config/joensuu.json). Define targets, baseline drone attack flight lines, sensor positions, and terrain anchor elevations inside this file. (See the Scenario Configuration Guide below for detailed parameters).

Step 2: Execute the Generation Engine

Run the main generator to parse your scenario config, refine flight vectors using terrain elevations, emulate target detections, and generate SAPIENT-compliant real-time outputs:
**` ```bash `**
# Runs the simulation using input config, fetches terrain, and dumps tactical and message streams
python -m src.generate_scenario --scenario joensuu
**` ``` `**

Outputs Generated:

joensuu_tactical.json: An enhanced configuration mapping terrain-refined WKT flight paths alongside target assets and defensive sensor locations.

joensuu_messages.json: A chronological database of simulated sensor detection reports formatted in compliance with SAPIENT message standards.

Step 3: Run the GIS Layer Exporter

Transform tactical data and sensor message outputs into map-ready CSV files:
**` ```bash `**
python ./src/export_scenario.py \
  --scenario data/tactical_scenarios/joensuu_tactical.json \
  --messages data/generated_output/joensuu_messages.json \
  --outdir data/export_output/ \
  --sample-rate 10

OR

python -m src.export_scenario --location joensuu
**` ``` `**

🗺️ Geospatial Layer Visualization

Once exported, you can instantly visualize your tactical layers on Google My Maps or standard GIS tools (QGIS, ArcGIS):

Open Google My Maps and create a new custom map.

For each generated CSV layer inside data/output/gis_layers/, click Add Layer and select Import:

| Layer Source CSV | Spatial Column Selection | Label / Title Column | Visual Styling Tips |
| :--- | :--- | :--- | :--- |
| `targets_layer.csv` | Latitude, Longitude | `Target_Name` | Red Flags (🏢) for critical structures. |
| `flight_vectors_layer.csv` | WKT (Well-Known Text) | `Vector_ID` | Group styles by classification (solid lines). |
| `sensor_network_layer.csv` | Latitude, Longitude | `Sensor_Node_ID` | Blue Radar/Shield icons showing sensor nodes. |
| `sensor_detections_layer.csv` | Latitude, Longitude | `Track_ID` | Small point clusters grouped by Tracking State. |