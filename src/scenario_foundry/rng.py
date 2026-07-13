# Copyright 2026 Lempea Edge Oy / DEFINE AI Foundry
# SPDX-License-Identifier: Apache-2.0

import random

import numpy as np


def seed_all(seed):
    """Seed all RNG sources (stdlib random + numpy) for reproducible runs."""
    random.seed(seed)
    np.random.seed(seed)
