"""HemoSlab deterministic clinical rulebook and mathematical forecasting engine."""

from .rulebook import (
    BLOOD_GROUPS,
    COMPONENTS,
    COMPONENT_SHELF_LIFE_DAYS,
    COMPONENT_SHELF_LIFE_HOURS,
    CRITICAL_THRESHOLD_HOURS,
    SAFE_THRESHOLD_HOURS,
    calculate_distance_km,
    calculate_transit_minutes,
    classify_status,
    get_compatible_donors,
    is_compatible,
)
from .math_engine import (
    compute_network_state,
    compute_zero_stock_hours,
    project_14_day_component_stock,
)

__all__ = [
    "BLOOD_GROUPS",
    "COMPONENTS",
    "COMPONENT_SHELF_LIFE_DAYS",
    "COMPONENT_SHELF_LIFE_HOURS",
    "CRITICAL_THRESHOLD_HOURS",
    "SAFE_THRESHOLD_HOURS",
    "calculate_distance_km",
    "calculate_transit_minutes",
    "classify_status",
    "get_compatible_donors",
    "is_compatible",
    "compute_network_state",
    "compute_zero_stock_hours",
    "project_14_day_component_stock",
]
