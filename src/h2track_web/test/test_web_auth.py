"""Tests for web auth module."""

import pytest

from h2track_web.web.auth import (
    AuthSettings,
    get_auth_dependency,
    verify_api_key,
)


class TestAuthSettings:
    """Tests for AuthSettings dataclass."""

    def test_auth_settings_frozen(self):
        """AuthSettings should be immutable."""
        settings = AuthSettings(API_KEY="test-key", AUTH_ENABLED=True)
        with pytest.raises(AttributeError):
            settings.API_KEY = "new-key"  # type: ignore[misc]

    def test_from_env_no_key(self):
        """When no API key in environment, auth should be disabled."""
        settings = AuthSettings.from_env({})
        assert settings.API_KEY == ""
        assert settings.AUTH_ENABLED is False

    def test_from_env_with_key(self):
        """When API key is set, auth should be enabled."""
        settings = AuthSettings.from_env({"H2TRACK_API_KEY": "secret123"})
        assert settings.API_KEY == "secret123"
        assert settings.AUTH_ENABLED is True

    def test_from_env_uses_os_environ_by_default(self, monkeypatch):
        """from_env should use os.environ by default."""
        monkeypatch.setenv("H2TRACK_API_KEY", "env-key")
        settings = AuthSettings.from_env()
        assert settings.API_KEY == "env-key"
        assert settings.AUTH_ENABLED is True


class TestVerifyApiKey:
    """Tests for verify_api_key function."""

    def test_verify_passes_when_auth_disabled(self, monkeypatch):
        """When auth is disabled, verify should always pass."""
        monkeypatch.setattr(
            "h2track_tracking.web.auth.settings",
            AuthSettings(API_KEY="", AUTH_ENABLED=False),
        )
        result = verify_api_key("any-key")
        assert result == ""

    def test_verify_passes_with_correct_key(self, monkeypatch):
        """With correct API key, verify should pass."""
        monkeypatch.setattr(
            "h2track_tracking.web.auth.settings",
            AuthSettings(API_KEY="correct-key", AUTH_ENABLED=True),
        )
        result = verify_api_key("correct-key")
        assert result == "correct-key"

    def test_verify_raises_with_wrong_key(self, monkeypatch):
        """With wrong API key, verify should raise HTTPException."""
        monkeypatch.setattr(
            "h2track_tracking.web.auth.settings",
            AuthSettings(API_KEY="correct-key", AUTH_ENABLED=True),
        )
        with pytest.raises(Exception) as exc_info:
            verify_api_key("wrong-key")
        # Check it's an HTTPException with 403 status
        assert exc_info.value.status_code == 403  # type: ignore[attr-defined]
        assert "Invalid API key" in str(exc_info.value.detail)  # type: ignore[attr-defined]


@pytest.mark.skipif(
    not pytest.importorskip("fastapi", reason="fastapi not installed"),
    reason="fastapi not installed",
)
class TestAuthDependency:
    """Tests for FastAPI auth dependency integration."""

    def test_get_auth_dependency_returns_dependency(self):
        """get_auth_dependency should return a FastAPI Depends object."""
        dep = get_auth_dependency()
        assert dep is not None

    def test_auth_dependency_with_valid_key(self, monkeypatch):
        """Auth dependency should allow requests with valid API key."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        monkeypatch.setattr(
            "h2track_tracking.web.auth.settings",
            AuthSettings(API_KEY="test-key", AUTH_ENABLED=True),
        )

        # Need to re-create the dependency after changing settings
        from h2track_web.web.auth import create_auth_dependency

        auth_dep = create_auth_dependency()

        app = FastAPI()

        @app.post("/protected")
        async def protected(auth: str = auth_dep):
            return {"ok": True, "auth": auth}

        client = TestClient(app)
        response = client.post("/protected", headers={"X-API-Key": "test-key"})
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_auth_dependency_rejects_invalid_key(self, monkeypatch):
        """Auth dependency should reject requests with invalid API key."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        monkeypatch.setattr(
            "h2track_tracking.web.auth.settings",
            AuthSettings(API_KEY="correct-key", AUTH_ENABLED=True),
        )

        from h2track_web.web.auth import create_auth_dependency

        auth_dep = create_auth_dependency()

        app = FastAPI()

        @app.post("/protected")
        async def protected(auth: str = auth_dep):
            return {"ok": True}

        client = TestClient(app)
        response = client.post("/protected", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 403
        assert "Invalid API key" in response.json()["detail"]

    def test_auth_dependency_allows_when_disabled(self, monkeypatch):
        """When auth is disabled, dependency should allow all requests."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        monkeypatch.setattr(
            "h2track_tracking.web.auth.settings",
            AuthSettings(API_KEY="", AUTH_ENABLED=False),
        )

        from h2track_web.web.auth import create_auth_dependency

        auth_dep = create_auth_dependency()

        app = FastAPI()

        @app.post("/protected")
        async def protected(auth: str = auth_dep):
            return {"ok": True}

        client = TestClient(app)
        # Request without any API key header
        response = client.post("/protected")
        assert response.status_code == 200
