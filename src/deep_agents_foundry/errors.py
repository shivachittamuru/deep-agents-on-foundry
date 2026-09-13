"""Package-specific exception hierarchy for explicit startup/construction failures."""

from __future__ import annotations


class DeepAgentsFoundryError(Exception):
    """Base class for all deep-agents-foundry errors."""


class ConfigurationError(DeepAgentsFoundryError):
    """Raised when required configuration is missing or invalid."""


class ModelInitializationError(DeepAgentsFoundryError):
    """Raised when the Foundry-backed chat model fails to construct."""


class ToolInitializationError(DeepAgentsFoundryError):
    """Raised when a tool fails to construct."""


class AgentInitializationError(DeepAgentsFoundryError):
    """Raised when the Deep Agent fails to construct."""


class ExperimentLogError(DeepAgentsFoundryError):
    """Raised when a persisted experiment record cannot be read or parsed."""


class EconomicsLogError(DeepAgentsFoundryError):
    """Raised when a persisted economics record cannot be read or parsed."""
