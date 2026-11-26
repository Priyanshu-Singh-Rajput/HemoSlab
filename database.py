"""
HemoSlab SQLite3 Persistence Layer (Localized: Ranchi Regional Blood Network).

Manages:
- Schema creation & deterministic 6-hospital Ranchi regional seed data
- Realistic short-expiry Platelet and O- batches (24h-60h remaining)
- Atomic FEFO transfer transactions with audit logging and Units Saved tracking
- Instant demo reset to initial seed state
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = Path(__file__).resolve().parent / "hemoslab.db"

# Coordinates (x, y) mapped to Ranchi's real N/S/E/W layout while keeping SVG cards non-overlapping
SEED_HOSPITALS: List[Tuple[str, str, str, str, float, float]] = [
    ("HOSP-01", "RIMS Level-1 Trauma Center", "RIM", "Level-1 Trauma Hub", 50.0, 18.0),
    ("HOSP-02", "Sadar Hospital Regional Blood Bank", "SRB", "Primary Regional Depot", 20.0, 72.0),
    ("HOSP-03", "Ranchi Cancer Hospital & Research Centre", "RCH", "Oncology & Bone Marrow", 20.0, 26.0),
    ("HOSP-04", "Rani Children & Maternal Hospital", "RNH", "Perinatal & OB-GYN", 80.0, 72.0),
    ("HOSP-05", "Paras HEC Multispecialty Hospital", "PHC", "Regional Acute Care", 50.0, 82.0),
    ("HOSP-06", "Medanta Heart & Surgical Institute", "MED", "Cardiothoracic Surgery", 80.0, 28.0),
]


# Base daily demand & scheduled daily inflow by (hospital_id, blood_group, component)
# Carefully calibrated so baseline shows immediate Critical/Watch alerts + healthy FEFO donors,
# while Dengue (+180% Platelets) and Trauma (O-/O+ surge at RIM) create sharp realistic shifts.
def _build_seed_demand_profiles() -> List[Tuple[str, str, str, float, float]]:
    profiles: List[Tuple[str, str, str, float, float]] = []
    # (daily_demand, daily_inflow)
    templates: Dict[str, Dict[str, Dict[str, Tuple[float, float]]]] = {
        "HOSP-01": {  # RIMS Level-1 Trauma Center
            "O-":  {"RBCs": (11.5, 4.0), "Platelets": (7.5, 2.5),  "Plasma": (5.0, 4.5)},
            "O+":  {"RBCs": (14.0, 9.0), "Platelets": (9.0, 5.5),  "Plasma": (6.5, 6.0)},
            "A+":  {"RBCs": (9.5, 8.5),  "Platelets": (6.0, 5.0),  "Plasma": (4.5, 4.5)},
            "B+":  {"RBCs": (7.0, 6.5),  "Platelets": (4.5, 4.0),  "Plasma": (3.5, 3.5)},
            "AB-": {"RBCs": (2.5, 2.5),  "Platelets": (2.0, 2.0),  "Plasma": (4.0, 3.5)},
        },
        "HOSP-02": {  # Sadar Hospital Regional Blood Bank (Primary Surplus Donor)
            "O-":  {"RBCs": (4.0, 12.0), "Platelets": (3.0, 9.0),  "Plasma": (3.0, 8.0)},
            "O+":  {"RBCs": (6.0, 18.0), "Platelets": (4.5, 13.0), "Plasma": (4.0, 10.0)},
            "A+":  {"RBCs": (5.0, 15.0), "Platelets": (4.0, 12.0), "Plasma": (3.5, 9.0)},
            "B+":  {"RBCs": (4.0, 12.0), "Platelets": (3.0, 9.5),  "Plasma": (3.0, 8.0)},
            "AB-": {"RBCs": (2.0, 5.5),  "Platelets": (1.5, 4.5),  "Plasma": (2.0, 6.5)},
        },
        "HOSP-03": {  # Ranchi Cancer Hospital & Research Centre (High Platelet Burn)
            "O-":  {"RBCs": (5.5, 5.0),  "Platelets": (6.5, 3.0),  "Plasma": (3.0, 3.0)},
            "O+":  {"RBCs": (7.5, 7.0),  "Platelets": (10.5, 5.0), "Plasma": (4.0, 4.0)},
            "A+":  {"RBCs": (6.5, 6.0),  "Platelets": (12.0, 4.5), "Plasma": (3.5, 3.5)},
            "B+":  {"RBCs": (5.0, 4.5),  "Platelets": (7.0, 4.5),  "Plasma": (2.5, 2.5)},
            "AB-": {"RBCs": (2.0, 2.0),  "Platelets": (3.0, 2.0),  "Plasma": (2.5, 2.5)},
        },
        "HOSP-04": {  # Rani Children & Maternal Hospital (Surplus A+/B+/O+)
            "O-":  {"RBCs": (4.0, 5.0),  "Platelets": (2.5, 4.0),  "Plasma": (2.5, 3.5)},
            "O+":  {"RBCs": (6.0, 8.5),  "Platelets": (3.5, 6.5),  "Plasma": (3.0, 4.5)},
            "A+":  {"RBCs": (5.0, 8.0),  "Platelets": (3.0, 6.5),  "Plasma": (3.0, 4.5)},
            "B+":  {"RBCs": (4.0, 7.0),  "Platelets": (2.5, 5.5),  "Plasma": (2.0, 3.5)},
            "AB-": {"RBCs": (1.5, 2.5),  "Platelets": (1.5, 2.5),  "Plasma": (2.0, 3.0)},
        },
        "HOSP-05": {  # Paras HEC Multispecialty Hospital (Secondary Balanced Donor)
            "O-":  {"RBCs": (4.5, 6.5),  "Platelets": (3.0, 5.0),  "Plasma": (2.5, 4.0)},
            "O+":  {"RBCs": (7.0, 10.0), "Platelets": (4.0, 7.0),  "Plasma": (3.5, 5.0)},
            "A+":  {"RBCs": (6.0, 9.0),  "Platelets": (3.5, 6.5),  "Plasma": (3.0, 4.5)},
            "B+":  {"RBCs": (4.5, 7.5),  "Platelets": (3.0, 5.5),  "Plasma": (2.5, 4.0)},
            "AB-": {"RBCs": (1.5, 3.0),  "Platelets": (1.5, 2.5),  "Plasma": (2.0, 3.5)},
        },
        "HOSP-06": {  # Medanta Heart & Surgical Institute (Watch on B+ RBCs & O+ Platelets)
            "O-":  {"RBCs": (5.0, 4.5),  "Platelets": (3.5, 3.0),  "Plasma": (4.0, 4.0)},
            "O+":  {"RBCs": (8.5, 7.5),  "Platelets": (7.5, 4.0),  "Plasma": (5.5, 5.0)},
            "A+":  {"RBCs": (7.0, 6.5),  "Platelets": (5.0, 4.5),  "Plasma": (4.5, 4.5)},
            "B+":  {"RBCs": (9.0, 4.5),  "Platelets": (4.5, 3.5),  "Plasma": (3.5, 3.5)},
            "AB-": {"RBCs": (2.0, 2.0),  "Platelets": (2.0, 2.0),  "Plasma": (3.0, 3.0)},
        },
    }
    for hosp_id, groups in templates.items():
        for bg, comps in groups.items():
            for comp, (demand, inflow) in comps.items():
                profiles.append((hosp_id, bg, comp, demand, inflow))
    return profiles


def _build_seed_batches() -> List[Tuple[str, str, str, str, int, float]]:
    """
    Create realistic multi-batch inventory per hospital, including short-expiry
    Platelets and O- batches (24h-60h remaining) so Watch/Critical alerts and
    FEFO transfer opportunities appear immediately on first load.
    """
    # (batch_id, hospital_id, blood_group, component, units, hours_to_expiry)
    return [
        # --- HOSP-01: RIMS Level-1 Trauma Center (Critical O- RBCs & Critical O- Platelets) ---
        ("RIM-ON-R01", "HOSP-01", "O-",  "RBCs",      6,  38.0),
        ("RIM-ON-R02", "HOSP-01", "O-",  "RBCs",      5, 420.0),
        ("RIM-ON-P01", "HOSP-01", "O-",  "Platelets", 5,  26.0),
        ("RIM-ON-P02", "HOSP-01", "O-",  "Platelets", 4,  52.0),
        ("RIM-ON-L01", "HOSP-01", "O-",  "Plasma",    34, 4200.0),

        ("RIM-OP-R01", "HOSP-01", "O+",  "RBCs",      14, 180.0),
        ("RIM-OP-R02", "HOSP-01", "O+",  "RBCs",      16, 620.0),
        ("RIM-OP-P01", "HOSP-01", "O+",  "Platelets", 8,  34.0),
        ("RIM-OP-P02", "HOSP-01", "O+",  "Platelets", 9,  76.0),
        ("RIM-OP-L01", "HOSP-01", "O+",  "Plasma",    42, 5100.0),

        ("RIM-AP-R01", "HOSP-01", "A+",  "RBCs",      36, 480.0),
        ("RIM-AP-P01", "HOSP-01", "A+",  "Platelets", 18, 66.0),
        ("RIM-AP-L01", "HOSP-01", "A+",  "Plasma",    30, 4800.0),

        ("RIM-BP-R01", "HOSP-01", "B+",  "RBCs",      28, 520.0),
        ("RIM-BP-P01", "HOSP-01", "B+",  "Platelets", 15, 78.0),
        ("RIM-BP-L01", "HOSP-01", "B+",  "Plasma",    24, 5400.0),

        ("RIM-AB-R01", "HOSP-01", "AB-", "RBCs",      16, 600.0),
        ("RIM-AB-P01", "HOSP-01", "AB-", "Platelets", 10, 84.0),
        ("RIM-AB-L01", "HOSP-01", "AB-", "Plasma",    26, 4600.0),

        # --- HOSP-02: Sadar Hospital Regional Blood Bank (High Surplus + Short-Expiry FEFO Batches) ---
        ("SRB-ON-R01", "HOSP-02", "O-",  "RBCs",      16, 44.0),   # Short-expiry FEFO target!
        ("SRB-ON-R02", "HOSP-02", "O-",  "RBCs",      46, 540.0),
        ("SRB-ON-P01", "HOSP-02", "O-",  "Platelets", 12, 30.0),   # Short-expiry FEFO target!
        ("SRB-ON-P02", "HOSP-02", "O-",  "Platelets", 24, 92.0),
        ("SRB-ON-L01", "HOSP-02", "O-",  "Plasma",    55, 6200.0),

        ("SRB-OP-R01", "HOSP-02", "O+",  "RBCs",      22, 50.0),
        ("SRB-OP-R02", "HOSP-02", "O+",  "RBCs",      64, 710.0),
        ("SRB-OP-P01", "HOSP-02", "O+",  "Platelets", 16, 32.0),   # Short-expiry FEFO target!
        ("SRB-OP-P02", "HOSP-02", "O+",  "Platelets", 30, 96.0),
        ("SRB-OP-L01", "HOSP-02", "O+",  "Plasma",    70, 6800.0),

        ("SRB-AP-R01", "HOSP-02", "A+",  "RBCs",      18, 56.0),
        ("SRB-AP-R02", "HOSP-02", "A+",  "RBCs",      54, 680.0),
        ("SRB-AP-P01", "HOSP-02", "A+",  "Platelets", 18, 28.0),   # Short-expiry FEFO target for RCH!
        ("SRB-AP-P02", "HOSP-02", "A+",  "Platelets", 28, 98.0),
        ("SRB-AP-L01", "HOSP-02", "A+",  "Plasma",    62, 7000.0),

        ("SRB-BP-R01", "HOSP-02", "B+",  "RBCs",      18, 42.0),   # Short-expiry FEFO target for MED!
        ("SRB-BP-R02", "HOSP-02", "B+",  "RBCs",      44, 640.0),
        ("SRB-BP-P01", "HOSP-02", "B+",  "Platelets", 14, 36.0),
        ("SRB-BP-P02", "HOSP-02", "B+",  "Platelets", 22, 94.0),
        ("SRB-BP-L01", "HOSP-02", "B+",  "Plasma",    48, 6500.0),

        ("SRB-AB-R01", "HOSP-02", "AB-", "RBCs",      24, 590.0),
        ("SRB-AB-P01", "HOSP-02", "AB-", "Platelets", 14, 48.0),
        ("SRB-AB-P02", "HOSP-02", "AB-", "Platelets", 16, 102.0),
        ("SRB-AB-L01", "HOSP-02", "AB-", "Plasma",    46, 7400.0),

        # --- HOSP-03: Ranchi Cancer Hospital & Research Centre (Critical A+ Platelets, Watch O+ Platelets) ---
        ("RCH-ON-R01", "HOSP-03", "O-",  "RBCs",      30, 520.0),
        ("RCH-ON-P01", "HOSP-03", "O-",  "Platelets", 8,  34.0),
        ("RCH-ON-P02", "HOSP-03", "O-",  "Platelets", 6,  72.0),
        ("RCH-ON-L01", "HOSP-03", "O-",  "Plasma",    28, 5000.0),

        ("RCH-OP-R01", "HOSP-03", "O+",  "RBCs",      42, 600.0),
        ("RCH-OP-P01", "HOSP-03", "O+",  "Platelets", 10, 32.0),
        ("RCH-OP-P02", "HOSP-03", "O+",  "Platelets", 10, 68.0),
        ("RCH-OP-L01", "HOSP-03", "O+",  "Plasma",    32, 5200.0),

        ("RCH-AP-R01", "HOSP-03", "A+",  "RBCs",      36, 560.0),
        ("RCH-AP-P01", "HOSP-03", "A+",  "Platelets", 7,  24.0),   # Imminent expiry + high oncology burn!
        ("RCH-AP-P02", "HOSP-03", "A+",  "Platelets", 5,  46.0),
        ("RCH-AP-L01", "HOSP-03", "A+",  "Plasma",    26, 4900.0),

        ("RCH-BP-R01", "HOSP-03", "B+",  "RBCs",      28, 490.0),
        ("RCH-BP-P01", "HOSP-03", "B+",  "Platelets", 14, 58.0),
        ("RCH-BP-L01", "HOSP-03", "B+",  "Plasma",    22, 5300.0),

        ("RCH-AB-R01", "HOSP-03", "AB-", "RBCs",      16, 610.0),
        ("RCH-AB-P01", "HOSP-03", "AB-", "Platelets", 9,  64.0),
        ("RCH-AB-L01", "HOSP-03", "AB-", "Plasma",    20, 5600.0),

        # --- HOSP-04: Rani Children & Maternal Hospital (Safe Surplus + Short-Expiry Batches) ---
        ("RNH-ON-R01", "HOSP-04", "O-",  "RBCs",      10, 54.0),
        ("RNH-ON-R02", "HOSP-04", "O-",  "RBCs",      28, 620.0),
        ("RNH-ON-P01", "HOSP-04", "O-",  "Platelets", 9,  42.0),
        ("RNH-ON-P02", "HOSP-04", "O-",  "Platelets", 14, 96.0),
        ("RNH-ON-L01", "HOSP-04", "O-",  "Plasma",    34, 6100.0),

        ("RNH-OP-R01", "HOSP-04", "O+",  "RBCs",      44, 680.0),
        ("RNH-OP-P01", "HOSP-04", "O+",  "Platelets", 14, 38.0),
        ("RNH-OP-P02", "HOSP-04", "O+",  "Platelets", 20, 98.0),
        ("RNH-OP-L01", "HOSP-04", "O+",  "Plasma",    38, 6300.0),

        ("RNH-AP-R01", "HOSP-04", "A+",  "RBCs",      40, 640.0),
        ("RNH-AP-P01", "HOSP-04", "A+",  "Platelets", 14, 34.0),   # Secondary FEFO donor for RCH!
        ("RNH-AP-P02", "HOSP-04", "A+",  "Platelets", 20, 100.0),
        ("RNH-AP-L01", "HOSP-04", "A+",  "Plasma",    36, 6400.0),

        ("RNH-BP-R01", "HOSP-04", "B+",  "RBCs",      14, 48.0),
        ("RNH-BP-R02", "HOSP-04", "B+",  "RBCs",      30, 660.0),
        ("RNH-BP-P01", "HOSP-04", "B+",  "Platelets", 18, 86.0),
        ("RNH-BP-L01", "HOSP-04", "B+",  "Plasma",    28, 6000.0),

        ("RNH-AB-R01", "HOSP-04", "AB-", "RBCs",      18, 700.0),
        ("RNH-AB-P01", "HOSP-04", "AB-", "Platelets", 12, 88.0),
        ("RNH-AB-L01", "HOSP-04", "AB-", "Plasma",    26, 6700.0),

        # --- HOSP-05: Paras HEC Multispecialty Hospital (Safe Mid-Tier Donor) ---
        ("PHC-ON-R01", "HOSP-05", "O-",  "RBCs",      12, 48.0),
        ("PHC-ON-R02", "HOSP-05", "O-",  "RBCs",      32, 650.0),
        ("PHC-ON-P01", "HOSP-05", "O-",  "Platelets", 10, 44.0),
        ("PHC-ON-P02", "HOSP-05", "O-",  "Platelets", 16, 94.0),
        ("PHC-ON-L01", "HOSP-05", "O-",  "Plasma",    36, 5900.0),

        ("PHC-OP-R01", "HOSP-05", "O+",  "RBCs",      50, 690.0),
        ("PHC-OP-P01", "HOSP-05", "O+",  "Platelets", 14, 40.0),
        ("PHC-OP-P02", "HOSP-05", "O+",  "Platelets", 22, 96.0),
        ("PHC-OP-L01", "HOSP-05", "O+",  "Plasma",    44, 6200.0),

        ("PHC-AP-R01", "HOSP-05", "A+",  "RBCs",      42, 620.0),
        ("PHC-AP-P01", "HOSP-05", "A+",  "Platelets", 12, 46.0),
        ("PHC-AP-P02", "HOSP-05", "A+",  "Platelets", 20, 98.0),
        ("PHC-AP-L01", "HOSP-05", "A+",  "Plasma",    38, 6100.0),

        ("PHC-BP-R01", "HOSP-05", "B+",  "RBCs",      14, 52.0),
        ("PHC-BP-R02", "HOSP-05", "B+",  "RBCs",      34, 670.0),
        ("PHC-BP-P01", "HOSP-05", "B+",  "Platelets", 18, 84.0),
        ("PHC-BP-L01", "HOSP-05", "B+",  "Plasma",    32, 6000.0),

        ("PHC-AB-R01", "HOSP-05", "AB-", "RBCs",      20, 680.0),
        ("PHC-AB-P01", "HOSP-05", "AB-", "Platelets", 12, 90.0),
        ("PHC-AB-L01", "HOSP-05", "AB-", "Plasma",    28, 6500.0),

        # --- HOSP-06: Medanta Heart & Surgical Institute (Watch B+ RBCs, Watch O+ Platelets) ---
        ("MED-ON-R01", "HOSP-06", "O-",  "RBCs",      28, 490.0),
        ("MED-ON-P01", "HOSP-06", "O-",  "Platelets", 14, 72.0),
        ("MED-ON-L01", "HOSP-06", "O-",  "Plasma",    36, 5200.0),

        ("MED-OP-R01", "HOSP-06", "O+",  "RBCs",      46, 560.0),
        ("MED-OP-P01", "HOSP-06", "O+",  "Platelets", 7,  30.0),
        ("MED-OP-P02", "HOSP-06", "O+",  "Platelets", 6,  64.0),
        ("MED-OP-L01", "HOSP-06", "O+",  "Plasma",    42, 5400.0),

        ("MED-AP-R01", "HOSP-06", "A+",  "RBCs",      40, 580.0),
        ("MED-AP-P01", "HOSP-06", "A+",  "Platelets", 18, 76.0),
        ("MED-AP-L01", "HOSP-06", "A+",  "Plasma",    34, 5100.0),

        ("MED-BP-R01", "HOSP-06", "B+",  "RBCs",      8,  44.0),   # Watch status on B+ RBCs
        ("MED-BP-R02", "HOSP-06", "B+",  "RBCs",      8,  310.0),
        ("MED-BP-P01", "HOSP-06", "B+",  "Platelets", 15, 70.0),
        ("MED-BP-L01", "HOSP-06", "B+",  "Plasma",    28, 5300.0),

        ("MED-AB-R01", "HOSP-06", "AB-", "RBCs",      16, 600.0),
        ("MED-AB-P01", "HOSP-06", "AB-", "Platelets", 10, 82.0),
        ("MED-AB-L01", "HOSP-06", "AB-", "Plasma",    24, 5500.0),
    ]


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Create tables if missing and seed initial data if empty."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS hospitals (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    code TEXT NOT NULL,
                    role TEXT NOT NULL,
                    x REAL NOT NULL,
                    y REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS demand_profiles (
                    hospital_id TEXT NOT NULL,
                    blood_group TEXT NOT NULL,
                    component TEXT NOT NULL,
                    base_daily_demand REAL NOT NULL,
                    base_daily_inflow REAL NOT NULL,
                    PRIMARY KEY (hospital_id, blood_group, component),
                    FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
                );

                CREATE TABLE IF NOT EXISTS batches (
                    batch_id TEXT PRIMARY KEY,
                    hospital_id TEXT NOT NULL,
                    blood_group TEXT NOT NULL,
                    component TEXT NOT NULL,
                    units INTEGER NOT NULL CHECK(units > 0),
                    hours_to_expiry REAL NOT NULL CHECK(hours_to_expiry >= 0),
                    FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
                );

                CREATE TABLE IF NOT EXISTS network_metrics (
                    key TEXT PRIMARY KEY,
                    int_value INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    donor_hospital_id TEXT NOT NULL,
                    donor_hospital_name TEXT NOT NULL,
                    receiver_hospital_id TEXT NOT NULL,
                    receiver_hospital_name TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    blood_group TEXT NOT NULL,
                    component TEXT NOT NULL,
                    units INTEGER NOT NULL,
                    hours_to_expiry_at_transfer REAL NOT NULL,
                    transit_minutes INTEGER NOT NULL,
                    units_saved_from_expiry INTEGER NOT NULL,
                    math_snapshot_json TEXT NOT NULL
                );
                """
            )
            count = conn.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0]
            if count == 0:
                _seed_tables(conn)
    finally:
        conn.close()


def _seed_tables(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO hospitals (id, name, code, role, x, y) VALUES (?, ?, ?, ?, ?, ?)",
        SEED_HOSPITALS,
    )
    conn.executemany(
        """
        INSERT INTO demand_profiles (hospital_id, blood_group, component, base_daily_demand, base_daily_inflow)
        VALUES (?, ?, ?, ?, ?)
        """,
        _build_seed_demand_profiles(),
    )
    conn.executemany(
        """
        INSERT INTO batches (batch_id, hospital_id, blood_group, component, units, hours_to_expiry)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        _build_seed_batches(),
    )
    conn.execute(
        "INSERT OR REPLACE INTO network_metrics (key, int_value) VALUES ('units_saved_from_expiry', 0)"
    )


def reset_db(db_path: Path = DB_PATH) -> None:
    """Atomically wipe and re-seed SQLite to the clean initial demo state."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM audit_logs")
            conn.execute("DELETE FROM batches")
            conn.execute("DELETE FROM demand_profiles")
            conn.execute("DELETE FROM network_metrics")
            conn.execute("DELETE FROM hospitals")
            _seed_tables(conn)
    finally:
        conn.close()


def fetch_network_raw_data(db_path: Path = DB_PATH) -> Dict[str, Any]:
    """Fetch hospitals, demand profiles, active batches, and network metrics."""
    conn = get_connection(db_path)
    try:
        hospitals = [dict(row) for row in conn.execute("SELECT * FROM hospitals ORDER BY id").fetchall()]
        demand_profiles = [
            dict(row) for row in conn.execute("SELECT * FROM demand_profiles").fetchall()
        ]
        batches = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM batches ORDER BY hospital_id, component, blood_group, hours_to_expiry ASC"
            ).fetchall()
        ]
        metric_row = conn.execute(
            "SELECT int_value FROM network_metrics WHERE key = 'units_saved_from_expiry'"
        ).fetchone()
        units_saved = int(metric_row["int_value"]) if metric_row else 0
        return {
            "hospitals": hospitals,
            "demand_profiles": demand_profiles,
            "batches": batches,
            "units_saved_from_expiry": units_saved,
        }
    finally:
        conn.close()


def execute_atomic_transfer(
    donor_hospital_id: str,
    receiver_hospital_id: str,
    batch_id: str,
    units: int,
    transit_minutes: int,
    math_snapshot: Optional[Dict[str, Any]] = None,
    db_path: Path = DB_PATH,
) -> Dict[str, Any]:
    """
    Atomically deduct `units` from `batch_id` at `donor_hospital_id`, add them to
    `receiver_hospital_id` with transit-adjusted remaining shelf life, increment
    Units Saved from Expiry when saving short-expiry stock, and write an audit log.
    """
    if donor_hospital_id == receiver_hospital_id:
        raise ValueError("Donor and receiver hospitals must be distinct.")
    if units <= 0:
        raise ValueError("Transfer units must be positive.")

    conn = get_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        donor_row = conn.execute(
            "SELECT id, name FROM hospitals WHERE id = ?", (donor_hospital_id,)
        ).fetchone()
        receiver_row = conn.execute(
            "SELECT id, name FROM hospitals WHERE id = ?", (receiver_hospital_id,)
        ).fetchone()
        if not donor_row or not receiver_row:
            raise ValueError("Invalid donor or receiver hospital ID.")

        batch_row = conn.execute(
            "SELECT * FROM batches WHERE batch_id = ? AND hospital_id = ?",
            (batch_id, donor_hospital_id),
        ).fetchone()
        if not batch_row:
            raise ValueError(f"Batch '{batch_id}' not found at donor '{donor_hospital_id}'.")

        available_units = int(batch_row["units"])
        if units > available_units:
            raise ValueError(
                f"Requested {units} units exceeds available {available_units} units in batch '{batch_id}'."
            )

        remaining_units = available_units - units
        if remaining_units == 0:
            conn.execute("DELETE FROM batches WHERE batch_id = ?", (batch_id,))
        else:
            conn.execute(
                "UPDATE batches SET units = ? WHERE batch_id = ?",
                (remaining_units, batch_id),
            )

        hours_to_expiry = float(batch_row["hours_to_expiry"])
        post_transit_hours = round(max(1.0, hours_to_expiry - (transit_minutes / 60.0)), 1)

        # Create a unique transferred batch ID at the receiving hospital
        ts_suffix = datetime.now(timezone.utc).strftime("%H%M%S%f")[:10]
        transferred_batch_id = f"FEFO-{batch_id}-{ts_suffix}"
        conn.execute(
            """
            INSERT INTO batches (batch_id, hospital_id, blood_group, component, units, hours_to_expiry)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                transferred_batch_id,
                receiver_hospital_id,
                batch_row["blood_group"],
                batch_row["component"],
                units,
                post_transit_hours,
            ),
        )

        # Units saved from expiry: batches within 72h of expiry routed before wastage
        units_saved_increment = units if hours_to_expiry <= 72.0 else 0
        conn.execute(
            """
            UPDATE network_metrics
            SET int_value = int_value + ?
            WHERE key = 'units_saved_from_expiry'
            """,
            (units_saved_increment,),
        )

        timestamp = datetime.now(timezone.utc).isoformat()
        snapshot_json = json.dumps(math_snapshot or {}, ensure_ascii=False)
        cursor = conn.execute(
            """
            INSERT INTO audit_logs (
                timestamp, action_type, donor_hospital_id, donor_hospital_name,
                receiver_hospital_id, receiver_hospital_name, batch_id,
                blood_group, component, units, hours_to_expiry_at_transfer,
                transit_minutes, units_saved_from_expiry, math_snapshot_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                "FEFO_TRANSFER",
                donor_hospital_id,
                donor_row["name"],
                receiver_hospital_id,
                receiver_row["name"],
                batch_id,
                batch_row["blood_group"],
                batch_row["component"],
                units,
                hours_to_expiry,
                transit_minutes,
                units_saved_increment,
                snapshot_json,
            ),
        )
        transfer_id = int(cursor.lastrowid)
        conn.commit()
        return {
            "transfer_id": transfer_id,
            "units_transferred": units,
            "units_saved_increment": units_saved_increment,
            "donor_hospital_name": donor_row["name"],
            "receiver_hospital_name": receiver_row["name"],
            "blood_group": batch_row["blood_group"],
            "component": batch_row["component"],
            "batch_id": batch_id,
            "transferred_batch_id": transferred_batch_id,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_audit_logs(limit: int = 50, db_path: Path = DB_PATH) -> Dict[str, Any]:
    """Return recent timestamped FEFO transfer logs and cumulative units saved."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        total_row = conn.execute("SELECT COUNT(*) AS cnt FROM audit_logs").fetchone()
        saved_row = conn.execute(
            "SELECT int_value FROM network_metrics WHERE key = 'units_saved_from_expiry'"
        ).fetchone()
        logs = []
        for row in rows:
            item = dict(row)
            raw_json = item.pop("math_snapshot_json", "{}")
            try:
                item["math_snapshot"] = json.loads(raw_json)
            except json.JSONDecodeError:
                item["math_snapshot"] = {}
            logs.append(item)
        return {
            "total_transfers": int(total_row["cnt"]) if total_row else 0,
            "units_saved_from_expiry": int(saved_row["int_value"]) if saved_row else 0,
            "logs": logs,
        }
    finally:
        conn.close()