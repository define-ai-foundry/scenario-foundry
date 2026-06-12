import argparse
import sys
from pathlib import Path

# Ensure Python can discover modules inside the src/ directory
sys.path.append(str(Path(__file__).resolve().parent))

import src.config
from src.generation.fetch_terrain import main as run_fetch_terrain
from src.generation.optimize_vectors import main as run_optimize_vectors
from src.generation.generate_sensor_data import main as run_generate_sensor_data

def main():
    parser = argparse.ArgumentParser(description="SAPIENT Generation Pipeline Orchestrator")
    parser.add_argument(
        "--scenario", 
        required=True, 
        help="Name of the scenario file inside config/scenarios/ (e.g., joensuu.json or just joensuu)"
    )
    args = parser.parse_args()

    # 1. If scenario argument is missng .json extension, append it
    if not args.scenario.endswith(".json"):
        args.scenario += ".json"

    # 2. Resolve the absolute path for the input coarse scenario
    coarse_scenario_path = src.config.SCENARIOS_DIR / args.scenario
    if not coarse_scenario_path.exists():
        print(f"[ERROR] Scenario configuration file not found at: {coarse_scenario_path}")
        return

    scenario_name = coarse_scenario_path.stem  # Extracts e.g., "joensuu"

    print("=" * 80)
    print(f"LAUNCHING SAPIENT GENERATION PIPELINE: {scenario_name.upper()}")
    print("=" * 80)

    # STEP 1: Fetch Terrain Data (Downloads only if missing from local cache)
    print("\n[STEP 1/3] Verifying and fetching required terrain grid nodes...")
    sys.argv = ["fetch_terrain.py", "--scenario", str(coarse_scenario_path)]
    try:
        run_fetch_terrain()
    except Exception as e:
        print(f"[ERROR] Step 1 (Terrain Fetch) failed: {e}")
        return

    # STEP 2: Optimize Threat Vectors based on Terrain Geometry
    print("\n[STEP 2/3] Optimizing threat flight vectors using terrain data...")
    tactical_scenario_path = src.config.TACTICAL_DIR / f"{scenario_name}_tactical.json"
    sys.argv = [
        "optimize_vectors.py", 
        "--scenario", str(coarse_scenario_path), 
        "--output", str(tactical_scenario_path)
    ]
    try:
        run_optimize_vectors()
    except Exception as e:
        print(f"[ERROR] Step 2 (Vector Optimization) failed: {e}")
        return

    # STEP 3: Generate Sensor Data (Generate SAPIENT Message Stream)
    print("\n[STEP 3/3] Generating synchronized SAPIENT sensor data stream...")
    generated_output_path = src.config.GENERATED_DIR / f"{scenario_name}_messages.json"
    sys.argv = [
        "generate_sensor_data.py", 
        "--scenario", str(tactical_scenario_path), 
        "--output", str(generated_output_path)
    ]
    try:
        run_generate_sensor_data()
    except Exception as e:
        print(f"[ERROR] Step 3 (Sensor Generation) failed: {e}")
        return

    # Execution complete
    print("\n" + "=" * 80)
    print("SAPIENT GENERATION PIPELINE COMPLETED SUCCESSFULLY!")
    print(f"-> Refined Tactical Scenario: {tactical_scenario_path.relative_to(src.config.PROJECT_ROOT)}")
    print(f"-> SAPIENT Log Stream (JSON): {generated_output_path.relative_to(src.config.PROJECT_ROOT)}")
    print("=" * 80)

if __name__ == "__main__":
    main()