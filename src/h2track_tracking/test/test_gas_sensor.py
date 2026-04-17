"""Tests for gas sensor node."""

import pytest
from unittest.mock import MagicMock, patch

from h2track_tracking.gas_types import GasType, get_gas_properties


class TestGasSensorNodeSimulation:
    """Tests for gas sensor node in simulation mode."""

    def test_gas_type_loading(self) -> None:
        """Test gas type is correctly loaded."""
        props = get_gas_properties(GasType.HYDROGEN)
        assert props.name == "Hydrogen"
        assert props.alarm_threshold == 250.0

    def test_methane_gas_properties(self) -> None:
        """Test methane gas properties."""
        props = get_gas_properties(GasType.METHANE)
        assert props.name == "Methane"
        assert props.density_ratio < 1.0  # Lighter than air

    def test_propane_gas_properties(self) -> None:
        """Test propane gas properties."""
        props = get_gas_properties(GasType.PROPANE)
        assert props.name == "Propane"
        assert props.density_ratio > 1.0  # Heavier than air

    def test_co_gas_properties(self) -> None:
        """Test carbon monoxide gas properties."""
        props = get_gas_properties(GasType.CARBON_MONOXIDE)
        assert props.name == "Carbon Monoxide"
        assert 0.8 < props.density_ratio < 1.2  # Near neutral


class TestGasSensorThresholds:
    """Tests for gas sensor alarm thresholds."""

    def test_hydrogen_alarm_threshold(self) -> None:
        """Test hydrogen alarm threshold."""
        props = get_gas_properties(GasType.HYDROGEN)
        assert props.alarm_threshold == 250.0

    def test_methane_alarm_threshold(self) -> None:
        """Test methane alarm threshold."""
        props = get_gas_properties(GasType.METHANE)
        assert props.alarm_threshold == 5000.0

    def test_co_alarm_threshold(self) -> None:
        """Test CO alarm threshold."""
        props = get_gas_properties(GasType.CARBON_MONOXIDE)
        assert props.alarm_threshold == 50.0

    def test_propane_alarm_threshold(self) -> None:
        """Test propane alarm threshold."""
        props = get_gas_properties(GasType.PROPANE)
        assert props.alarm_threshold == 1000.0


class TestGasSensorHeight:
    """Tests for gas sensor mounting height."""

    def test_rising_gas_sensor_elevated(self) -> None:
        """Test rising gases need elevated sensor."""
        h2_height = get_gas_properties(GasType.HYDROGEN).sensor_height
        ch4_height = get_gas_properties(GasType.METHANE).sensor_height
        assert h2_height > 1.0
        assert ch4_height > 1.0

    def test_sinking_gas_sensor_low(self) -> None:
        """Test sinking gases need low sensor."""
        propane_height = get_gas_properties(GasType.PROPANE).sensor_height
        assert propane_height < 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
