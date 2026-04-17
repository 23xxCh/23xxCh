"""Tests for multi-gas support."""

import pytest

from h2track_tracking.gas_types import (
    GasType,
    GasProperties,
    GAS_PROPERTIES,
    get_gas_properties,
    get_sensor_height,
    get_gas_behavior,
)


class TestGasType:
    """Tests for GasType enum."""

    def test_hydrogen_exists(self) -> None:
        """Test HYDROGEN gas type exists."""
        assert GasType.HYDROGEN.value == "H2"

    def test_methane_exists(self) -> None:
        """Test METHANE gas type exists."""
        assert GasType.METHANE.value == "CH4"

    def test_carbon_monoxide_exists(self) -> None:
        """Test CARBON_MONOXIDE gas type exists."""
        assert GasType.CARBON_MONOXIDE.value == "CO"

    def test_propane_exists(self) -> None:
        """Test PROPANE gas type exists."""
        assert GasType.PROPANE.value == "C3H8"


class TestGasProperties:
    """Tests for GasProperties dataclass."""

    def test_hydrogen_properties(self) -> None:
        """Test hydrogen gas properties."""
        props = GAS_PROPERTIES[GasType.HYDROGEN]
        assert props.name == "Hydrogen"
        assert props.molecular_weight == pytest.approx(2.016)
        assert props.density_ratio < 1.0  # Lighter than air
        assert props.sensor_height > 1.0  # Elevated sensor

    def test_propane_properties(self) -> None:
        """Test propane gas properties."""
        props = GAS_PROPERTIES[GasType.PROPANE]
        assert props.name == "Propane"
        assert props.density_ratio > 1.0  # Heavier than air
        assert props.sensor_height < 0.5  # Low sensor


class TestGetGasProperties:
    """Tests for get_gas_properties function."""

    def test_get_hydrogen(self) -> None:
        """Test getting hydrogen properties."""
        props = get_gas_properties(GasType.HYDROGEN)
        assert props.name == "Hydrogen"

    def test_get_methane(self) -> None:
        """Test getting methane properties."""
        props = get_gas_properties(GasType.METHANE)
        assert props.name == "Methane"


class TestGetSensorHeight:
    """Tests for get_sensor_height function."""

    def test_hydrogen_sensor_elevated(self) -> None:
        """Test hydrogen requires elevated sensor."""
        height = get_sensor_height(GasType.HYDROGEN)
        assert height > 1.0

    def test_propane_sensor_low(self) -> None:
        """Test propane requires low sensor."""
        height = get_sensor_height(GasType.PROPANE)
        assert height < 0.5


class TestGetGasBehavior:
    """Tests for get_gas_behavior function."""

    def test_hydrogen_rising(self) -> None:
        """Test hydrogen is rising gas."""
        behavior = get_gas_behavior(GasType.HYDROGEN)
        assert behavior == "rising"

    def test_propane_sinking(self) -> None:
        """Test propane is sinking gas."""
        behavior = get_gas_behavior(GasType.PROPANE)
        assert behavior == "sinking"

    def test_co_neutral(self) -> None:
        """Test CO is neutral buoyancy."""
        behavior = get_gas_behavior(GasType.CARBON_MONOXIDE)
        assert behavior == "neutral"


class TestGasDensityComparison:
    """Tests comparing gas densities."""

    def test_hydrogen_lightest(self) -> None:
        """Test hydrogen is lighter than methane."""
        h2 = GAS_PROPERTIES[GasType.HYDROGEN]
        ch4 = GAS_PROPERTIES[GasType.METHANE]
        assert h2.density_ratio < ch4.density_ratio

    def test_propane_heaviest(self) -> None:
        """Test propane is heaviest of supported gases."""
        propane = GAS_PROPERTIES[GasType.PROPANE]
        for gas_type in [GasType.HYDROGEN, GasType.METHANE, GasType.CARBON_MONOXIDE]:
            assert propane.density_ratio > GAS_PROPERTIES[gas_type].density_ratio
