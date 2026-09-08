"""Configuration loading and validation for the research agent."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

PROJECT_ENDPOINT_ENV = "AZURE_AI_PROJECT_ENDPOINT"
MODEL_DEPLOYMENT_ENV = "AZURE_AI_MODEL_DEPLOYMENT_NAME"


@dataclass(frozen=True)
class Settings:
    """Explicit settings required to build the Foundry-backed model."""

    project_endpoint: str
    model_deployment: str


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
        raise ValueError(
            "Missing required environment variables: " + ", ".join(missing)
        )

    return Settings(
        project_endpoint=project_endpoint,
        model_deployment=model_deployment,
    )
