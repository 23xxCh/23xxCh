"""LLM assistant backend for the H2Track web console.

This module re-exports symbols from the llm/ package for backwards compatibility.
New code should import directly from h2track_tracking.llm instead.
"""

from .llm import (
    ALLOWED_COMMAND_PREFIXES,
    DEFAULT_PROFILE_PATH,
    FORBIDDEN_COMMAND_PATTERNS,
    LlmController,
    LlmProfileStore,
    OpenAICompatClient,
    SYSTEM_PROMPT,
    _extract_json_block,
)

__all__ = [
    "ALLOWED_COMMAND_PREFIXES",
    "DEFAULT_PROFILE_PATH",
    "FORBIDDEN_COMMAND_PATTERNS",
    "LlmController",
    "LlmProfileStore",
    "OpenAICompatClient",
    "SYSTEM_PROMPT",
    "_extract_json_block",
]
