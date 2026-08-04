"""Every committed scenario must validate against the real schema and taxonomy."""

import pytest

from scenario_foundry import config
from scenario_foundry.validation.validate import validate_scenario

SCHEMA_PATH = config.SCHEMA_DIR / "scenario.schema.json"
SCENARIO_PATHS = sorted(config.SCENARIOS_DIR.glob("*.json"))


def test_scenarios_were_discovered():
    # Guards the glob: an empty parametrize would report as a pass.
    assert SCENARIO_PATHS


@pytest.mark.parametrize("scenario_path", SCENARIO_PATHS, ids=lambda p: p.stem)
def test_committed_scenario_is_valid(scenario_path):
    assert validate_scenario(scenario_path, SCHEMA_PATH) is True
