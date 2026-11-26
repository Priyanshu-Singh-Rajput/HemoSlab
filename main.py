"""
HemoSlab FastAPI Application Entrypoint.

Serves REST endpoints for deterministic network state, scenario simulation,
atomic FEFO transfer dispatch, structured AI briefings, audit ledger, demo reset,
and static frontend assets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import (
    execute_atomic_transfer,
    fetch_audit_logs,
    fetch_network_raw_data,
    init_db,
    reset_db,
)
from engine.math_engine import compute_network_state
from models import (
    AuditLogEntry,
    AuditResponse,
    BriefingRequest,
    NetworkStateResponse,
    ScenarioType,
    StructuredBriefing,
    TransferDispatchRequest,
    TransferDispatchResponse,
)
from services.briefing_client import generate_structured_briefing

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="HemoSlab",
    description="Deterministic, AI-assisted predictive blood shortage & FEFO allocation network.",
    version="1.0.0",
)

# Ensure SQLite schema and 6-hospital seed data exist on module load
init_db()

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_landing() -> FileResponse:
    landing_path = STATIC_DIR / "landing.html"
    if landing_path.exists():
        return FileResponse(str(landing_path))
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    return FileResponse(str(index_path))


@app.get("/dashboard", include_in_schema=False)
def serve_dashboard() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    return FileResponse(str(index_path))


@app.get("/api/network/state", response_model=NetworkStateResponse)
def get_network_state(
    scenario: ScenarioType = Query("baseline", description="baseline | dengue | trauma"),
    donation_drop: float = Query(0.0, ge=0.0, le=50.0, description="Donation drop percentage (0-50)"),
    demand_mult: float = Query(1.0, ge=1.0, le=3.0, description="Demand multiplier (1.0-3.0)"),
) -> NetworkStateResponse:
    raw = fetch_network_raw_data()
    return compute_network_state(
        raw_data=raw,
        scenario=scenario,
        donation_drop=donation_drop,
        demand_mult=demand_mult,
    )


@app.post("/api/transfers/dispatch", response_model=TransferDispatchResponse)
def dispatch_transfer(payload: TransferDispatchRequest) -> TransferDispatchResponse:
    try:
        result = execute_atomic_transfer(
            donor_hospital_id=payload.donor_hospital_id,
            receiver_hospital_id=payload.receiver_hospital_id,
            batch_id=payload.batch_id,
            units=payload.units,
            transit_minutes=payload.transit_minutes,
            math_snapshot=payload.math_snapshot,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    updated_raw = fetch_network_raw_data()
    updated_state = compute_network_state(
        raw_data=updated_raw,
        scenario=payload.scenario,
        donation_drop=payload.donation_drop,
        demand_mult=payload.demand_mult,
    )

    msg = (
        f"Dispatched {result['units_transferred']}u {result['blood_group']} {result['component']} "
        f"({result['batch_id']}) from {result['donor_hospital_name']} to {result['receiver_hospital_name']}."
    )
    return TransferDispatchResponse(
        status="dispatched",
        transfer_id=result["transfer_id"],
        message=msg,
        units_transferred=result["units_transferred"],
        units_saved_increment=result["units_saved_increment"],
        donor_hospital_id=payload.donor_hospital_id,
        receiver_hospital_id=payload.receiver_hospital_id,
        network_state=updated_state,
    )


@app.post("/api/briefing", response_model=StructuredBriefing)
def create_briefing(payload: BriefingRequest) -> StructuredBriefing:
    return generate_structured_briefing(
        alert=payload.alert,
        recommendation=payload.recommendation,
    )


@app.get("/api/audit", response_model=AuditResponse)
def get_audit_ledger(limit: int = Query(50, ge=1, le=200)) -> AuditResponse:
    data = fetch_audit_logs(limit=limit)
    return AuditResponse(
        total_transfers=data["total_transfers"],
        units_saved_from_expiry=data["units_saved_from_expiry"],
        logs=[AuditLogEntry(**entry) for entry in data["logs"]],
    )


@app.post("/api/reset", response_model=NetworkStateResponse)
def reset_demo_state(
    scenario: Literal["baseline", "dengue", "trauma"] = Query("baseline"),
    donation_drop: float = Query(0.0, ge=0.0, le=50.0),
    demand_mult: float = Query(1.0, ge=1.0, le=3.0),
) -> NetworkStateResponse:
    reset_db()
    raw = fetch_network_raw_data()
    return compute_network_state(
        raw_data=raw,
        scenario=scenario,
        donation_drop=donation_drop,
        demand_mult=demand_mult,
    )
