"""Tests for scenario_foundry.config module-level setup."""

from pathlib import Path

from scenario_foundry import config


def test_exported_paths_are_paths():
    for name in [
        "PROJECT_ROOT",
        "CONFIG_DIR",
        "SCENARIOS_DIR",
        "SCHEMA_DIR",
        "DATA_DIR",
        "TERRAIN_DIR",
        "TACTICAL_DIR",
        "GENERATED_DIR",
        "EXPORT_DIR",
    ]:
        assert isinstance(getattr(config, name), Path)


def test_directories_created_by_import():
    for folder in [
        config.SCENARIOS_DIR,
        config.SCHEMA_DIR,
        config.TERRAIN_DIR,
        config.TACTICAL_DIR,
        config.GENERATED_DIR,
        config.EXPORT_DIR,
    ]:
        assert folder.is_dir()
