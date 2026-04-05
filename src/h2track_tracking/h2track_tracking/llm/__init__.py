"""LLM assistant modules for H2Track web console."""

from .actions import (
    ALLOWED_COMMAND_PREFIXES,
    FORBIDDEN_COMMAND_PATTERNS,
)
from .chat import SYSTEM_PROMPT, extract_json_block, normalize_actions
from .client import OpenAICompatClient
from .controller import LlmController
from .profile_store import DEFAULT_PROFILE_PATH, LlmProfileStore

# Backward compatibility: expose _extract_json_block as the internal name
_extract_json_block = extract_json_block

__all__ = [
    "ALLOWED_COMMAND_PREFIXES",
    "DEFAULT_PROFILE_PATH",
    "FORBIDDEN_COMMAND_PATTERNS",
    "LlmController",
    "LlmProfileStore",
    "OpenAICompatClient",
    "SYSTEM_PROMPT",
    "_extract_json_block",
    # New exports
    "extract_json_block",
    "normalize_actions",
]
