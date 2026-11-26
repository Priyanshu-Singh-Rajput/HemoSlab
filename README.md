# HemoSlab

Deterministic, AI-assisted predictive blood shortage and FEFO (First-Expired, First-Out) allocation network connecting 6 regional hospitals and blood banks.

## Quick Start (3 Steps)

1. **Install dependencies** (from inside the `hemoslab/` directory):
   ```bash
   pip install -r requirements.txt
   ```
2. *(Optional)* **Enable live Gemini structured briefings**:
   Set `GEMINI_API_KEY` in your environment or a `.env` file in `hemoslab/`. If unset or offline, HemoSlab automatically runs its deterministic offline briefing fallback with the exact same 4-field schema.
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```
3. **Run the server**:
   ```bash
   uvicorn main:app --reload
   ```
   Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

## Architecture Overview

- `engine/rulebook.py` — Pure Python clinical ABO/Rh transfusion matrix, component shelf lives (`Platelets: 120h`, `RBCs: 1008h`, `Plasma: 8760h`), and safety thresholds (`Safe >120h`, `Watch 48h–120h`, `Critical <48h`).
- `engine/math_engine.py` — Pure Python 14-day stock decay forecast, hourly Zero-Stock Countdown, and FEFO transfer optimizer.
- `services/briefing_client.py` — `google-genai` (`gemini-3.5-flash-lite`) strict Pydantic structured output client with deterministic offline fallback.
- `database.py` — SQLite3 persistence (`hemoslab.db`, auto-seeded on first start) with atomic FEFO transfers and audit logging.
- `main.py` — FastAPI REST API and static frontend host.
- `static/` — Tactile 2D-in-3D structural UI with pure-SVG topology map, animated FEFO transfer pulses, 72-hour flow timeline, Chart.js 14-day forecast, and Audit & Ask drawer.
