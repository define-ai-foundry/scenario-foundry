# Copyright 2026 Lempea Edge Oy / DEFINE AI Foundry
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path
from dotenv import load_dotenv

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env file
load_dotenv(PROJECT_ROOT / ".env")

# Directory paths
CONFIG_DIR = PROJECT_ROOT / "config"
SCENARIOS_DIR = CONFIG_DIR / "scenarios"
SCHEMA_DIR = CONFIG_DIR / "schemas"

DATA_DIR = PROJECT_ROOT / "data"
TERRAIN_DIR = DATA_DIR / "terrain"
TACTICAL_DIR = DATA_DIR / "tactical_scenarios"
GENERATED_DIR = DATA_DIR / "generated_output"
EXPORT_DIR = DATA_DIR / "export_output"

# Ensure directories exist
for folder in [SCENARIOS_DIR, SCHEMA_DIR, TERRAIN_DIR, TACTICAL_DIR, GENERATED_DIR, EXPORT_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# Environment variables
OPENTOPOGRAPHY_API_KEY = os.getenv("OPENTOPOGRAPHY_API_KEY")