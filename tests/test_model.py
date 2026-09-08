"""Tests for model construction (external constructors mocked, no live calls)."""

from __future__ import annotations

from deep_agents_foundry import model as model_module
from deep_agents_foundry.config import Settings
from deep_agents_foundry.errors import ModelInitializationError

import pytest


def test_build_model_passes_expected_arguments(monkeypatch):
    captured = {}
    sentinel_credential = object()
    sentinel_model = object()

    def fake_credential():
        return sentinel_credential

    def fake_chat_model(**kwargs):
        captured.update(kwargs)
        return sentinel_model

    monkeypatch.setattr(model_module, "DefaultAzureCredential", fake_credential)
    monkeypatch.setattr(model_module, "AzureAIOpenAIApiChatModel", fake_chat_model)

    settings = Settings(
        project_endpoint="https://example.services.ai.azure.com",
        model_deployment="gpt-test",
    )

    result = model_module.build_model(settings)

    assert result is sentinel_model
    assert captured == {
        "project_endpoint": "https://example.services.ai.azure.com",
        "credential": sentinel_credential,
        "model": "gpt-test",
    }


def test_build_model_loads_settings_when_not_provided(monkeypatch):
    sentinel_settings = Settings(
        project_endpoint="https://loaded",
        model_deployment="loaded-deployment",
    )
    captured = {}

    monkeypatch.setattr(
        model_module, "load_settings", lambda: sentinel_settings
    )
    monkeypatch.setattr(
        model_module, "DefaultAzureCredential", lambda: object()
    )
    monkeypatch.setattr(
        model_module,
        "AzureAIOpenAIApiChatModel",
        lambda **kwargs: captured.update(kwargs) or object(),
    )

    model_module.build_model()

    assert captured["project_endpoint"] == "https://loaded"
    assert captured["model"] == "loaded-deployment"


def test_build_model_wraps_constructor_failure(monkeypatch):
    original = RuntimeError("boom")

    def failing_constructor(**kwargs):
        raise original

    monkeypatch.setattr(model_module, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(
        model_module, "AzureAIOpenAIApiChatModel", failing_constructor
    )

    settings = Settings(
        project_endpoint="https://example",
        model_deployment="gpt-test",
    )

    with pytest.raises(ModelInitializationError) as excinfo:
        model_module.build_model(settings)

    assert excinfo.value.__cause__ is original
