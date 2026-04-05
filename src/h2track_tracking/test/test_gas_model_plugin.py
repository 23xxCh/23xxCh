"""Tests for the gas model plugin architecture."""

import math
import random

import pytest

from h2track_tracking.gas_model import GasFieldParams, Pose2D
from h2track_tracking.gas_model_plugin import (
    GadenGasModelPlugin,
    GasModelMetadata,
    GasModelPlugin,
    GasModelRegistry,
    register_builtin_plugins,
    SimplifiedGasModelPlugin,
)


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the registry before and after each test."""
    GasModelRegistry.clear()
    yield
    GasModelRegistry.clear()


def make_default_params() -> GasFieldParams:
    """Create default gas field parameters for testing."""
    return GasFieldParams(
        source_x=0.0,
        source_y=0.0,
        source_strength=100.0,
        decay_rate=0.5,
        plume_stddev=1.0,
        wind_x=0.0,
        wind_y=0.0,
        noise_stddev=0.0,
        min_concentration=0.0,
    )


class TestGasModelMetadata:
    """Tests for GasModelMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating metadata with all fields."""
        metadata = GasModelMetadata(
            name="test",
            version="1.0.0",
            description="Test plugin",
            supports_3d=True,
            supports_wind=False,
            author="Test Author",
        )
        assert metadata.name == "test"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test plugin"
        assert metadata.supports_3d is True
        assert metadata.supports_wind is False
        assert metadata.author == "Test Author"

    def test_metadata_defaults(self):
        """Test metadata default values."""
        metadata = GasModelMetadata(
            name="test",
            version="1.0.0",
            description="Test plugin",
        )
        assert metadata.supports_3d is False
        assert metadata.supports_wind is True
        assert metadata.author == ""

    def test_metadata_is_frozen(self):
        """Test that metadata is immutable."""
        metadata = GasModelMetadata(name="test", version="1.0.0", description="Test")
        with pytest.raises(AttributeError):
            metadata.name = "changed"  # type: ignore


class TestGasModelRegistry:
    """Tests for GasModelRegistry class."""

    def test_register_plugin(self):
        """Test registering a plugin."""

        class DummyPlugin(GasModelPlugin):
            def get_concentration(self, x: float, y: float, z: float = 0.0) -> float:
                return 1.0

            def get_name(self) -> str:
                return "dummy"

            def get_metadata(self) -> GasModelMetadata:
                return GasModelMetadata(
                    name="dummy", version="1.0.0", description="Dummy"
                )

        plugin = DummyPlugin()
        GasModelRegistry.register(plugin)

        assert "dummy" in GasModelRegistry.list_plugins()
        assert GasModelRegistry.get("dummy") is plugin

    def test_register_duplicate_raises(self):
        """Test that registering duplicate names raises error."""

        class DummyPlugin(GasModelPlugin):
            def get_concentration(self, x: float, y: float, z: float = 0.0) -> float:
                return 1.0

            def get_name(self) -> str:
                return "duplicate"

            def get_metadata(self) -> GasModelMetadata:
                return GasModelMetadata(
                    name="duplicate", version="1.0.0", description="Dummy"
                )

        GasModelRegistry.register(DummyPlugin())

        with pytest.raises(ValueError, match="already registered"):
            GasModelRegistry.register(DummyPlugin())

    def test_get_nonexistent_returns_none(self):
        """Test getting nonexistent plugin returns None."""
        assert GasModelRegistry.get("nonexistent") is None

    def test_unregister_existing(self):
        """Test unregistering an existing plugin."""

        class DummyPlugin(GasModelPlugin):
            def get_concentration(self, x: float, y: float, z: float = 0.0) -> float:
                return 1.0

            def get_name(self) -> str:
                return "to_remove"

            def get_metadata(self) -> GasModelMetadata:
                return GasModelMetadata(
                    name="to_remove", version="1.0.0", description="Dummy"
                )

        GasModelRegistry.register(DummyPlugin())
        result = GasModelRegistry.unregister("to_remove")

        assert result is True
        assert GasModelRegistry.get("to_remove") is None

    def test_unregister_nonexistent(self):
        """Test unregistering nonexistent plugin returns False."""
        result = GasModelRegistry.unregister("nonexistent")
        assert result is False

    def test_clear_removes_all(self):
        """Test clearing all plugins."""

        class Plugin1(GasModelPlugin):
            def get_concentration(self, x: float, y: float, z: float = 0.0) -> float:
                return 1.0

            def get_name(self) -> str:
                return "plugin1"

            def get_metadata(self) -> GasModelMetadata:
                return GasModelMetadata(
                    name="plugin1", version="1.0.0", description="Plugin 1"
                )

        class Plugin2(GasModelPlugin):
            def get_concentration(self, x: float, y: float, z: float = 0.0) -> float:
                return 2.0

            def get_name(self) -> str:
                return "plugin2"

            def get_metadata(self) -> GasModelMetadata:
                return GasModelMetadata(
                    name="plugin2", version="1.0.0", description="Plugin 2"
                )

        GasModelRegistry.register(Plugin1())
        GasModelRegistry.register(Plugin2())
        GasModelRegistry.clear()

        assert GasModelRegistry.list_plugins() == []

    def test_list_plugins_returns_names(self):
        """Test that list_plugins returns all registered names."""

        class PluginA(GasModelPlugin):
            def get_concentration(self, x: float, y: float, z: float = 0.0) -> float:
                return 1.0

            def get_name(self) -> str:
                return "plugin_a"

            def get_metadata(self) -> GasModelMetadata:
                return GasModelMetadata(
                    name="plugin_a", version="1.0.0", description="A"
                )

        class PluginB(GasModelPlugin):
            def get_concentration(self, x: float, y: float, z: float = 0.0) -> float:
                return 2.0

            def get_name(self) -> str:
                return "plugin_b"

            def get_metadata(self) -> GasModelMetadata:
                return GasModelMetadata(
                    name="plugin_b", version="1.0.0", description="B"
                )

        GasModelRegistry.register(PluginA())
        GasModelRegistry.register(PluginB())

        names = GasModelRegistry.list_plugins()
        assert set(names) == {"plugin_a", "plugin_b"}


class TestSimplifiedGasModelPlugin:
    """Tests for SimplifiedGasModelPlugin."""

    def test_plugin_name(self):
        """Test plugin name constant."""
        assert SimplifiedGasModelPlugin.PLUGIN_NAME == "simplified"

    def test_get_concentration(self):
        """Test concentration calculation."""
        params = GasFieldParams(
            source_x=0.0,
            source_y=0.0,
            source_strength=100.0,
            decay_rate=0.5,
            plume_stddev=1.0,
            wind_x=0.0,
            wind_y=0.0,
            noise_stddev=0.0,
            min_concentration=0.0,
        )
        plugin = SimplifiedGasModelPlugin(params, random.Random(42))

        # Near source should have higher concentration
        near = plugin.get_concentration(0.1, 0.1)
        far = plugin.get_concentration(5.0, 5.0)

        assert near > far
        assert near > 0
        assert far >= 0

    def test_get_concentration_2d(self):
        """Test 2D convenience method."""
        params = make_default_params()
        plugin = SimplifiedGasModelPlugin(params, random.Random(42))

        pose = Pose2D(1.0, 1.0)
        concentration_2d = plugin.get_concentration_2d(pose)
        concentration_3d = plugin.get_concentration(1.0, 1.0, 0.0)

        assert concentration_2d == concentration_3d

    def test_get_name(self):
        """Test plugin name method."""
        plugin = SimplifiedGasModelPlugin(make_default_params())
        assert plugin.get_name() == "simplified"

    def test_get_metadata(self):
        """Test plugin metadata."""
        plugin = SimplifiedGasModelPlugin(make_default_params())
        metadata = plugin.get_metadata()

        assert metadata.name == "simplified"
        assert metadata.version == "1.0.0"
        assert metadata.supports_wind is True
        assert metadata.supports_3d is False

    def test_get_params(self):
        """Test getting parameters."""
        params = make_default_params()
        plugin = SimplifiedGasModelPlugin(params)

        assert plugin.get_params() is params

    def test_next_search_target(self):
        """Test search target calculation."""
        params = GasFieldParams(
            source_x=2.0,
            source_y=2.0,
            source_strength=100.0,
            decay_rate=0.4,
            plume_stddev=1.0,
            wind_x=0.0,
            wind_y=0.0,
            noise_stddev=0.0,
            min_concentration=0.0,
        )
        plugin = SimplifiedGasModelPlugin(params)
        history = [
            (Pose2D(0.0, 0.0), 3.0),
            (Pose2D(0.6, 0.0), 2.0),
        ]

        target = plugin.next_search_target(
            current_pose=Pose2D(0.6, 0.0),
            current_yaw=0.0,
            history=history,
            step_size=0.5,
            sweep_angle=math.pi / 6.0,
        )

        assert target.x > 0.6
        assert target.y != 0.0

    def test_reproducible_with_same_rng(self):
        """Test that same RNG seed produces same results."""
        params = make_default_params()

        plugin1 = SimplifiedGasModelPlugin(params, random.Random(42))
        plugin2 = SimplifiedGasModelPlugin(params, random.Random(42))

        # With noise, results should be identical with same seed
        noisy_params = GasFieldParams(
            source_x=0.0,
            source_y=0.0,
            source_strength=100.0,
            decay_rate=0.5,
            plume_stddev=1.0,
            wind_x=0.0,
            wind_y=0.0,
            noise_stddev=0.5,
            min_concentration=0.0,
        )
        plugin3 = SimplifiedGasModelPlugin(noisy_params, random.Random(42))
        plugin4 = SimplifiedGasModelPlugin(noisy_params, random.Random(42))

        c1 = plugin3.get_concentration(1.0, 1.0)
        c2 = plugin4.get_concentration(1.0, 1.0)

        assert c1 == c2


class TestGadenGasModelPlugin:
    """Tests for GadenGasModelPlugin."""

    def test_plugin_name(self):
        """Test plugin name constant."""
        assert GadenGasModelPlugin.PLUGIN_NAME == "gaden"

    def test_with_concentration_provider(self):
        """Test using a concentration provider."""

        def provider(x: float, y: float, z: float) -> float:
            return x + y + z

        plugin = GadenGasModelPlugin(concentration_provider=provider)

        assert plugin.get_concentration(1.0, 2.0, 3.0) == 6.0
        assert plugin.is_gaden_available() is True

    def test_with_fallback(self):
        """Test using fallback simplified model."""
        params = make_default_params()
        plugin = GadenGasModelPlugin(fallback_params=params)

        assert plugin.has_fallback() is True
        assert plugin.is_gaden_available() is False

        # Should use fallback
        concentration = plugin.get_concentration(0.0, 0.0)
        assert concentration > 0

    def test_without_provider_or_fallback_raises(self):
        """Test that no provider or fallback raises error."""
        plugin = GadenGasModelPlugin()

        with pytest.raises(RuntimeError, match="not available"):
            plugin.get_concentration(0.0, 0.0)

    def test_get_name(self):
        """Test plugin name method."""
        plugin = GadenGasModelPlugin(fallback_params=make_default_params())
        assert plugin.get_name() == "gaden"

    def test_get_metadata(self):
        """Test plugin metadata."""
        plugin = GadenGasModelPlugin(fallback_params=make_default_params())
        metadata = plugin.get_metadata()

        assert metadata.name == "gaden"
        assert metadata.version == "1.0.0"
        assert metadata.supports_wind is True
        assert metadata.supports_3d is True

    def test_provider_exception_falls_back(self):
        """Test that provider exceptions fall back gracefully."""

        def failing_provider(x: float, y: float, z: float) -> float:
            raise RuntimeError("GADEN unavailable")

        params = make_default_params()
        plugin = GadenGasModelPlugin(
            concentration_provider=failing_provider, fallback_params=params
        )

        # Should not raise, should use fallback
        concentration = plugin.get_concentration(0.0, 0.0)
        assert concentration >= 0


class TestRegisterBuiltinPlugins:
    """Tests for register_builtin_plugins function."""

    def test_registers_both_plugins(self):
        """Test that both built-in plugins are registered."""
        register_builtin_plugins()

        names = GasModelRegistry.list_plugins()
        assert "simplified" in names
        assert "gaden" in names

    def test_with_custom_params(self):
        """Test registration with custom parameters."""
        params = GasFieldParams(
            source_x=5.0,
            source_y=5.0,
            source_strength=200.0,
            decay_rate=0.3,
            plume_stddev=2.0,
            wind_x=1.0,
            wind_y=0.0,
            noise_stddev=0.1,
            min_concentration=0.01,
        )
        register_builtin_plugins(params)

        simplified = GasModelRegistry.get("simplified")
        assert simplified is not None
        assert isinstance(simplified, SimplifiedGasModelPlugin)

        # Check that custom params are used
        plugin_params = simplified.get_params()
        assert plugin_params.source_x == 5.0
        assert plugin_params.source_strength == 200.0

    def test_default_params(self):
        """Test registration with default parameters."""
        register_builtin_plugins()

        simplified = GasModelRegistry.get("simplified")
        assert simplified is not None

        params = simplified.get_params()
        assert params.source_x == 0.0
        assert params.source_y == 0.0
        assert params.source_strength == 100.0


class TestPluginIntegration:
    """Integration tests for the plugin system."""

    def test_swap_plugins_at_runtime(self):
        """Test swapping plugins at runtime."""
        params = make_default_params()

        # Register simplified plugin
        simplified = SimplifiedGasModelPlugin(params)
        GasModelRegistry.register(simplified)

        # Get and use simplified
        plugin = GasModelRegistry.get("simplified")
        assert plugin is not None
        c1 = plugin.get_concentration(0.0, 0.0)

        # Unregister and register gaden
        GasModelRegistry.unregister("simplified")
        gaden = GadenGasModelPlugin(fallback_params=params)
        GasModelRegistry.register(gaden)

        # Get and use gaden
        plugin = GasModelRegistry.get("gaden")
        assert plugin is not None
        c2 = plugin.get_concentration(0.0, 0.0)

        # Both should return valid concentrations
        assert c1 > 0
        assert c2 > 0

    def test_custom_plugin(self):
        """Test registering a custom plugin."""

        class CustomGasPlugin(GasModelPlugin):
            PLUGIN_NAME = "custom"

            def __init__(self, scale: float = 1.0):
                self._scale = scale

            def get_concentration(self, x: float, y: float, z: float = 0.0) -> float:
                distance = (x**2 + y**2 + z**2) ** 0.5
                return self._scale / (distance + 1.0)

            def get_name(self) -> str:
                return self.PLUGIN_NAME

            def get_metadata(self) -> GasModelMetadata:
                return GasModelMetadata(
                    name=self.PLUGIN_NAME,
                    version="0.1.0",
                    description="Custom inverse-distance model",
                    supports_3d=True,
                )

        custom = CustomGasPlugin(scale=50.0)
        GasModelRegistry.register(custom)

        plugin = GasModelRegistry.get("custom")
        assert plugin is not None
        assert plugin.get_concentration(0.0, 0.0) == 50.0
        assert plugin.get_concentration(3.0, 4.0) == 50.0 / 6.0  # distance = 5, 5+1=6

    def test_plugin_metadata_capabilities(self):
        """Test querying plugin capabilities via metadata."""
        params = make_default_params()

        simplified = SimplifiedGasModelPlugin(params)
        gaden = GadenGasModelPlugin(fallback_params=params)

        # Simplified doesn't support 3D
        assert simplified.get_metadata().supports_3d is False

        # GADEN supports 3D
        assert gaden.get_metadata().supports_3d is True

        # Both support wind
        assert simplified.get_metadata().supports_wind is True
        assert gaden.get_metadata().supports_wind is True
