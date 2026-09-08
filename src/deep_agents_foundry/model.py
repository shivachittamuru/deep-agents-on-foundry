"""Build the Foundry-backed LangChain chat model."""

from __future__ import annotations

from azure.identity import DefaultAzureCredential
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel

from .config import Settings, load_settings
from .errors import ModelInitializationError


def build_model(settings: Settings | None = None) -> AzureAIOpenAIApiChatModel:
    """Construct the `AzureAIOpenAIApiChatModel` used by the research agent.

    Authenticates with Entra ID via `DefaultAzureCredential`, matching the
    notebook setup. Construction is not a connectivity/auth check: Azure calls
    may still fail lazily at invocation time.
    """
    settings = settings or load_settings()

    try:
        return AzureAIOpenAIApiChatModel(
            project_endpoint=settings.project_endpoint,
            credential=DefaultAzureCredential(),
            model=settings.model_deployment,
        )
    except Exception as exc:
        raise ModelInitializationError(
            "Failed to construct the Foundry chat model."
        ) from exc
