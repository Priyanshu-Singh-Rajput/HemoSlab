"""
HemoSlab Clinical Rulebook (Pure Python, Zero LLM).

Encodes deterministic blood transfusion clinical constraints:
- Exact ABO/Rh compatibility matrices for RBCs, Platelets, and Plasma
- Component shelf-life constants (Platelets 120h, RBCs 1008h, Plasma 8760h)
- Tiered facility safety thresholds (Safe >120h, Watch 48h-120h, Critical <48h)
- Cold-chain courier distance and transit ETA geometry
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

BLOOD_GROUPS: Tuple[str, ...] = ("O-", "O+", "A+", "B+", "AB-")
ALL_ABO_RH_GROUPS: Tuple[str, ...] = ("O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+")
COMPONENTS: Tuple[str, ...] = ("RBCs", "Platelets", "Plasma")

# Real blood component shelf lives
COMPONENT_SHELF_LIFE_DAYS: Dict[str, int] = {
    "Platelets": 5,
    "RBCs": 42,
    "Plasma": 365,
}

COMPONENT_SHELF_LIFE_HOURS: Dict[str, int] = {
    "Platelets": 120,   # 5 days
    "RBCs": 1008,       # 42 days
    "Plasma": 8760,     # 365 days
}

# Tiered facility stock buffer thresholds (in hours until zero stock)
SAFE_THRESHOLD_HOURS: float = 120.0
CRITICAL_THRESHOLD_HOURS: float = 48.0

# Exact ABO/Rh compatibility matrices ordered by clinical preference:
# Index 0 is always exact match; universal fallbacks appear last.
RBC_COMPATIBILITY: Dict[str, List[str]] = {
    "O-":  ["O-"],
    "O+":  ["O+", "O-"],
    "A-":  ["A-", "O-"],
    "A+":  ["A+", "A-", "O+", "O-"],
    "B-":  ["B-", "O-"],
    "B+":  ["B+", "B-", "O+", "O-"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "AB+": ["AB+", "AB-", "A+", "A-", "B+", "B-", "O+", "O-"],
}

# Plasma follows inverse ABO compatibility; AB+ is the universal plasma donor.
PLASMA_COMPATIBILITY: Dict[str, List[str]] = {
    "O-":  ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
    "O+":  ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"],
    "A-":  ["A-", "A+", "AB-", "AB+"],
    "A+":  ["A+", "A-", "AB+", "AB-"],
    "B-":  ["B-", "B+", "AB-", "AB+"],
    "B+":  ["B+", "B-", "AB+", "AB-"],
    "AB-": ["AB-", "AB+"],
    "AB+": ["AB+", "AB-"],
}

# Platelets prioritize ABO/Rh exact match first, then plasma-compatible groups,
# with O- retained as emergency fallback when Rh-negative preservation is required.
PLATELET_COMPATIBILITY: Dict[str, List[str]] = {
    "O-":  ["O-", "A-", "B-", "AB-", "O+"],
    "O+":  ["O+", "O-", "A+", "B+", "AB-"],
    "A-":  ["A-", "AB-", "O-"],
    "A+":  ["A+", "A-", "AB+", "AB-", "O+", "O-"],
    "B-":  ["B-", "AB-", "O-"],
    "B+":  ["B+", "B-", "AB+", "AB-", "O+", "O-"],
    "AB-": ["AB-", "AB+", "A-", "B-", "O-"],
    "AB+": ["AB+", "AB-", "A+", "B+", "O+"],
}


def classify_status(zero_stock_hours: float) -> str:
    """Return 'Safe', 'Watch', or 'Critical' based on hours until zero stock."""
    if zero_stock_hours < CRITICAL_THRESHOLD_HOURS:
        return "Critical"
    if zero_stock_hours <= SAFE_THRESHOLD_HOURS:
        return "Watch"
    return "Safe"


def get_compatible_donors(recipient_group: str, component: str) -> List[str]:
    """
    Return ordered list of clinically compatible donor blood groups for a recipient
    and component. Exact match is always first.
    """
    if component == "RBCs":
        return list(RBC_COMPATIBILITY.get(recipient_group, [recipient_group]))
    if component == "Plasma":
        return list(PLASMA_COMPATIBILITY.get(recipient_group, [recipient_group]))
    if component == "Platelets":
        return list(PLATELET_COMPATIBILITY.get(recipient_group, [recipient_group]))
    return [recipient_group]


def is_compatible(donor_group: str, recipient_group: str, component: str) -> Tuple[bool, int, str]:
    """
    Validate donor-to-recipient transfusion compatibility.

    Returns:
        (compatible: bool, priority_rank: int, label: str)
        priority_rank: 0 = exact match, 1 = compatible group, 2 = universal fallback, 99 = incompatible
    """
    allowed = get_compatible_donors(recipient_group, component)
    if donor_group not in allowed:
        return False, 99, "Incompatible"

    if donor_group == recipient_group:
        return True, 0, f"Exact Match ({donor_group} -> {recipient_group})"

    if component == "RBCs" and donor_group == "O-":
        return True, 2, f"Universal RBC Fallback (O- -> {recipient_group})"

    if component == "Plasma" and donor_group in ("AB+", "AB-"):
        return True, 2, f"Universal Plasma Fallback ({donor_group} -> {recipient_group})"

    return True, 1, f"ABO/Rh Compatible ({donor_group} -> {recipient_group})"


_HOSPITAL_GEO: Dict[Tuple[float, float], Tuple[float, float]] = {
    (50.0, 18.0): (23.3915, 85.3485),  # HOSP-01: RIMS, Bariatu, Ranchi
    (20.0, 72.0): (23.3689, 85.3258),  # HOSP-02: Sadar Hospital, Ranchi
    (20.0, 26.0): (23.4375, 85.3026),  # HOSP-03: Ranchi Cancer Hospital (RCHRC), Kanke
    (80.0, 72.0): (23.3883, 85.3313),  # HOSP-04: Rani Children Hospital, Ranchi
    (50.0, 82.0): (23.3116, 85.2772),  # HOSP-05: Paras HEC Hospital, Dhurwa
    (80.0, 28.0): (23.4636, 85.4014),  # HOSP-06: Medanta Hospital, Irba, Ranchi
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 1)


def calculate_distance_km(x1: float, y1: float, x2: float, y2: float) -> float:
    """Return real-world Haversine distance (km) for known hospitals, or schematic fallback."""
    g1 = _HOSPITAL_GEO.get((x1, y1))
    g2 = _HOSPITAL_GEO.get((x2, y2))
    if g1 is not None and g2 is not None:
        return _haversine_km(g1[0], g1[1], g2[0], g2[1])
    raw = math.hypot(x2 - x1, y2 - y1)
    return round(raw * 0.65, 1)


def calculate_transit_minutes(x1: float, y1: float, x2: float, y2: float) -> int:
    """
    Compute deterministic cold-chain courier transit ETA (minutes) from (x, y) grid coords.
    Includes 10-minute cold-pack dispatch & handoff overhead plus 0.85 min per grid unit.
    """
    if x1 == x2 and y1 == y2:
        return 0
    dist = math.hypot(x2 - x1, y2 - y1)
    return max(14, int(round(10.0 + dist * 0.85)))
