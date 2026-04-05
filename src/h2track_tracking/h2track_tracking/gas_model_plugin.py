"""Plugin architecture for gas models.

This module provides an abstract base class for gas model plugins and a registry
for managing them. This enables swapping simulation backends without changing
downstream code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import random
from typing import Any

from h2track_tracking.gas_model import GasFieldModel, GasFieldParams, Pose2D


@dataclass(frozen=True)
class GasModelMetadata:
    """Metadata for a gas model plugin."""

    name: str
    version: str
    description: str
    supports_3d: bool = False
    supports_wind: bool = True
    author: str = ""


class GasModelPlugin(ABC):
    """Abstract base class for gas model plugins.

    Plugins must implement the concentration calculation and provide metadata.
    This enables different gas simulation backends to be swapped transparently.
    """

    @abstractmethod
    def get_concentration(self, x: float, y: float, z: float = 0.0) -> float:
        """Get gas concentration at a 3D position.

        Args:
            x: X coordinate in meters
            y: Y coordinate in meters
            z: Z coordinate in meters (height, default 0.0)

        Returns:
            Gas concentration (units depend on the model implementation)
        """
        ...

    @abstractmethod
    def get_name(self) -> str:
        """Get the plugin name.

        Returns:
            Unique identifier for this plugin
        """
        ...

    @abstractmethod
    def get_metadata(self) -> GasModelMetadata:
        """Get plugin metadata.

        Returns:
            Metadata describing the plugin's capabilities
        """
        ...

    def get_concentration_2d(self, pose: Pose2D) -> float:
        """Get gas concentration at a 2D position.

        Convenience method that delegates to get_concentration.

        Args:
            pose: 2D position

        Returns:
            Gas concentration at the position
        """
        return self.get_concentration(pose.x, pose.y, 0.0)


class GasModelRegistry:
    """Registry for gas model plugins.

    Plugins can be registered and retrieved by name. The registry is a singleton
    pattern using class methods and class-level storage.
    """

    _plugins: dict[str, GasModelPlugin] = {}

    @classmethod
    def register(cls, plugin: GasModelPlugin) -> None:
        """Register a gas model plugin.

        Args:
            plugin: The plugin instance to register

        Raises:
            ValueError: If a plugin with the same name is already registered
        """
        name = plugin.get_name()
        if name in cls._plugins:
            raise ValueError(f"Plugin '{name}' is already registered")
        cls._plugins[name] = plugin

    @classmethod
    def get(cls, name: str) -> GasModelPlugin | None:
        """Get a registered plugin by name.

        Args:
            name: The plugin name

        Returns:
            The plugin instance, or None if not found
        """
        return cls._plugins.get(name)

    @classmethod
    def list_plugins(cls) -> list[str]:
        """List all registered plugin names.

        Returns:
            List of plugin names
        """
        return list(cls._plugins.keys())

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Remove a plugin from the registry.

        Args:
            name: The plugin name to remove

        Returns:
            True if the plugin was removed, False if it wasn't registered
        """
        if name in cls._plugins:
            del cls._plugins[name]
            return True
        return False

    @classmethod
    def clear(cls) -> None:
        """Clear all registered plugins.

        Useful for testing to reset state between tests.
        """
        cls._plugins.clear()


class SimplifiedGasModelPlugin(GasModelPlugin):
    """Plugin wrapping the simplified GasFieldModel.

    This is the default gas model that uses analytical plume equations
    with wind bias and noise.
    """

    PLUGIN_NAME = "simplified"

    def __init__(self, params: GasFieldParams, rng: random.Random | None = None) -> None:
        """Initialize the simplified gas model plugin.

        Args:
            params: Gas field parameters
            rng: Optional random number generator for reproducibility
        """
        self._model = GasFieldModel(params, rng)
        self._params = params

    def get_concentration(self, x: float, y: float, z: float = 0.0) -> float:
        """Get gas concentration at a 3D position.

        Note: The simplified model ignores the z-coordinate.

        Args:
            x: X coordinate in meters
            y: Y coordinate in meters
            z: Z coordinate in meters (ignored)

        Returns:
            Gas concentration
        """
        return self._model.concentration_at(Pose2D(x, y))

    def get_name(self) -> str:
        """Get the plugin name."""
        return self.PLUGIN_NAME

    def get_metadata(self) -> GasModelMetadata:
        """Get plugin metadata."""
        return GasModelMetadata(
            name=self.PLUGIN_NAME,
            version="1.0.0",
            description="Simplified analytical gas plume model with wind bias",
            supports_3d=False,
            supports_wind=True,
            author="h2track",
        )

    def get_params(self) -> GasFieldParams:
        """Get the gas field parameters.

        Returns:
            The parameters used by this model
        """
        return self._params

    def next_search_target(
        self,
        current_pose: Pose2D,
        current_yaw: float,
        history: list[tuple[Pose2D, float]],
        step_size: float,
        sweep_angle: float,
    ) -> Pose2D:
        """Calculate the next search position based on gradient ascent.

        Args:
            current_pose: Current robot position
            current_yaw: Current robot heading in radians
            history: List of (position, concentration) tuples
            step_size: Distance to move in meters
            sweep_angle: Angle to turn when concentration drops

        Returns:
            Target position for next step
        """
        return self._model.next_search_target(
            current_pose, current_yaw, history, step_size, sweep_angle
        )


class GadenGasModelPlugin(GasModelPlugin):
    """Plugin for GADEN gas simulation backend.

    This plugin wraps the GADEN (GAs Dispersion and detectioN) simulator
    which provides realistic filament-based gas dispersion.

    Note: This requires GADEN to be installed and configured. The plugin
    provides a fallback to simplified model if GADEN is unavailable.
    """

    PLUGIN_NAME = "gaden"

    def __init__(
        self,
        concentration_provider: Any = None,
        fallback_params: GasFieldParams | None = None,
        rng: random.Random | None = None,
    ) -> None:
        """Initialize the GADEN gas model plugin.

        Args:
            concentration_provider: Optional callable that takes (x, y, z) and
                returns concentration. This would typically be a ROS node that
                subscribes to GADEN sensor data.
            fallback_params: Parameters for simplified fallback model if
                concentration_provider is not available.
            rng: Optional random number generator for fallback model
        """
        self._concentration_provider = concentration_provider
        self._fallback: SimplifiedGasModelPlugin | None = None
        if fallback_params is not None:
            self._fallback = SimplifiedGasModelPlugin(fallback_params, rng)

    def get_concentration(self, x: float, y: float, z: float = 0.0) -> float:
        """Get gas concentration at a 3D position.

        Uses the concentration provider if available, otherwise falls back
        to the simplified model.

        Args:
            x: X coordinate in meters
            y: Y coordinate in meters
            z: Z coordinate in meters (height)

        Returns:
            Gas concentration
        """
        if self._concentration_provider is not None:
            try:
                return float(self._concentration_provider(x, y, z))
            except Exception:
                # Fall back on error
                pass

        if self._fallback is not None:
            return self._fallback.get_concentration(x, y, z)

        raise RuntimeError(
            "GADEN concentration provider not available and no fallback configured"
        )

    def get_name(self) -> str:
        """Get the plugin name."""
        return self.PLUGIN_NAME

    def get_metadata(self) -> GasModelMetadata:
        """Get plugin metadata."""
        return GasModelMetadata(
            name=self.PLUGIN_NAME,
            version="1.0.0",
            description="GADEN filament-based gas dispersion simulator",
            supports_3d=True,
            supports_wind=True,
            author="GADEN Project",
        )

    def is_gaden_available(self) -> bool:
        """Check if GADEN concentration provider is available.

        Returns:
            True if GADEN is available, False otherwise
        """
        return self._concentration_provider is not None

    def has_fallback(self) -> bool:
        """Check if a fallback model is configured.

        Returns:
            True if fallback is available
        """
        return self._fallback is not None


def register_builtin_plugins(params: GasFieldParams | None = None) -> None:
    """Register the built-in gas model plugins.

    Args:
        params: Optional parameters for the simplified model. If not provided,
            uses default parameters.
    """
    if params is None:
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

    simplified = SimplifiedGasModelPlugin(params)
    GasModelRegistry.register(simplified)

    gaden = GadenGasModelPlugin(fallback_params=params)
    GasModelRegistry.register(gaden)
