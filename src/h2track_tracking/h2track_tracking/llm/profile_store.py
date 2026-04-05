"""LLM profile storage for managing API configurations."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any
import uuid


def _now_iso() -> str:
    """Return current UTC datetime in ISO format."""
    return datetime.now(tz=timezone.utc).isoformat()


DEFAULT_PROFILE_PATH = Path.home() / ".config" / "h2track" / "llm_profiles.json"


class LlmProfileStore:
    """Manages LLM profile configurations with file persistence.

    Profiles store API credentials and settings for connecting to LLM services.
    The store supports multiple profiles with one active at a time.

    Attributes:
        path: The file path where profiles are persisted.
    """

    def __init__(self, path: Path | None = None) -> None:
        """Initialize the profile store.

        Args:
            path: Optional custom path for the profile file.
                  Defaults to ~/.config/h2track/llm_profiles.json.
        """
        self._path = Path(path) if path else DEFAULT_PROFILE_PATH
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        """Return the path to the profile file."""
        return self._path

    def _empty_doc(self) -> dict[str, Any]:
        """Return an empty profile document structure."""
        return {"active_profile_id": None, "profiles": []}

    def _read_doc(self) -> dict[str, Any]:
        """Read and parse the profile document from file.

        Returns an empty document if the file doesn't exist or is invalid.
        """
        if not self._path.exists():
            return self._empty_doc()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return self._empty_doc()
            profiles = data.get("profiles")
            if not isinstance(profiles, list):
                data["profiles"] = []
            if "active_profile_id" not in data:
                data["active_profile_id"] = None
            return data
        except Exception:
            return self._empty_doc()

    def _write_doc(self, doc: dict[str, Any]) -> None:
        """Write the profile document to file with restricted permissions."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(self._path, 0o600)
        except Exception:
            pass

    def _public_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Return a profile with sensitive data masked for public display.

        Args:
            profile: The full profile dictionary.

        Returns:
            A copy of the profile with api_key masked.
        """
        masked = dict(profile)
        key = str(masked.pop("api_key", "") or "")
        masked["has_api_key"] = bool(key)
        masked["api_key_preview"] = f"***{key[-4:]}" if key else ""
        return masked

    def list_profiles(self) -> dict[str, Any]:
        """List all profiles with sensitive data masked.

        Returns:
            A dictionary containing:
                - active_profile_id: The ID of the active profile, or None.
                - profiles: List of profiles with masked API keys.
                - path: The file path string.
        """
        with self._lock:
            doc = self._read_doc()
            return {
                "active_profile_id": doc.get("active_profile_id"),
                "profiles": [self._public_profile(p) for p in doc.get("profiles", []) if isinstance(p, dict)],
                "path": str(self._path),
            }

    def get_profile(self, profile_id: str | None = None) -> dict[str, Any]:
        """Get a profile by ID or the active/default profile.

        Args:
            profile_id: Optional specific profile ID to retrieve.
                        If None, returns the active profile or first available.

        Returns:
            The profile dictionary with full API key.

        Raises:
            ValueError: If no profiles are configured.
        """
        with self._lock:
            doc = self._read_doc()
            profiles = [p for p in doc.get("profiles", []) if isinstance(p, dict)]
            selected_id = profile_id or doc.get("active_profile_id")
            if selected_id:
                for p in profiles:
                    if p.get("id") == selected_id:
                        return dict(p)
            if profiles:
                return dict(profiles[0])
            raise ValueError("no llm profile configured")

    def save_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Save or update a profile.

        Args:
            payload: Profile data containing:
                - id: Optional profile ID (auto-generated if missing).
                - name: Profile name (defaults to "default").
                - base_url: Required API base URL.
                - api_key: Required API key.
                - model: Required model name.
                - protocol: Optional protocol ("chat", "responses", "dual").
                - timeout_sec: Optional timeout in seconds.
                - headers: Optional extra headers dict.
                - set_active: If True, makes this profile active.

        Returns:
            The saved profile with masked API key.

        Raises:
            ValueError: If required fields are missing.
        """
        with self._lock:
            doc = self._read_doc()
            profiles = [p for p in doc.get("profiles", []) if isinstance(p, dict)]
            profile_id = str(payload.get("id") or "").strip() or str(uuid.uuid4())
            now = _now_iso()
            new_profile = {
                "id": profile_id,
                "name": str(payload.get("name") or "default").strip() or "default",
                "base_url": str(payload.get("base_url") or "").strip(),
                "api_key": str(payload.get("api_key") or "").strip(),
                "model": str(payload.get("model") or "").strip(),
                "protocol": str(payload.get("protocol") or "chat").strip().lower(),
                "timeout_sec": float(payload.get("timeout_sec") or 60.0),
                "headers": payload.get("headers") if isinstance(payload.get("headers"), dict) else {},
                "created_at": now,
                "updated_at": now,
            }
            if not new_profile["base_url"]:
                raise ValueError("base_url is required")
            if not new_profile["model"]:
                raise ValueError("model is required")
            if not new_profile["api_key"]:
                raise ValueError("api_key is required")
            if new_profile["protocol"] not in {"chat", "responses", "dual"}:
                new_profile["protocol"] = "chat"

            replaced = False
            for i, old in enumerate(profiles):
                if old.get("id") == profile_id:
                    new_profile["created_at"] = old.get("created_at", now)
                    profiles[i] = new_profile
                    replaced = True
                    break
            if not replaced:
                profiles.append(new_profile)
            doc["profiles"] = profiles
            if not doc.get("active_profile_id"):
                doc["active_profile_id"] = profile_id
            if payload.get("set_active"):
                doc["active_profile_id"] = profile_id
            self._write_doc(doc)
            return self._public_profile(new_profile)

    def activate_profile(self, profile_id: str) -> None:
        """Set a profile as the active profile.

        Args:
            profile_id: The ID of the profile to activate.

        Raises:
            ValueError: If the profile ID is not found.
        """
        with self._lock:
            doc = self._read_doc()
            if not any(p.get("id") == profile_id for p in doc.get("profiles", []) if isinstance(p, dict)):
                raise ValueError("profile not found")
            doc["active_profile_id"] = profile_id
            self._write_doc(doc)

    def delete_profile(self, profile_id: str) -> None:
        """Delete a profile by ID.

        If the deleted profile was active, the first remaining profile becomes active,
        or active_profile_id is set to None if no profiles remain.

        Args:
            profile_id: The ID of the profile to delete.

        Raises:
            ValueError: If the profile ID is not found.
        """
        with self._lock:
            doc = self._read_doc()
            profiles = [p for p in doc.get("profiles", []) if isinstance(p, dict)]
            kept = [p for p in profiles if p.get("id") != profile_id]
            if len(kept) == len(profiles):
                raise ValueError("profile not found")
            doc["profiles"] = kept
            if doc.get("active_profile_id") == profile_id:
                doc["active_profile_id"] = kept[0].get("id") if kept else None
            self._write_doc(doc)
