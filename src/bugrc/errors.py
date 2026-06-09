"""Shared BugRC exceptions."""

from __future__ import annotations

from typing import Any


class BugRCError(Exception):
    """Base exception for BugRC errors."""


class ModelSerializationError(BugRCError):
    """Raised when JSON serialization or deserialization fails."""


class ModelValidationError(BugRCError):
    """Raised when a model fails validation."""

    def __init__(self, model_name: str, details: Any) -> None:
        self.model_name = model_name
        self.details = details
        super().__init__(f"Validation failed for {model_name}: {details}")


class LLMError(BugRCError):
    """Base exception for LLM-related failures."""


class LLMProviderError(LLMError):
    """Raised when an LLM provider request fails."""


class LLMResponseParseError(LLMError):
    """Raised when an LLM response cannot be parsed into the expected structure."""
