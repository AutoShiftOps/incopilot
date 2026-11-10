"""Shared fixtures."""

from pathlib import Path

import pytest

from incopilot.patterns import resolve_packs

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "checkout-incident.log"


@pytest.fixture
def core():
    return resolve_packs(["core"])


@pytest.fixture
def example_log():
    return EXAMPLE
