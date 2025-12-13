"""Pytest configuration and shared fixtures."""

import pytest


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-smoke",
        action="store_true",
        default=False,
        help="Run smoke tests that require real API keys",
    )


def pytest_collection_modifyitems(config, items):
    """Skip smoke tests unless --run-smoke is passed."""
    if config.getoption("--run-smoke"):
        return

    skip_smoke = pytest.mark.skip(reason="Need --run-smoke to run")
    for item in items:
        if "smoke" in item.keywords:
            item.add_marker(skip_smoke)
