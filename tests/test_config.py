"""Tests for configuration loading and validation (no live calls)."""

from __future__ import annotations

import pytest

from deep_agents_foundry.config import (
    MODEL_DEPLOYMENT_ENV,
    PROJECT_ENDPOINT_ENV,
    Settings,
    load_settings,
)
from deep_agents_foundry.errors import ConfigurationError


def test_load_settings_reads_environment(monkeypatch):
    monkeypatch.setenv(PROJECT_ENDPOINT_ENV, "https://example.services.ai.azure.com")
    monkeypatch.setenv(MODEL_DEPLOYMENT_ENV, "gpt-test")

    settings = load_settings(use_dotenv=False)

    assert settings == Settings(
        project_endpoint="https://example.services.ai.azure.com",
        model_deployment="gpt-test",
    )


def test_load_settings_strips_whitespace(monkeypatch):
    monkeypatch.setenv(PROJECT_ENDPOINT_ENV, "  https://example  ")
    monkeypatch.setenv(MODEL_DEPLOYMENT_ENV, "  gpt-test  ")

    settings = load_settings(use_dotenv=False)

    assert settings.project_endpoint == "https://example"
    assert settings.model_deployment == "gpt-test"


def test_load_settings_missing_raises(monkeypatch):
    monkeypatch.delenv(PROJECT_ENDPOINT_ENV, raising=False)
    monkeypatch.delenv(MODEL_DEPLOYMENT_ENV, raising=False)

    with pytest.raises(ConfigurationError) as excinfo:
        load_settings(use_dotenv=False)

    message = str(excinfo.value)
    assert PROJECT_ENDPOINT_ENV in message
    assert MODEL_DEPLOYMENT_ENV in message


def test_load_settings_partial_missing_names_only_missing(monkeypatch):
    monkeypatch.setenv(PROJECT_ENDPOINT_ENV, "https://example")
    monkeypatch.delenv(MODEL_DEPLOYMENT_ENV, raising=False)

    with pytest.raises(ConfigurationError) as excinfo:
        load_settings(use_dotenv=False)

    message = str(excinfo.value)
    assert MODEL_DEPLOYMENT_ENV in message
    assert PROJECT_ENDPOINT_ENV not in message
