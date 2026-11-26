"""
HemoSlab Strict Pydantic v2 Schemas.

Shared data contracts across database.py, engine/math_engine.py,
services/briefing_client.py, main.py, and static/app.js.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

BloodGroup = Literal["O-", "O+", "A+", "B+", "AB-"]
ComponentType = Literal["RBCs", "Platelets", "Plasma"]
StatusLevel = Literal["Safe", "Watch", "Critical"]
ScenarioType = Literal["baseline", "dengue", "trauma"]


def model_to_dict(model: BaseModel) -> Dict[str, Any]:
    """Serialize a Pydantic model cleanly in both Pydantic v2 and v1 runtimes."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class BatchItem(BaseModel):
    batch_id: str
    hospital_id: str
    blood_group: BloodGroup
    component: ComponentType
    units: int = Field(..., ge=0)
    hours_to_expiry: float = Field(..., ge=0.0)


class InventorySummary(BaseModel):
    blood_group: BloodGroup
    component: ComponentType
    total_units: int = Field(..., ge=0)
    daily_demand: float = Field(..., ge=0.0)
    scheduled_daily_inflow: float = Field(..., ge=0.0)
    expiring_within_72h: int = Field(..., ge=0)
    min_hours_to_expiry: Optional[float] = None
    zero_stock_hours: float = Field(..., ge=0.0)
    status: StatusLevel


class ForecastDay(BaseModel):
    day: int = Field(..., ge=1, le=14)
    label: str
    projected_stock: float = Field(..., ge=0.0)
    predicted_demand: float = Field(..., ge=0.0)
    expiring_units: float = Field(..., ge=0.0)
    scheduled_inflow: float = Field(..., ge=0.0)


class HospitalState(BaseModel):
    id: str
    name: str
    code: str
    role: str
    x: float = Field(..., ge=0.0, le=100.0)
    y: float = Field(..., ge=0.0, le=100.0)
    status: StatusLevel
    min_zero_stock_hours: float = Field(..., ge=0.0)
    critical_pair: str
    total_units: int = Field(..., ge=0)
    inventory: List[InventorySummary]
    batches: List[BatchItem]
    forecasts: Dict[str, List[ForecastDay]]


class NetworkEdge(BaseModel):
    source_id: str
    target_id: str
    transit_minutes: int = Field(..., ge=0)
    distance_km: float = Field(..., ge=0.0)


class MathSnapshot(BaseModel):
    equation: str
    hospital_id: str
    hospital_name: str
    blood_group: BloodGroup
    component: ComponentType
    current_stock: int = Field(..., ge=0)
    daily_demand: float = Field(..., ge=0.0)
    hourly_burn_rate: float = Field(..., ge=0.0)
    scheduled_daily_inflow: float = Field(..., ge=0.0)
    expiring_within_48h: int = Field(..., ge=0)
    expiring_within_72h: int = Field(..., ge=0)
    zero_stock_hours: float = Field(..., ge=0.0)
    status: StatusLevel
    scenario: ScenarioType
    donation_drop_pct: float = Field(..., ge=0.0, le=50.0)
    demand_multiplier: float = Field(..., ge=1.0, le=3.0)
    donor_candidates_evaluated: int = Field(..., ge=0)
    selected_donor_post_transfer_hours: Optional[float] = None
    compatibility_rule: Optional[str] = None


class FEFORecommendation(BaseModel):
    recommendation_id: str
    donor_hospital_id: str
    donor_hospital_name: str
    donor_code: str
    receiver_hospital_id: str
    receiver_hospital_name: str
    receiver_code: str
    batch_id: str
    donor_blood_group: BloodGroup
    receiver_blood_group: BloodGroup
    component: ComponentType
    units: int = Field(..., ge=1)
    batch_hours_to_expiry: float = Field(..., ge=0.0)
    transit_minutes: int = Field(..., ge=0)
    compatibility_label: str
    receiver_zero_stock_hours_before: float = Field(..., ge=0.0)
    receiver_zero_stock_hours_after: float = Field(..., ge=0.0)
    donor_hours_after: float = Field(..., ge=0.0)
    urgency_status: StatusLevel
    expiry_risk_saved: bool
    math_inputs: MathSnapshot


class AlertItem(BaseModel):
    alert_id: str
    hospital_id: str
    hospital_name: str
    hospital_code: str
    blood_group: BloodGroup
    component: ComponentType
    status: StatusLevel
    zero_stock_hours: float = Field(..., ge=0.0)
    expiring_within_72h: int = Field(..., ge=0)
    current_stock: int = Field(..., ge=0)
    daily_demand: float = Field(..., ge=0.0)
    headline: str
    recommendation: Optional[FEFORecommendation] = None
    math_inputs: MathSnapshot


class TimelineEvent(BaseModel):
    event_id: str
    hour_offset: float = Field(..., ge=0.0, le=72.0)
    kind: Literal["expiry", "shortage", "transfer"]
    severity: StatusLevel
    hospital_id: str
    hospital_code: str
    hospital_name: str
    blood_group: BloodGroup
    component: ComponentType
    units: int = Field(..., ge=0)
    title: str
    subtitle: str
    alert_id: Optional[str] = None
    recommendation_id: Optional[str] = None


class NetworkStateResponse(BaseModel):
    scenario: ScenarioType
    donation_drop: float = Field(..., ge=0.0, le=50.0)
    demand_mult: float = Field(..., ge=1.0, le=3.0)
    network_readiness_score: int = Field(..., ge=0, le=100)
    most_urgent_countdown_hours: float = Field(..., ge=0.0)
    most_urgent_label: str
    most_urgent_hospital_id: str
    units_saved_from_expiry: int = Field(..., ge=0)
    total_active_alerts: int = Field(..., ge=0)
    hospitals: List[HospitalState]
    edges: List[NetworkEdge]
    recommendations: List[FEFORecommendation]
    alerts: List[AlertItem]
    timeline_72h: List[TimelineEvent]


class TransferDispatchRequest(BaseModel):
    donor_hospital_id: str
    receiver_hospital_id: str
    batch_id: str
    units: int = Field(..., ge=1)
    scenario: ScenarioType = "baseline"
    donation_drop: float = Field(0.0, ge=0.0, le=50.0)
    demand_mult: float = Field(1.0, ge=1.0, le=3.0)
    transit_minutes: int = Field(30, ge=0)
    math_snapshot: Optional[Dict[str, Any]] = None


class TransferDispatchResponse(BaseModel):
    status: Literal["dispatched"]
    transfer_id: int
    message: str
    units_transferred: int = Field(..., ge=1)
    units_saved_increment: int = Field(..., ge=0)
    donor_hospital_id: str
    receiver_hospital_id: str
    network_state: NetworkStateResponse


class GeminiBriefingPayload(BaseModel):
    """Exact 4-field structured output schema enforced on Gemini API responses."""

    cause: str = Field(..., description="1 crisp clinical/operational sentence explaining the shortage or expiry risk.")
    math_trigger: str = Field(..., description="Exact numerical trigger from the deterministic math engine.")
    recommended_action: str = Field(..., description="Exact FEFO transfer instruction including donor, receiver, units, expiry saved, and ETA.")
    donor_sms_draft: str = Field(..., description="Actionable local donor mobilization SMS under 160 characters.")


class StructuredBriefing(BaseModel):
    cause: str
    math_trigger: str
    recommended_action: str
    donor_sms_draft: str
    source: Literal["gemini", "deterministic_fallback"] = "deterministic_fallback"


class BriefingRequest(BaseModel):
    alert: AlertItem
    recommendation: Optional[FEFORecommendation] = None


class AuditLogEntry(BaseModel):
    id: int
    timestamp: str
    action_type: str
    donor_hospital_id: str
    donor_hospital_name: str
    receiver_hospital_id: str
    receiver_hospital_name: str
    batch_id: str
    blood_group: str
    component: str
    units: int
    hours_to_expiry_at_transfer: float
    transit_minutes: int
    units_saved_from_expiry: int
    math_snapshot: Dict[str, Any]


class AuditResponse(BaseModel):
    total_transfers: int
    units_saved_from_expiry: int
    logs: List[AuditLogEntry]
