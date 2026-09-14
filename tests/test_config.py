"""Tests for configuration loading and validation (no live calls)."""

from __future__ import annotations

import pytest

from deep_agents_foundry.config import (
    MODEL_DEPLOYMENT_ENV,
    POSTGRES_DATABASE_ENV,
    POSTGRES_HOST_ENV,
    POSTGRES_SSLMODE_ENV,
    POSTGRES_USER_ENV,
    PROJECT_ENDPOINT_ENV,
    PostgresSettings,
    Settings,
    load_postgres_settings,
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


def test_load_postgres_settings_reads_environment(monkeypatch):
    monkeypatch.setenv(POSTGRES_HOST_ENV, "srv.postgres.database.azure.com")
    monkeypatch.setenv(POSTGRES_DATABASE_ENV, "deepagents")
    monkeypatch.setenv(POSTGRES_USER_ENV, "shiva@contoso.com")
    monkeypatch.setenv(POSTGRES_SSLMODE_ENV, "require")

    settings = load_postgres_settings(use_dotenv=False)

    assert settings == PostgresSettings(
        host="srv.postgres.database.azure.com",
        database="deepagents",
        user="shiva@contoso.com",
        sslmode="require",
    )


def test_load_postgres_settings_defaults_sslmode(monkeypatch):
    monkeypatch.setenv(POSTGRES_HOST_ENV, "srv")
    monkeypatch.setenv(POSTGRES_DATABASE_ENV, "db")
    monkeypatch.setenv(POSTGRES_USER_ENV, "user")
    monkeypatch.delenv(POSTGRES_SSLMODE_ENV, raising=False)

    assert load_postgres_settings(use_dotenv=False).sslmode == "require"


def test_load_postgres_settings_missing_required_raises(monkeypatch):
    for env in (POSTGRES_HOST_ENV, POSTGRES_DATABASE_ENV, POSTGRES_USER_ENV):
        monkeypatch.delenv(env, raising=False)

    with pytest.raises(ConfigurationError) as excinfo:
        load_postgres_settings(use_dotenv=False)

    message = str(excinfo.value)
    assert POSTGRES_HOST_ENV in message
    assert POSTGRES_DATABASE_ENV in message
    assert POSTGRES_USER_ENV in message
