"""Tests for LlmProfileStore."""

from pathlib import Path
import threading

import pytest

# Will import from the new module location
from h2track_web.llm.profile_store import LlmProfileStore


class TestLlmProfileStoreInit:
    """Tests for LlmProfileStore initialization."""

    def test_default_path(self):
        """Test default path is set correctly."""
        store = LlmProfileStore()
        assert store.path.name == "llm_profiles.json"
        assert ".config" in str(store.path)
        assert "h2track" in str(store.path)

    def test_custom_path(self, tmp_path):
        """Test custom path is used."""
        custom_path = tmp_path / "custom_profiles.json"
        store = LlmProfileStore(path=custom_path)
        assert store.path == custom_path

    def test_path_property_returns_path_object(self, tmp_path):
        """Test path property returns a Path object."""
        store = LlmProfileStore(path=tmp_path / "test.json")
        assert isinstance(store.path, Path)


class TestLlmProfileStoreEmpty:
    """Tests for empty store behavior."""

    def test_list_profiles_empty(self, tmp_path):
        """Test listing profiles when none exist."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        result = store.list_profiles()
        assert result["active_profile_id"] is None
        assert result["profiles"] == []
        assert str(tmp_path / "profiles.json") == result["path"]

    def test_get_profile_raises_when_empty(self, tmp_path):
        """Test get_profile raises when no profiles exist."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        with pytest.raises(ValueError, match="no llm profile configured"):
            store.get_profile()


class TestLlmProfileStoreSave:
    """Tests for save_profile method."""

    def test_save_profile_basic(self, tmp_path):
        """Test saving a basic profile."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        saved = store.save_profile(
            {
                "name": "test-profile",
                "base_url": "http://localhost:8000",
                "api_key": "test-key-12345678",
                "model": "gpt-4",
            }
        )
        assert saved["name"] == "test-profile"
        assert saved["has_api_key"] is True
        assert saved["api_key_preview"] == "***5678"
        assert "id" in saved  # ID is included in public profile
        assert "api_key" not in saved  # But api_key is masked

    def test_save_profile_sets_first_as_active(self, tmp_path):
        """Test first saved profile becomes active automatically."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        store.save_profile(
            {
                "name": "first",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
            }
        )
        result = store.list_profiles()
        assert result["active_profile_id"] is not None

    def test_save_profile_set_active_flag(self, tmp_path):
        """Test set_active flag makes profile active."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        # Save first profile
        store.save_profile(
            {
                "name": "first",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
            }
        )
        # Save second with set_active=True
        second = store.save_profile(
            {
                "name": "second",
                "base_url": "http://localhost:8001",
                "api_key": "key2",
                "model": "model2",
                "set_active": True,
            }
        )
        result = store.list_profiles()
        assert result["active_profile_id"] == second["id"]

    def test_save_profile_updates_existing(self, tmp_path):
        """Test saving with existing ID updates the profile."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        first = store.save_profile(
            {
                "name": "original",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
            }
        )
        profile_id = first["id"]

        # Update with same ID
        updated = store.save_profile(
            {
                "id": profile_id,
                "name": "updated",
                "base_url": "http://localhost:9000",
                "api_key": "key2",
                "model": "model2",
            }
        )
        assert updated["id"] == profile_id
        assert updated["name"] == "updated"

        # Should still have only 1 profile
        result = store.list_profiles()
        assert len(result["profiles"]) == 1

    def test_save_profile_preserves_created_at(self, tmp_path):
        """Test created_at is preserved on update."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        first = store.save_profile(
            {
                "name": "original",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
            }
        )

        # Get the raw profile to check created_at
        raw = store.get_profile()
        original_created = raw.get("created_at")

        # Update
        store.save_profile(
            {
                "id": raw["id"],
                "name": "updated",
                "base_url": "http://localhost:9000",
                "api_key": "key2",
                "model": "model2",
            }
        )

        updated_raw = store.get_profile()
        assert updated_raw.get("created_at") == original_created

    def test_save_profile_requires_base_url(self, tmp_path):
        """Test save_profile requires base_url."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        with pytest.raises(ValueError, match="base_url is required"):
            store.save_profile({"name": "x", "api_key": "key", "model": "m"})

    def test_save_profile_requires_model(self, tmp_path):
        """Test save_profile requires model."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        with pytest.raises(ValueError, match="model is required"):
            store.save_profile(
                {"name": "x", "api_key": "key", "base_url": "http://localhost:8000"}
            )

    def test_save_profile_requires_api_key(self, tmp_path):
        """Test save_profile requires api_key."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        with pytest.raises(ValueError, match="api_key is required"):
            store.save_profile(
                {"name": "x", "model": "m", "base_url": "http://localhost:8000"}
            )

    def test_save_profile_normalizes_protocol(self, tmp_path):
        """Test protocol is normalized to valid values."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        store.save_profile(
            {
                "name": "test",
                "base_url": "http://localhost:8000",
                "api_key": "key",
                "model": "m",
                "protocol": "INVALID",
            }
        )
        raw = store.get_profile()
        assert raw["protocol"] == "chat"  # Falls back to default

    def test_save_profile_generates_uuid_if_missing(self, tmp_path):
        """Test profile ID is generated if not provided."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        saved = store.save_profile(
            {
                "name": "test",
                "base_url": "http://localhost:8000",
                "api_key": "key",
                "model": "m",
            }
        )
        assert saved["id"] is not None
        assert len(saved["id"]) == 36  # UUID format


class TestLlmProfileStoreGet:
    """Tests for get_profile method."""

    def test_get_profile_returns_active(self, tmp_path):
        """Test get_profile returns active profile by default."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        store.save_profile(
            {
                "name": "first",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
                "set_active": True,
            }
        )
        store.save_profile(
            {
                "name": "second",
                "base_url": "http://localhost:8001",
                "api_key": "key2",
                "model": "model2",
            }
        )
        profile = store.get_profile()
        assert profile["name"] == "first"

    def test_get_profile_by_id(self, tmp_path):
        """Test get_profile returns specific profile by ID."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        first = store.save_profile(
            {
                "name": "first",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
            }
        )
        second = store.save_profile(
            {
                "name": "second",
                "base_url": "http://localhost:8001",
                "api_key": "key2",
                "model": "model2",
                "set_active": True,
            }
        )
        profile = store.get_profile(profile_id=first["id"])
        assert profile["name"] == "first"

    def test_get_profile_returns_first_if_no_active(self, tmp_path):
        """Test get_profile returns first profile if no active set."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        # Save directly without setting active
        store.save_profile(
            {
                "name": "first",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
            }
        )
        profile = store.get_profile()
        assert profile["name"] == "first"


class TestLlmProfileStoreActivate:
    """Tests for activate_profile method."""

    def test_activate_profile(self, tmp_path):
        """Test activating a profile."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        first = store.save_profile(
            {
                "name": "first",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
            }
        )
        second = store.save_profile(
            {
                "name": "second",
                "base_url": "http://localhost:8001",
                "api_key": "key2",
                "model": "model2",
            }
        )
        store.activate_profile(second["id"])
        result = store.list_profiles()
        assert result["active_profile_id"] == second["id"]

    def test_activate_profile_not_found(self, tmp_path):
        """Test activating non-existent profile raises."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        store.save_profile(
            {
                "name": "first",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
            }
        )
        with pytest.raises(ValueError, match="profile not found"):
            store.activate_profile("nonexistent-id")


class TestLlmProfileStoreDelete:
    """Tests for delete_profile method."""

    def test_delete_profile(self, tmp_path):
        """Test deleting a profile."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        first = store.save_profile(
            {
                "name": "first",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
            }
        )
        second = store.save_profile(
            {
                "name": "second",
                "base_url": "http://localhost:8001",
                "api_key": "key2",
                "model": "model2",
            }
        )
        store.delete_profile(second["id"])
        result = store.list_profiles()
        assert len(result["profiles"]) == 1
        assert result["profiles"][0]["id"] == first["id"]

    def test_delete_active_profile_switches_to_first(self, tmp_path):
        """Test deleting active profile switches to next available."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        first = store.save_profile(
            {
                "name": "first",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
            }
        )
        second = store.save_profile(
            {
                "name": "second",
                "base_url": "http://localhost:8001",
                "api_key": "key2",
                "model": "model2",
                "set_active": True,
            }
        )
        store.delete_profile(second["id"])
        result = store.list_profiles()
        assert result["active_profile_id"] == first["id"]

    def test_delete_only_profile_clears_active(self, tmp_path):
        """Test deleting only profile clears active_profile_id."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        saved = store.save_profile(
            {
                "name": "only",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
            }
        )
        store.delete_profile(saved["id"])
        result = store.list_profiles()
        assert result["active_profile_id"] is None
        assert result["profiles"] == []

    def test_delete_profile_not_found(self, tmp_path):
        """Test deleting non-existent profile raises."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        store.save_profile(
            {
                "name": "first",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
            }
        )
        with pytest.raises(ValueError, match="profile not found"):
            store.delete_profile("nonexistent-id")


class TestLlmProfileStoreThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_saves(self, tmp_path):
        """Test concurrent saves don't corrupt data."""
        store = LlmProfileStore(path=tmp_path / "profiles.json")
        errors = []
        saved_ids = []

        def save_profile(index):
            try:
                result = store.save_profile(
                    {
                        "name": f"profile-{index}",
                        "base_url": f"http://localhost:800{index % 10}",
                        "api_key": f"key-{index}",
                        "model": f"model-{index}",
                    }
                )
                saved_ids.append(result["id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=save_profile, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(saved_ids) == 10
        result = store.list_profiles()
        assert len(result["profiles"]) == 10


class TestLlmProfileStorePersistence:
    """Tests for file persistence."""

    def test_persists_to_file(self, tmp_path):
        """Test profiles are persisted to file."""
        path = tmp_path / "profiles.json"
        store = LlmProfileStore(path=path)
        store.save_profile(
            {
                "name": "test",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
            }
        )
        assert path.exists()

    def test_loads_from_file(self, tmp_path):
        """Test profiles are loaded from existing file."""
        path = tmp_path / "profiles.json"
        # Create a store and save a profile
        store1 = LlmProfileStore(path=path)
        saved = store1.save_profile(
            {
                "name": "test",
                "base_url": "http://localhost:8000",
                "api_key": "key1",
                "model": "model1",
            }
        )

        # Create a new store with same path
        store2 = LlmProfileStore(path=path)
        result = store2.list_profiles()
        assert len(result["profiles"]) == 1
        assert result["profiles"][0]["id"] == saved["id"]

    def test_handles_corrupt_file(self, tmp_path):
        """Test corrupt file is handled gracefully."""
        path = tmp_path / "profiles.json"
        path.write_text("not valid json", encoding="utf-8")
        store = LlmProfileStore(path=path)
        result = store.list_profiles()
        assert result["profiles"] == []
        assert result["active_profile_id"] is None

    def test_handles_invalid_structure(self, tmp_path):
        """Test invalid JSON structure is handled gracefully."""
        path = tmp_path / "profiles.json"
        path.write_text('"just a string"', encoding="utf-8")
        store = LlmProfileStore(path=path)
        result = store.list_profiles()
        assert result["profiles"] == []
