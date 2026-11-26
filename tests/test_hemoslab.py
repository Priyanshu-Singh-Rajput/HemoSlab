"""Automated unit and API integration tests for HemoSlab."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import database
from engine.math_engine import compute_network_state
from engine.rulebook import (
    calculate_distance_km,
    calculate_transit_minutes,
    classify_status,
    is_compatible,
)
from main import app


class HemoSlabRulebookTests(unittest.TestCase):
    def test_abo_rh_compatibility(self) -> None:
        ok_exact, priority_exact, _ = is_compatible("O-", "O-")
        self.assertTrue(ok_exact)
        self.assertEqual(priority_exact, 0)

        ok_universal, priority_univ, _ = is_compatible("O-", "A+")
        self.assertTrue(ok_universal)
        self.assertEqual(priority_univ, 1)

        ok_invalid, _, _ = is_compatible("AB+", "O-")
        self.assertFalse(ok_invalid)

    def test_status_thresholds(self) -> None:
        self.assertEqual(classify_status(24.0), "Critical")
        self.assertEqual(classify_status(48.0), "Watch")
        self.assertEqual(classify_status(120.0), "Watch")
        self.assertEqual(classify_status(120.1), "Safe")

    def test_real_ranchi_distances_and_eta(self) -> None:
        # RIMS (50, 18) -> Sadar Hospital (20, 72)
        dist = calculate_distance_km(50.0, 18.0, 20.0, 72.0)
        self.assertGreater(dist, 2.0)
        self.assertLess(dist, 10.0)
        self.assertGreaterEqual(calculate_transit_minutes(50.0, 18.0, 20.0, 72.0), 14)
        self.assertEqual(calculate_transit_minutes(50.0, 18.0, 50.0, 18.0), 0)


class HemoSlabEngineAndApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._orig_db_path = database.DB_PATH
        database.DB_PATH = Path(cls._tmpdir.name) / "test_hemoslab.db"
        database.init_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        database.DB_PATH = cls._orig_db_path
        cls._tmpdir.cleanup()

    def test_math_engine_baseline_and_scenarios(self) -> None:
        raw = database.fetch_network_raw_data()
        baseline = compute_network_state(raw, scenario="baseline")
        self.assertEqual(len(baseline.hospitals), 6)
        self.assertGreater(len(baseline.alerts), 0)
        self.assertGreater(len(baseline.recommendations), 0)

        dengue = compute_network_state(raw, scenario="dengue", donation_drop=20.0, demand_mult=1.5)
        self.assertLessEqual(dengue.network_readiness_score, baseline.network_readiness_score)

    def test_pages_and_api_routes(self) -> None:
        for route in [
            "/",
            "/dashboard",
            "/static/styles.css",
            "/static/landing.css",
            "/static/app.js",
            "/static/landing.js",
        ]:
            resp = self.client.get(route)
            self.assertEqual(resp.status_code, 200, f"Route {route} returned {resp.status_code}")

        state_resp = self.client.get("/api/network/state?scenario=baseline")
        self.assertEqual(state_resp.status_code, 200)
        payload = state_resp.json()
        self.assertEqual(len(payload["hospitals"]), 6)

        audit_resp = self.client.get("/api/audit")
        self.assertEqual(audit_resp.status_code, 200)
        self.assertIn("logs", audit_resp.json())

    def test_atomic_dispatch_and_reset(self) -> None:
        state = self.client.get("/api/network/state?scenario=baseline").json()
        rec = state["recommendations"][0]

        dispatch_resp = self.client.post(
            "/api/transfers/dispatch",
            json={
                "donor_hospital_id": rec["donor_hospital_id"],
                "receiver_hospital_id": rec["receiver_hospital_id"],
                "batch_id": rec["batch_id"],
                "units": rec["units"],
                "scenario": "baseline",
                "donation_drop": 0.0,
                "demand_mult": 1.0,
                "transit_minutes": rec["transit_minutes"],
                "math_snapshot": rec["math_inputs"],
            },
        )
        self.assertEqual(dispatch_resp.status_code, 200)
        d_json = dispatch_resp.json()
        self.assertEqual(d_json["status"], "dispatched")
        self.assertEqual(d_json["units_transferred"], rec["units"])

        reset_resp = self.client.post("/api/reset?scenario=baseline")
        self.assertEqual(reset_resp.status_code, 200)

    def test_briefing_endpoint_deterministic_fallback(self) -> None:
        state = self.client.get("/api/network/state?scenario=baseline").json()
        alert = state["alerts"][0]
        rec = state["recommendations"][0]
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            resp = self.client.post("/api/briefing", json={"alert": alert, "recommendation": rec})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for key in ["cause", "math_trigger", "recommended_action", "donor_sms"]:
            self.assertIn(key, data)
            self.assertTrue(len(data[key]) > 0)
        self.assertLessEqual(len(data["donor_sms"]), 160)

    def test_accessibility_attributes_present(self) -> None:
        static_dir = Path(__file__).resolve().parent.parent / "static"
        for fname in ["index.html", "landing.html"]:
            html = (static_dir / fname).read_text(encoding="utf-8")
            self.assertIn('lang="en"', html)
            self.assertIn("skip-link", html)
            self.assertIn('id="main-content"', html)
            self.assertIn("<h1", html)
            self.assertIn('name="description"', html)


if __name__ == "__main__":
    unittest.main()
