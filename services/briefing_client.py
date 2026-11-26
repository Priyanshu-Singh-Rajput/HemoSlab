"""
HemoSlab Structured AI Briefing Client.

Uses the `google-genai` Python SDK with model `gemini-3.5-flash-lite` and strict
Pydantic structured output (`response_mime_type="application/json"`,
`response_schema=GeminiBriefingPayload`).

Includes a mandatory deterministic offline fallback so the application operates
100% reliably even when `GEMINI_API_KEY` is unset or the network is unavailable.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from dotenv import load_dotenv

from models import (
    AlertItem,
    FEFORecommendation,
    GeminiBriefingPayload,
    StructuredBriefing,
    model_to_dict,
)

load_dotenv()

GEMINI_MODEL = "gemini-3.5-flash-lite"


def _enforce_sms_limit(sms: str, max_len: int = 160) -> str:
    cleaned = " ".join(sms.strip().split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "."


def _build_deterministic_briefing(
    alert: AlertItem,
    recommendation: Optional[FEFORecommendation] = None,
) -> StructuredBriefing:
    """Generate the exact 4-field StructuredBriefing deterministically from math_engine outputs."""
    m = alert.math_inputs
    rec = recommendation or alert.recommendation

    scenario_phrase = {
        "baseline": "routine clinical utilization",
        "dengue": "monsoon dengue surge (+180% platelet burn)",
        "trauma": "regional trauma surge depleting O-group trauma reserves",
    }.get(m.scenario, "active clinical demand")

    if alert.expiring_within_72h > 0:
        cause = (
            f"{alert.hospital_name} ({alert.hospital_code}) faces a {alert.status.lower()} "
            f"{alert.blood_group} {alert.component} deficit under {scenario_phrase}, "
            f"compounded by {alert.expiring_within_72h} units nearing shelf-life expiry."
        )
    else:
        cause = (
            f"{alert.hospital_name} ({alert.hospital_code}) is depleting {alert.blood_group} "
            f"{alert.component} under {scenario_phrase} faster than scheduled daily inflow can replenish."
        )

    if alert.expiring_within_72h > 0:
        math_trigger = (
            f"{alert.expiring_within_72h} {alert.blood_group} {alert.component} units expiring <=72h "
            f"against {m.daily_demand:.1f}/day burn rate ({alert.current_stock}u on hand); "
            f"zero-stock in {alert.zero_stock_hours:.1f}h."
        )
    else:
        math_trigger = (
            f"{alert.current_stock} {alert.blood_group} {alert.component} units on hand vs "
            f"{m.daily_demand:.1f}/day burn and {m.scheduled_daily_inflow:.1f}/day inflow; "
            f"zero-stock in {alert.zero_stock_hours:.1f}h."
        )

    if rec is not None:
        expiry_note = (
            f"saving {rec.units}u expiring in {rec.batch_hours_to_expiry:.0f}h"
            if rec.expiry_risk_saved
            else f"batch shelf life {rec.batch_hours_to_expiry:.0f}h"
        )
        recommended_action = (
            f"Dispatch {rec.units}u {rec.donor_blood_group} {rec.component} (Batch {rec.batch_id}) "
            f"from {rec.donor_hospital_name} ({rec.donor_code}) to {rec.receiver_hospital_name} "
            f"({rec.receiver_code}), {expiry_note}, ETA {rec.transit_minutes} min "
            f"({rec.compatibility_label}; extends buffer to {rec.receiver_zero_stock_hours_after:.1f}h)."
        )
    else:
        recommended_action = (
            f"No regional facility holds safe transferable surplus above Watch threshold (48h) for "
            f"{alert.blood_group} {alert.component}; activate emergency regional donor drive and "
            f"cross-bank mutual-aid escalation for {alert.hospital_code}."
        )

    sms = (
        f"HEMOSLAB URGENT: {alert.blood_group} {alert.component} needed at {alert.hospital_name} "
        f"({alert.zero_stock_hours:.0f}h buffer). Donate today at Regional Blood Bank. Reply YES."
    )

    return StructuredBriefing(
        cause=cause,
        math_trigger=math_trigger,
        recommended_action=recommended_action,
        donor_sms_draft=_enforce_sms_limit(sms, 160),
        source="deterministic_fallback",
    )


def generate_structured_briefing(
    alert: AlertItem,
    recommendation: Optional[FEFORecommendation] = None,
) -> StructuredBriefing:
    """
    Generate a strict 4-field StructuredBriefing using Gemini (`gemini-3.5-flash-lite`)
    with Pydantic structured output, falling back deterministically if offline or unconfigured.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return _build_deterministic_briefing(alert, recommendation)

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return _build_deterministic_briefing(alert, recommendation)

    rec = recommendation or alert.recommendation
    payload = {
        "alert": model_to_dict(alert),
        "recommendation": model_to_dict(rec) if rec is not None else None,
    }

    prompt = (
        "You are HemoSlab's clinical blood-bank operations briefing engine. "
        "Using ONLY the exact deterministic numbers, hospital names, batch IDs, and FEFO transfer "
        "plan in the JSON payload below, produce a strict 4-field JSON briefing:\n"
        "- cause: 1 crisp clinical/operational sentence.\n"
        "- math_trigger: exact numerical trigger (stock, burn rate, expiry hours, zero-stock hours).\n"
        "- recommended_action: exact FEFO transfer instruction (donor, receiver, units, batch expiry saved, ETA).\n"
        "- donor_sms_draft: actionable local donor mobilization SMS strictly under 160 characters.\n\n"
        f"DETERMINISTIC_PAYLOAD:\n{json.dumps(payload, indent=2)}"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeminiBriefingPayload,
                temperature=0.15,
            ),
        )
        raw_text = (response.text or "").strip()
        if not raw_text:
            return _build_deterministic_briefing(alert, recommendation)

        parsed = json.loads(raw_text)
        validated = GeminiBriefingPayload(**parsed)
        return StructuredBriefing(
            cause=validated.cause.strip(),
            math_trigger=validated.math_trigger.strip(),
            recommended_action=validated.recommended_action.strip(),
            donor_sms_draft=_enforce_sms_limit(validated.donor_sms_draft, 160),
            source="gemini",
        )
    except Exception:
        return _build_deterministic_briefing(alert, recommendation)
