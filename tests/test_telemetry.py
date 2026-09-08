"""Tests for tracing/telemetry (external constructors mocked, no live calls)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from deep_agents_foundry import telemetry as telemetry_module
from deep_agents_foundry.config import (
    APP_INSIGHTS_CONNECTION_STRING_ENV,
    ENABLE_TRACE_CONTENT_RECORDING_ENV,
    TracingSettings,
    load_tracing_settings,
)


def test_build_azure_tracer_passes_expected_arguments(monkeypatch):
    captured = {}
    sentinel_tracer = object()

    monkeypatch.setattr(
        telemetry_module,
        "AzureAIOpenTelemetryTracer",
        lambda **kwargs: captured.update(kwargs) or sentinel_tracer,
    )

    settings = TracingSettings(
        connection_string="InstrumentationKey=abc",
        enable_content_recording=True,
    )

    result = telemetry_module.build_azure_tracer(settings, agent_id="my-agent")

    assert result is sentinel_tracer
    assert captured == {
        "connection_string": "InstrumentationKey=abc",
        "enable_content_recording": True,
        "agent_id": "my-agent",
    }


def test_build_azure_tracer_omits_agent_id_when_none(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        telemetry_module,
        "AzureAIOpenTelemetryTracer",
        lambda **kwargs: captured.update(kwargs) or object(),
    )

    settings = TracingSettings(
        connection_string="InstrumentationKey=abc",
        enable_content_recording=False,
    )

    telemetry_module.build_azure_tracer(settings, agent_id=None)

    assert "agent_id" not in captured


def test_load_tracing_settings_missing_connection_string_raises(monkeypatch):
    monkeypatch.delenv(APP_INSIGHTS_CONNECTION_STRING_ENV, raising=False)

    with pytest.raises(ValueError) as excinfo:
        load_tracing_settings(use_dotenv=False)

    assert APP_INSIGHTS_CONNECTION_STRING_ENV in str(excinfo.value)


def test_content_recording_defaults_to_false(monkeypatch):
    monkeypatch.setenv(APP_INSIGHTS_CONNECTION_STRING_ENV, "InstrumentationKey=abc")
    monkeypatch.delenv(ENABLE_TRACE_CONTENT_RECORDING_ENV, raising=False)

    settings = load_tracing_settings(use_dotenv=False)

    assert settings.enable_content_recording is False


@pytest.mark.parametrize("value", ["true", "True", "1", "yes", "on"])
def test_content_recording_opt_in(monkeypatch, value):
    monkeypatch.setenv(APP_INSIGHTS_CONNECTION_STRING_ENV, "InstrumentationKey=abc")
    monkeypatch.setenv(ENABLE_TRACE_CONTENT_RECORDING_ENV, value)

    settings = load_tracing_settings(use_dotenv=False)

    assert settings.enable_content_recording is True


@pytest.mark.parametrize("value", ["false", "False", "0", "no", "off"])
def test_content_recording_explicit_false(monkeypatch, value):
    monkeypatch.setenv(APP_INSIGHTS_CONNECTION_STRING_ENV, "InstrumentationKey=abc")
    monkeypatch.setenv(ENABLE_TRACE_CONTENT_RECORDING_ENV, value)

    settings = load_tracing_settings(use_dotenv=False)

    assert settings.enable_content_recording is False


def test_content_recording_invalid_value_raises(monkeypatch):
    monkeypatch.setenv(APP_INSIGHTS_CONNECTION_STRING_ENV, "InstrumentationKey=abc")
    monkeypatch.setenv(ENABLE_TRACE_CONTENT_RECORDING_ENV, "maybe")

    with pytest.raises(ValueError):
        load_tracing_settings(use_dotenv=False)


def test_attach_tracing_uses_with_config():
    agent = MagicMock()
    tracer = object()

    result = telemetry_module.attach_tracing(agent, tracer)

    agent.with_config.assert_called_once_with({"callbacks": [tracer]})
    assert result is agent.with_config.return_value


def test_build_traced_research_agent_composes_builders(monkeypatch):
    agent = MagicMock()
    sentinel_tracer = object()

    monkeypatch.setattr(telemetry_module, "build_research_agent", lambda: agent)
    monkeypatch.setattr(
        telemetry_module,
        "build_azure_tracer",
        lambda settings, *, agent_id: sentinel_tracer,
    )

    result = telemetry_module.build_traced_research_agent()

    agent.with_config.assert_called_once_with({"callbacks": [sentinel_tracer]})
    assert result is agent.with_config.return_value
