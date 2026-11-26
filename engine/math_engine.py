"""
HemoSlab Deterministic Forecasting & FEFO Transfer Optimizer (Pure Python, Zero LLM).

Implements:
- 14-day stock decay projection:
  Projected_Stock(t) = Current_Stock - Predicted_Demand(t) - Expiring_Units(t) + Scheduled_Inflow(t)
- Exact hourly Zero-Stock Countdown for every (hospital, blood_group, component)
- FEFO (First-Expired, First-Out) Transfer Optimizer constrained by rulebook.py
- Regional Network Readiness Score (0-100) and 72-hour chronological timeline
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from models import (
    AlertItem,
    BatchItem,
    FEFORecommendation,
    ForecastDay,
    HospitalState,
    InventorySummary,
    MathSnapshot,
    NetworkEdge,
    NetworkStateResponse,
    ScenarioType,
    TimelineEvent,
)
from .rulebook import (
    BLOOD_GROUPS,
    COMPONENTS,
    COMPONENT_SHELF_LIFE_HOURS,
    CRITICAL_THRESHOLD_HOURS,
    SAFE_THRESHOLD_HOURS,
    calculate_distance_km,
    calculate_transit_minutes,
    classify_status,
    is_compatible,
)

# Sparse clean regional cold-chain corridor graph connecting all 6 facilities
CORRIDOR_PAIRS: List[Tuple[str, str]] = [
    ("HOSP-01", "HOSP-02"),
    ("HOSP-02", "HOSP-03"),
    ("HOSP-03", "HOSP-04"),
    ("HOSP-04", "HOSP-05"),
    ("HOSP-05", "HOSP-06"),
    ("HOSP-06", "HOSP-01"),
    ("HOSP-02", "HOSP-05"),
    ("HOSP-01", "HOSP-05"),
    ("HOSP-02", "HOSP-04"),
    ("HOSP-03", "HOSP-05"),
]

MAX_SIMULATION_HOURS = 336  # 14 days


def _effective_rates(
    hospital_id: str,
    blood_group: str,
    component: str,
    base_demand: float,
    base_inflow: float,
    scenario: ScenarioType,
    donation_drop: float,
    demand_mult: float,
) -> Tuple[float, float]:
    """Apply scenario shocks and stress-test sliders deterministically."""
    scenario_demand_factor = 1.0
    if scenario == "dengue" and component == "Platelets":
        # +180% Platelet burn rate across regional hospitals
        scenario_demand_factor = 2.8
    elif scenario == "trauma":
        if hospital_id == "HOSP-01" and blood_group == "O-" and component in ("RBCs", "Platelets"):
            scenario_demand_factor = 3.2
        elif hospital_id == "HOSP-01" and blood_group == "O+" and component in ("RBCs", "Platelets"):
            scenario_demand_factor = 2.6
        elif hospital_id == "HOSP-01" and component == "Plasma":
            scenario_demand_factor = 1.6
        elif blood_group in ("O-", "O+") and component == "RBCs":
            scenario_demand_factor = 1.25

    eff_demand = round(base_demand * scenario_demand_factor * demand_mult, 3)
    eff_inflow = round(base_inflow * max(0.0, 1.0 - (donation_drop / 100.0)), 3)
    return eff_demand, eff_inflow


def compute_zero_stock_hours(
    batches: List[Dict[str, Any]],
    daily_demand: float,
    daily_inflow: float,
    component: str,
) -> float:
    """
    Deterministic hourly FEFO simulation returning exact hours until stock reaches 0.
    Caps at 336.0h (14 days) when supply stays positive across the full horizon.
    """
    total_start = sum(float(b["units"]) for b in batches)
    if total_start <= 0.0:
        return 0.0
    if daily_demand <= 0.0:
        return float(MAX_SIMULATION_HOURS)

    hourly_demand = daily_demand / 24.0
    hourly_inflow = daily_inflow / 24.0
    fresh_shelf_hours = float(COMPONENT_SHELF_LIFE_HOURS.get(component, 120))

    # Mutable queue of [units, hours_remaining] sorted earliest expiry first (FEFO)
    queue: List[List[float]] = sorted(
        [[float(b["units"]), float(b["hours_to_expiry"])] for b in batches if b["units"] > 0],
        key=lambda item: item[1],
    )

    for hour in range(1, MAX_SIMULATION_HOURS + 1):
        # 1. Scheduled inflow arrives as fresh shelf-life stock
        if hourly_inflow > 0.0:
            queue.append([hourly_inflow, fresh_shelf_hours])

        # 2. Consume earliest-expiring non-expired units first (FEFO)
        demand_needed = hourly_demand
        available_before = sum(item[0] for item in queue if item[1] > 0.0)
        if available_before <= demand_needed:
            fraction = available_before / demand_needed if demand_needed > 0 else 0.0
            return round((hour - 1) + fraction, 1)

        idx = 0
        while demand_needed > 1e-9 and idx < len(queue):
            if queue[idx][1] > 0.0 and queue[idx][0] > 0.0:
                used = min(queue[idx][0], demand_needed)
                queue[idx][0] -= used
                demand_needed -= used
            idx += 1

        # 3. Age remaining units by 1 hour and discard expired units
        next_queue: List[List[float]] = []
        for units, hrs in queue:
            rem_hrs = hrs - 1.0
            if units > 1e-6 and rem_hrs > 0.0:
                next_queue.append([units, rem_hrs])
        queue = next_queue

        if not queue or sum(item[0] for item in queue) <= 1e-6:
            return round(float(hour), 1)

    return float(MAX_SIMULATION_HOURS)


def project_14_day_component_stock(
    batches: List[Dict[str, Any]],
    total_daily_demand: float,
    total_daily_inflow: float,
    component: str,
) -> List[ForecastDay]:
    """
    Compute 14-day daily stock projection for a hospital & component using:
    Projected_Stock(t) = Current_Stock - Predicted_Demand(t) - Expiring_Units(t) + Scheduled_Inflow(t)
    """
    fresh_shelf_hours = float(COMPONENT_SHELF_LIFE_HOURS.get(component, 120))
    queue: List[List[float]] = sorted(
        [[float(b["units"]), float(b["hours_to_expiry"])] for b in batches if b["units"] > 0],
        key=lambda item: item[1],
    )

    days: List[ForecastDay] = []
    for day in range(1, 15):
        # 1. Consume FEFO to satisfy Predicted_Demand(t)
        demand_rem = total_daily_demand
        for item in queue:
            if demand_rem <= 1e-9:
                break
            if item[0] > 0.0 and item[1] > 0.0:
                take = min(item[0], demand_rem)
                item[0] -= take
                demand_rem -= take

        # 2. Age by 24h and count Expiring_Units(t) that expire before day's end
        expiring_today = 0.0
        survivors: List[List[float]] = []
        for units, hrs in queue:
            if units <= 1e-6:
                continue
            rem_hrs = hrs - 24.0
            if rem_hrs <= 0.0:
                expiring_today += units
            else:
                survivors.append([units, rem_hrs])

        # 3. Add Scheduled_Inflow(t) as fresh component stock
        if total_daily_inflow > 0.0:
            survivors.append([total_daily_inflow, fresh_shelf_hours])

        survivors.sort(key=lambda item: item[1])
        queue = survivors
        projected_end = round(max(0.0, sum(item[0] for item in queue)), 1)

        days.append(
            ForecastDay(
                day=day,
                label=f"D+{day}",
                projected_stock=projected_end,
                predicted_demand=round(total_daily_demand, 1),
                expiring_units=round(expiring_today, 1),
                scheduled_inflow=round(total_daily_inflow, 1),
            )
        )
    return days


def _build_math_snapshot(
    hospital: Dict[str, Any],
    blood_group: str,
    component: str,
    batches: List[Dict[str, Any]],
    daily_demand: float,
    daily_inflow: float,
    zero_stock_hours: float,
    scenario: ScenarioType,
    donation_drop: float,
    demand_mult: float,
    donor_candidates_evaluated: int = 0,
    selected_donor_post_transfer_hours: Optional[float] = None,
    compatibility_rule: Optional[str] = None,
) -> MathSnapshot:
    current_stock = sum(int(b["units"]) for b in batches)
    exp_48 = sum(int(b["units"]) for b in batches if float(b["hours_to_expiry"]) <= 48.0)
    exp_72 = sum(int(b["units"]) for b in batches if float(b["hours_to_expiry"]) <= 72.0)
    status = classify_status(zero_stock_hours)
    equation = (
        f"Projected_Stock(t) = {current_stock} - {daily_demand:.1f}/d - "
        f"Exp({exp_72}u<=72h) + {daily_inflow:.1f}/d => ZeroStock={zero_stock_hours:.1f}h"
    )
    return MathSnapshot(
        equation=equation,
        hospital_id=hospital["id"],
        hospital_name=hospital["name"],
        blood_group=blood_group,
        component=component,
        current_stock=current_stock,
        daily_demand=round(daily_demand, 2),
        hourly_burn_rate=round(daily_demand / 24.0, 3),
        scheduled_daily_inflow=round(daily_inflow, 2),
        expiring_within_48h=exp_48,
        expiring_within_72h=exp_72,
        zero_stock_hours=zero_stock_hours,
        status=status,
        scenario=scenario,
        donation_drop_pct=donation_drop,
        demand_multiplier=demand_mult,
        donor_candidates_evaluated=donor_candidates_evaluated,
        selected_donor_post_transfer_hours=selected_donor_post_transfer_hours,
        compatibility_rule=compatibility_rule,
    )


def _find_optimal_fefo_transfer(
    receiver: Dict[str, Any],
    recipient_group: str,
    component: str,
    receiver_batches: List[Dict[str, Any]],
    receiver_demand: float,
    receiver_inflow: float,
    receiver_zero_hours: float,
    hospitals_by_id: Dict[str, Dict[str, Any]],
    batches_by_key: Dict[Tuple[str, str, str], List[Dict[str, Any]]],
    rates_by_key: Dict[Tuple[str, str, str], Tuple[float, float]],
    scenario: ScenarioType,
    donation_drop: float,
    demand_mult: float,
) -> Tuple[Optional[FEFORecommendation], int]:
    """
    Rank candidate donor batches strictly by:
    (a) clinical compatibility from rulebook.py (exact match first)
    (b) surplus batches closest to expiry without dropping donor below Watch (>= 48h)
    (c) shortest cold-chain transit time from (x, y) coordinates
    """
    candidates: List[Tuple[Tuple[int, float, int], Dict[str, Any]]] = []

    # Desired transfer volume to restore receiver safety margin
    desired_units = max(4, min(16, int(math.ceil(receiver_demand * 1.4))))

    for donor_id, donor in hospitals_by_id.items():
        if donor_id == receiver["id"]:
            continue

        transit_min = calculate_transit_minutes(
            donor["x"], donor["y"], receiver["x"], receiver["y"]
        )
        min_viable_expiry = (transit_min / 60.0) + 6.0

        for donor_bg in BLOOD_GROUPS:
            compatible, compat_rank, compat_label = is_compatible(
                donor_bg, recipient_group, component
            )
            if not compatible:
                continue

            donor_key = (donor_id, donor_bg, component)
            donor_batches = batches_by_key.get(donor_key, [])
            if not donor_batches:
                continue

            donor_demand, donor_inflow = rates_by_key[donor_key]
            donor_current_hours = compute_zero_stock_hours(
                donor_batches, donor_demand, donor_inflow, component
            )
            # Donor must currently be above Watch threshold or comfortably safe
            if donor_current_hours <= CRITICAL_THRESHOLD_HOURS + 12.0:
                continue

            for batch in donor_batches:
                batch_expiry = float(batch["hours_to_expiry"])
                batch_units = int(batch["units"])
                if batch_units < 2 or batch_expiry <= min_viable_expiry:
                    continue

                # Determine maximum transferable units keeping donor >= Watch (>= 48h)
                max_try = min(batch_units, desired_units)
                best_units = 0
                donor_after_hours = donor_current_hours

                for try_units in range(max_try, 1, -1):
                    sim_batches = []
                    for b in donor_batches:
                        if b["batch_id"] == batch["batch_id"]:
                            rem = int(b["units"]) - try_units
                            if rem > 0:
                                sim_batches.append({**b, "units": rem})
                        else:
                            sim_batches.append(b)
                    post_hours = compute_zero_stock_hours(
                        sim_batches, donor_demand, donor_inflow, component
                    )
                    if post_hours >= CRITICAL_THRESHOLD_HOURS:
                        best_units = try_units
                        donor_after_hours = post_hours
                        break

                if best_units <= 0:
                    continue

                # Compute receiver post-transfer zero-stock countdown
                post_transit_expiry = max(1.0, batch_expiry - (transit_min / 60.0))
                receiver_sim = list(receiver_batches) + [
                    {
                        "batch_id": f"SIM-{batch['batch_id']}",
                        "hospital_id": receiver["id"],
                        "blood_group": donor_bg,
                        "component": component,
                        "units": best_units,
                        "hours_to_expiry": post_transit_expiry,
                    }
                ]
                receiver_after_hours = compute_zero_stock_hours(
                    receiver_sim, receiver_demand, receiver_inflow, component
                )

                # Strict FEFO ranking tuple:
                # 1. Clinical compatibility rank (0 exact < 1 compatible < 2 universal)
                # 2. Earliest expiry first (FEFO)
                # 3. Shortest cold-chain transit ETA
                rank_key = (compat_rank, batch_expiry, transit_min)
                candidates.append(
                    (
                        rank_key,
                        {
                            "donor": donor,
                            "donor_bg": donor_bg,
                            "batch": batch,
                            "units": best_units,
                            "transit_minutes": transit_min,
                            "compat_label": compat_label,
                            "receiver_after_hours": receiver_after_hours,
                            "donor_after_hours": donor_after_hours,
                        },
                    )
                )

    if not candidates:
        return None, 0

    candidates.sort(key=lambda item: item[0])
    winner = candidates[0][1]
    donor = winner["donor"]
    batch = winner["batch"]
    batch_expiry = float(batch["hours_to_expiry"])

    math_inputs = _build_math_snapshot(
        hospital=receiver,
        blood_group=recipient_group,
        component=component,
        batches=receiver_batches,
        daily_demand=receiver_demand,
        daily_inflow=receiver_inflow,
        zero_stock_hours=receiver_zero_hours,
        scenario=scenario,
        donation_drop=donation_drop,
        demand_mult=demand_mult,
        donor_candidates_evaluated=len(candidates),
        selected_donor_post_transfer_hours=winner["donor_after_hours"],
        compatibility_rule=winner["compat_label"],
    )

    rec_id = f"REC-{donor['code']}-{receiver['code']}-{batch['batch_id']}"
    recommendation = FEFORecommendation(
        recommendation_id=rec_id,
        donor_hospital_id=donor["id"],
        donor_hospital_name=donor["name"],
        donor_code=donor["code"],
        receiver_hospital_id=receiver["id"],
        receiver_hospital_name=receiver["name"],
        receiver_code=receiver["code"],
        batch_id=batch["batch_id"],
        donor_blood_group=winner["donor_bg"],
        receiver_blood_group=recipient_group,
        component=component,
        units=winner["units"],
        batch_hours_to_expiry=round(batch_expiry, 1),
        transit_minutes=winner["transit_minutes"],
        compatibility_label=winner["compat_label"],
        receiver_zero_stock_hours_before=receiver_zero_hours,
        receiver_zero_stock_hours_after=winner["receiver_after_hours"],
        donor_hours_after=winner["donor_after_hours"],
        urgency_status=classify_status(receiver_zero_hours),
        expiry_risk_saved=batch_expiry <= 72.0,
        math_inputs=math_inputs,
    )
    return recommendation, len(candidates)


def compute_network_state(
    raw_data: Dict[str, Any],
    scenario: ScenarioType = "baseline",
    donation_drop: float = 0.0,
    demand_mult: float = 1.0,
) -> NetworkStateResponse:
    """Compute complete deterministic network state, forecasts, alerts, and FEFO plans."""
    hospitals_raw: List[Dict[str, Any]] = raw_data["hospitals"]
    profiles_raw: List[Dict[str, Any]] = raw_data["demand_profiles"]
    batches_raw: List[Dict[str, Any]] = raw_data["batches"]
    units_saved: int = int(raw_data["units_saved_from_expiry"])

    hospitals_by_id = {h["id"]: h for h in hospitals_raw}

    # Index batches and effective rates by (hospital_id, blood_group, component)
    batches_by_key: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for b in batches_raw:
        key = (b["hospital_id"], b["blood_group"], b["component"])
        batches_by_key.setdefault(key, []).append(b)

    rates_by_key: Dict[Tuple[str, str, str], Tuple[float, float]] = {}
    for p in profiles_raw:
        eff_d, eff_i = _effective_rates(
            hospital_id=p["hospital_id"],
            blood_group=p["blood_group"],
            component=p["component"],
            base_demand=float(p["base_daily_demand"]),
            base_inflow=float(p["base_daily_inflow"]),
            scenario=scenario,
            donation_drop=donation_drop,
            demand_mult=demand_mult,
        )
        rates_by_key[(p["hospital_id"], p["blood_group"], p["component"])] = (eff_d, eff_i)

    hospital_states: List[HospitalState] = []
    alerts: List[AlertItem] = []
    recommendations: List[FEFORecommendation] = []
    timeline_events: List[TimelineEvent] = []

    most_urgent_hours = float(MAX_SIMULATION_HOURS)
    most_urgent_label = "All Facilities Safe (>120h)"
    most_urgent_hospital_id = hospitals_raw[0]["id"] if hospitals_raw else "HOSP-01"

    critical_pairs_count = 0
    watch_pairs_count = 0

    for h in hospitals_raw:
        hid = h["id"]
        inv_summaries: List[InventorySummary] = []
        hosp_batches_models: List[BatchItem] = []
        hosp_min_hours = float(MAX_SIMULATION_HOURS)
        hosp_critical_pair = "All Stable"
        hosp_total_units = 0

        for bg in BLOOD_GROUPS:
            for comp in COMPONENTS:
                key = (hid, bg, comp)
                pair_batches = batches_by_key.get(key, [])
                daily_demand, daily_inflow = rates_by_key.get(key, (2.0, 2.0))
                total_u = sum(int(b["units"]) for b in pair_batches)
                hosp_total_units += total_u
                exp_72 = sum(int(b["units"]) for b in pair_batches if float(b["hours_to_expiry"]) <= 72.0)
                min_exp = min((float(b["hours_to_expiry"]) for b in pair_batches), default=None)

                zero_hrs = compute_zero_stock_hours(pair_batches, daily_demand, daily_inflow, comp)
                status = classify_status(zero_hrs)

                if status == "Critical":
                    critical_pairs_count += 1
                elif status == "Watch":
                    watch_pairs_count += 1

                if zero_hrs < hosp_min_hours:
                    hosp_min_hours = zero_hrs
                    hosp_critical_pair = f"{bg} {comp}"

                if zero_hrs < most_urgent_hours:
                    most_urgent_hours = zero_hrs
                    most_urgent_label = f"{h['code']} · {bg} {comp}"
                    most_urgent_hospital_id = hid

                inv_summaries.append(
                    InventorySummary(
                        blood_group=bg,
                        component=comp,
                        total_units=total_u,
                        daily_demand=round(daily_demand, 2),
                        scheduled_daily_inflow=round(daily_inflow, 2),
                        expiring_within_72h=exp_72,
                        min_hours_to_expiry=round(min_exp, 1) if min_exp is not None else None,
                        zero_stock_hours=zero_hrs,
                        status=status,
                    )
                )

                for b in pair_batches:
                    hosp_batches_models.append(BatchItem(**b))
                    # Add upcoming 72h expiry events to timeline
                    hrs_exp = float(b["hours_to_expiry"])
                    if hrs_exp <= 72.0:
                        timeline_events.append(
                            TimelineEvent(
                                event_id=f"EXP-{b['batch_id']}",
                                hour_offset=round(hrs_exp, 1),
                                kind="expiry",
                                severity="Critical" if hrs_exp <= 36.0 else "Watch",
                                hospital_id=hid,
                                hospital_code=h["code"],
                                hospital_name=h["name"],
                                blood_group=bg,
                                component=comp,
                                units=int(b["units"]),
                                title=f"{b['units']}u {bg} {comp} Expiring",
                                subtitle=f"{h['code']} batch {b['batch_id']} expires in {hrs_exp:.0f}h",
                            )
                        )

                # Generate Alert & FEFO Recommendation for Critical or Watch pairs
                if status in ("Critical", "Watch"):
                    rec, cand_count = _find_optimal_fefo_transfer(
                        receiver=h,
                        recipient_group=bg,
                        component=comp,
                        receiver_batches=pair_batches,
                        receiver_demand=daily_demand,
                        receiver_inflow=daily_inflow,
                        receiver_zero_hours=zero_hrs,
                        hospitals_by_id=hospitals_by_id,
                        batches_by_key=batches_by_key,
                        rates_by_key=rates_by_key,
                        scenario=scenario,
                        donation_drop=donation_drop,
                        demand_mult=demand_mult,
                    )
                    math_snap = (
                        rec.math_inputs
                        if rec is not None
                        else _build_math_snapshot(
                            hospital=h,
                            blood_group=bg,
                            component=comp,
                            batches=pair_batches,
                            daily_demand=daily_demand,
                            daily_inflow=daily_inflow,
                            zero_stock_hours=zero_hrs,
                            scenario=scenario,
                            donation_drop=donation_drop,
                            demand_mult=demand_mult,
                            donor_candidates_evaluated=cand_count,
                        )
                    )
                    alert_id = f"ALT-{h['code']}-{bg.replace('+', 'P').replace('-', 'N')}-{comp[:3].upper()}"
                    headline = (
                        f"{h['code']} {bg} {comp}: {zero_hrs:.1f}h to zero stock "
                        f"({total_u}u on hand, {daily_demand:.1f}/d burn)"
                    )
                    alert = AlertItem(
                        alert_id=alert_id,
                        hospital_id=hid,
                        hospital_name=h["name"],
                        hospital_code=h["code"],
                        blood_group=bg,
                        component=comp,
                        status=status,
                        zero_stock_hours=zero_hrs,
                        expiring_within_72h=exp_72,
                        current_stock=total_u,
                        daily_demand=round(daily_demand, 2),
                        headline=headline,
                        recommendation=rec,
                        math_inputs=math_snap,
                    )
                    alerts.append(alert)
                    if rec is not None:
                        recommendations.append(rec)

                    if zero_hrs <= 72.0:
                        timeline_events.append(
                            TimelineEvent(
                                event_id=f"SHRT-{alert_id}",
                                hour_offset=round(zero_hrs, 1),
                                kind="shortage",
                                severity=status,
                                hospital_id=hid,
                                hospital_code=h["code"],
                                hospital_name=h["name"],
                                blood_group=bg,
                                component=comp,
                                units=total_u,
                                title=f"{h['code']} {bg} {comp} Depletion",
                                subtitle=(
                                    f"FEFO ready: {rec.units}u from {rec.donor_code} ({rec.transit_minutes}m)"
                                    if rec
                                    else f"Zero-stock window at T+{zero_hrs:.1f}h (No safe surplus)"
                                ),
                                alert_id=alert_id,
                                recommendation_id=rec.recommendation_id if rec else None,
                            )
                        )

        # Build 14-day forecasts per component for this hospital
        forecasts: Dict[str, List[ForecastDay]] = {}
        for comp in COMPONENTS:
            comp_batches = [b for b in batches_raw if b["hospital_id"] == hid and b["component"] == comp]
            comp_demand = sum(rates_by_key.get((hid, bg, comp), (0.0, 0.0))[0] for bg in BLOOD_GROUPS)
            comp_inflow = sum(rates_by_key.get((hid, bg, comp), (0.0, 0.0))[1] for bg in BLOOD_GROUPS)
            forecasts[comp] = project_14_day_component_stock(
                comp_batches, comp_demand, comp_inflow, comp
            )

        hospital_states.append(
            HospitalState(
                id=hid,
                name=h["name"],
                code=h["code"],
                role=h["role"],
                x=float(h["x"]),
                y=float(h["y"]),
                status=classify_status(hosp_min_hours),
                min_zero_stock_hours=round(hosp_min_hours, 1),
                critical_pair=hosp_critical_pair,
                total_units=hosp_total_units,
                inventory=inv_summaries,
                batches=hosp_batches_models,
                forecasts=forecasts,
            )
        )

    # Sort alerts & recommendations by urgency (lowest zero_stock_hours first)
    alerts.sort(key=lambda a: (a.zero_stock_hours, -a.expiring_within_72h))
    recommendations.sort(
        key=lambda r: (
            0 if r.urgency_status == "Critical" else 1,
            r.receiver_zero_stock_hours_before,
            r.batch_hours_to_expiry,
        )
    )

    # Sort 72h timeline chronologically, prioritizing actionable shortage/transfer cards
    timeline_events.sort(key=lambda e: (e.hour_offset, 0 if e.kind == "shortage" else 1))

    # Build regional cold-chain edges with deterministic transit times
    edges: List[NetworkEdge] = []
    for src_id, dst_id in CORRIDOR_PAIRS:
        if src_id in hospitals_by_id and dst_id in hospitals_by_id:
            s_h = hospitals_by_id[src_id]
            d_h = hospitals_by_id[dst_id]
            edges.append(
                NetworkEdge(
                    source_id=src_id,
                    target_id=dst_id,
                    transit_minutes=calculate_transit_minutes(s_h["x"], s_h["y"], d_h["x"], d_h["y"]),
                    distance_km=calculate_distance_km(s_h["x"], s_h["y"], d_h["x"], d_h["y"]),
                )
            )

    # Deterministic Network Readiness Score (0-100)
    urgency_penalty = 0
    if most_urgent_hours < 24.0:
        urgency_penalty = 14
    elif most_urgent_hours < CRITICAL_THRESHOLD_HOURS:
        urgency_penalty = 8
    elif most_urgent_hours <= SAFE_THRESHOLD_HOURS:
        urgency_penalty = 3

    raw_score = 100 - min(48, critical_pairs_count * 7) - min(28, watch_pairs_count * 3) - urgency_penalty
    readiness_score = max(5, min(100, int(round(raw_score))))

    return NetworkStateResponse(
        scenario=scenario,
        donation_drop=donation_drop,
        demand_mult=demand_mult,
        network_readiness_score=readiness_score,
        most_urgent_countdown_hours=round(most_urgent_hours, 1),
        most_urgent_label=most_urgent_label,
        most_urgent_hospital_id=most_urgent_hospital_id,
        units_saved_from_expiry=units_saved,
        total_active_alerts=len(alerts),
        hospitals=hospital_states,
        edges=edges,
        recommendations=recommendations,
        alerts=alerts,
        timeline_72h=timeline_events[:18],
    )
