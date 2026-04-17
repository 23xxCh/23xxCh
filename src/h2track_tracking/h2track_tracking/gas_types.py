"""Gas type definitions and configurations.

Supports multiple gas types for different tracking scenarios:
- Hydrogen (H2): Lighter than air, rises quickly
- Methane (CH4): Lighter than air, moderate rise
- Carbon Monoxide (CO): Slightly lighter than air
- Propane (C3H8): Heavier than air, sinks
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class GasType(Enum):
    """Supported gas types."""
    HYDROGEN = "H2"
    METHANE = "CH4"
    CARBON_MONOXIDE = "CO"
    PROPANE = "C3H8"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class GasProperties:
    """Physical and sensing properties of a gas.
    
    Attributes:
        name: Gas name
        molecular_weight: Molecular weight (g/mol)
        density_ratio: Density ratio to air (< 1 = lighter, > 1 = heavier)
        diffusion_coefficient: Diffusion coefficient in air (cm²/s)
        typical_concentration_range: (min, max) typical concentration range
        alarm_threshold: Concentration threshold for alarm
        sensor_height: Recommended sensor height for detection (meters)
    """
    name: str
    molecular_weight: float
    density_ratio: float  # Relative to air (1.0)
    diffusion_coefficient: float
    typical_concentration_range: tuple[float, float]
    alarm_threshold: float
    sensor_height: float


# Predefined gas properties
GAS_PROPERTIES: Dict[GasType, GasProperties] = {
    GasType.HYDROGEN: GasProperties(
        name="Hydrogen",
        molecular_weight=2.016,
        density_ratio=0.069,  # Much lighter than air
        diffusion_coefficient=0.61,
        typical_concentration_range=(0.0, 100.0),
        alarm_threshold=250.0,  # ppm
        sensor_height=1.5,  # Elevated sensor for rising gas
    ),
    GasType.METHANE: GasProperties(
        name="Methane",
        molecular_weight=16.04,
        density_ratio=0.554,  # Lighter than air
        diffusion_coefficient=0.22,
        typical_concentration_range=(0.0, 100.0),
        alarm_threshold=5000.0,  # ppm
        sensor_height=1.2,
    ),
    GasType.CARBON_MONOXIDE: GasProperties(
        name="Carbon Monoxide",
        molecular_weight=28.01,
        density_ratio=0.967,  # Slightly lighter than air
        diffusion_coefficient=0.21,
        typical_concentration_range=(0.0, 500.0),
        alarm_threshold=50.0,  # ppm
        sensor_height=0.5,  # Near ground level
    ),
    GasType.PROPANE: GasProperties(
        name="Propane",
        molecular_weight=44.10,
        density_ratio=1.52,  # Heavier than air
        diffusion_coefficient=0.11,
        typical_concentration_range=(0.0, 100.0),
        alarm_threshold=1000.0,  # ppm
        sensor_height=0.3,  # Low sensor for sinking gas
    ),
}


def get_gas_properties(gas_type: GasType) -> GasProperties:
    """Get properties for a gas type."""
    return GAS_PROPERTIES.get(gas_type, GAS_PROPERTIES[GasType.HYDROGEN])


def get_sensor_height(gas_type: GasType) -> float:
    """Get recommended sensor height for a gas type.
    
    Lighter gases: sensor should be elevated
    Heavier gases: sensor should be lowered
    """
    props = get_gas_properties(gas_type)
    return props.sensor_height


def get_gas_behavior(gas_type: GasType) -> str:
    """Get behavior description for a gas.
    
    Returns:
        'rising' for lighter-than-air gases
        'sinking' for heavier-than-air gases
        'neutral' for near-neutral buoyancy
    """
    props = get_gas_properties(gas_type)
    if props.density_ratio < 0.8:
        return "rising"
    elif props.density_ratio > 1.2:
        return "sinking"
    else:
        return "neutral"
