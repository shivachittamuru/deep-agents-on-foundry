"""Configuration loading and validation for the research agent."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .errors import ConfigurationError

PROJECT_ENDPOINT_ENV = "AZURE_AI_PROJECT_ENDPOINT"
MODEL_DEPLOYMENT_ENV = "AZURE_AI_MODEL_DEPLOYMENT_NAME"
APP_INSIGHTS_CONNECTION_STRING_ENV = "APPLICATIONINSIGHTS_CONNECTION_STRING"
ENABLE_TRACE_CONTENT_RECORDING_ENV = "ENABLE_TRACE_CONTENT_RECORDING"

POSTGRES_HOST_ENV = "POSTGRES_HOST"
POSTGRES_DATABASE_ENV = "POSTGRES_DATABASE"
POSTGRES_USER_ENV = "POSTGRES_USER"
POSTGRES_SSLMODE_ENV = "POSTGRES_SSLMODE"
_DEFAULT_SSLMODE = "require"

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class Settings:
    """Explicit settings required to build the Foundry-backed model."""

    project_endpoint: str
    model_deployment: str


@dataclass(frozen=True)
class TracingSettings:
    """Explicit settings required to build the Application Insights tracer."""

    connection_string: str
    enable_content_recording: bool


@dataclass(frozen=True)
class PostgresSettings:
    """PostgreSQL connection settings (no password — Entra auth is used)."""

    host: str
    database: str
    user: str
    sslmode: str


def load_settings(*, use_dotenv: bool = True) -> Settings:
    """Read and validate the required environment variables.

    Set ``use_dotenv=False`` to skip loading a local ``.env`` file (used by tests
    so the environment is fully controlled by the caller).
    """
    if use_dotenv:
        load_dotenv()

    project_endpoint = os.environ.get(PROJECT_ENDPOINT_ENV, "").strip()
    model_deployment = os.environ.get(MODEL_DEPLOYMENT_ENV, "").strip()

    missing = [
        name
        for name, value in (
            (PROJECT_ENDPOINT_ENV, project_endpoint),
            (MODEL_DEPLOYMENT_ENV, model_deployment),
        )
        if not value
    ]
    if missing:
        raise ConfigurationError(
            "Missing required environment variables: " + ", ".join(missing)
        )

    return Settings(
        project_endpoint=project_endpoint,
        model_deployment=model_deployment,
    )


def _parse_bool(value: str, *, default: bool = False) -> bool:
    """Parse a common truthy/falsey environment string, falling back to default."""
    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ConfigurationError(
        f"Cannot parse boolean from {ENABLE_TRACE_CONTENT_RECORDING_ENV}={value!r}. "
        f"Use one of: {sorted(_TRUE_VALUES | _FALSE_VALUES)}."
    )


def load_tracing_settings(*, use_dotenv: bool = True) -> TracingSettings:
    """Read and validate tracing configuration.

    The Application Insights connection string is required only when tracing is
    requested (this loader is never called by `build_research_agent()`).
    Content recording defaults to ``False`` for production safety.
    """
    if use_dotenv:
        load_dotenv()

    connection_string = os.environ.get(
        APP_INSIGHTS_CONNECTION_STRING_ENV, ""
    ).strip()
    if not connection_string:
        raise ConfigurationError(
            "Missing required environment variable: "
            f"{APP_INSIGHTS_CONNECTION_STRING_ENV}"
        )

    enable_content_recording = _parse_bool(
        os.environ.get(ENABLE_TRACE_CONTENT_RECORDING_ENV, ""),
        default=False,
    )

    return TracingSettings(
        connection_string=connection_string,
        enable_content_recording=enable_content_recording,
    )


def load_postgres_settings(*, use_dotenv: bool = True) -> PostgresSettings:
    """Read and validate PostgreSQL settings (host/database/user/sslmode).

    No password is read: authentication uses Entra ID tokens obtained at runtime.
    `sslmode` defaults to ``require``.
    """
    if use_dotenv:
        load_dotenv()

    host = os.environ.get(POSTGRES_HOST_ENV, "").strip()
    database = os.environ.get(POSTGRES_DATABASE_ENV, "").strip()
    user = os.environ.get(POSTGRES_USER_ENV, "").strip()
    sslmode = os.environ.get(POSTGRES_SSLMODE_ENV, "").strip() or _DEFAULT_SSLMODE

    missing = [
        name
        for name, value in (
            (POSTGRES_HOST_ENV, host),
            (POSTGRES_DATABASE_ENV, database),
            (POSTGRES_USER_ENV, user),
        )
        if not value
    ]
    if missing:
        raise ConfigurationError(
            "Missing required environment variables: " + ", ".join(missing)
        )

    return PostgresSettings(
        host=host,
        database=database,
        user=user,
        sslmode=sslmode,
    )
