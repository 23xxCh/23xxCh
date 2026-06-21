"""Authentication middleware for the web console REST API.

This module provides API Key authentication for protecting sensitive endpoints.
Authentication is automatically disabled when no API key is configured.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class AuthSettings:
    """Immutable authentication settings.

    Attributes:
        API_KEY: The API key for authentication. If empty, auth is disabled.
        AUTH_ENABLED: Whether authentication is enabled (True if API_KEY is set).
    """

    API_KEY: str
    AUTH_ENABLED: bool

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "AuthSettings":
        """Create settings from environment variables.

        Args:
            env: Optional environment dict. Defaults to os.environ.

        Returns:
            AuthSettings instance.
        """
        source = env if env is not None else dict(os.environ)
        api_key = source.get("H2TRACK_API_KEY", "")
        return cls(API_KEY=api_key, AUTH_ENABLED=bool(api_key))


# Default settings instance from environment
settings = AuthSettings.from_env()


def verify_api_key(x_api_key: Optional[str]) -> str:
    """Verify the API key from request header.

    This function is designed to be used as a FastAPI dependency.
    When authentication is disabled (no API key configured), it always passes.

    Args:
        x_api_key: The API key from X-API-Key header, or None if not provided.

    Returns:
        The verified API key string, or empty string if auth is disabled.

    Raises:
        HTTPException: If authentication is enabled and the key is invalid or missing.
    """
    if not settings.AUTH_ENABLED:
        return ""

    if x_api_key is None or x_api_key != settings.API_KEY:
        # Import here to avoid circular dependency when FastAPI is not installed
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Invalid API key")

    return x_api_key


def create_auth_dependency() -> Any:
    """Create a FastAPI dependency for API key verification.

    This returns a dependency that can be used with Depends() in FastAPI routes.
    The dependency uses Header() to extract the X-API-Key header.
    When authentication is disabled, the header is optional.

    Returns:
        A callable suitable for use with FastAPI Depends().

    Example:
        ```python
        from fastapi import Depends

        auth_dep = create_auth_dependency()

        @app.post("/api/sim/start")
        async def start_sim(auth: str = Depends(auth_dep)):
            ...
        ```
    """
    from fastapi import Depends, Header

    # Make header optional - verification logic handles None case
    async def _verify(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> str:
        return verify_api_key(x_api_key)

    return Depends(_verify)


# Pre-computed dependency for convenience
# This is None if FastAPI is not available
_auth_dependency: Any = None


def get_auth_dependency() -> Any:
    """Get the authentication dependency, creating it lazily.

    Returns:
        FastAPI Depends object for authentication, or None if FastAPI unavailable.
    """
    global _auth_dependency
    if _auth_dependency is None:
        try:
            _auth_dependency = create_auth_dependency()
        except ImportError:
            pass
    return _auth_dependency
