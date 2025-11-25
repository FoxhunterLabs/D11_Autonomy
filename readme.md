````markdown
# D11 Safety HUD — Predictive Risk Console (Demo)

Streamlit demo of a **predictive safety console** for a D11-class dozer.  
All data is **synthetic** and **non-operational** — this is a UX and logic sandbox for human-gated autonomy, risk surfacing, and audit trails.

---

## Overview

This app simulates a heavy equipment operator HUD that:

- Streams **synthetic machine, ground, and operator telemetry**
- Computes **rollover, slip/traction, obstacle, and GNSS risk**
- Blends those into an **overall risk state**: `STABLE / ELEVATED / HIGH / CRITICAL`
- Generates **human-gated recommendations** (“proposals”) when risk climbs
- Tracks all **alerts, controls, and decisions** in an **audit log**
- Visualizes the situation in a **time-series HUD** and **roll/pitch attitude view**

Use it as a starting point for safety tooling, autonomy gatekeeping, or training UIs.

---

## Features

### 1. Synthetic Telemetry Engine

Each “tick” generates a `TelemetryRow` including:

- **Machine state**: speed, gear, RPM, grade, roll, pitch, blade load, fuel
- **Ground & environment**: ground firmness, moisture index, visibility
- **Sensing**: GNSS HDOP, GNSS jitter, obstacle distance & bearing
- **Operator**: shift hours, micro-corrections per minute
- **Risk outputs**: rollover risk, slip risk, obstacle risk, GNSS confidence, overall risk, state

Patterns simulate:

- Shift progression (fatigue proxy: `shift_hours`, `micro_corrections_per_min`)
- Terrain changes (ramps, benches, wetter/softer ground over time)
- Visibility degrading (dust / lighting)
- Occasional nearby obstacles (e.g., trucks, bench edges)

### 2. Risk Model

Helpers compute risk on top of the raw telemetry:

- `compute_rollover_risk(grade, roll, speed)`
- `compute_slip_risk(grade, moisture, firmness, speed)`
- `compute_obstacle_risk(distance, speed)`
- `compute_gnss_confidence(hdop, jitter, visibility)`
- `compute_overall_risk(...)` with GNSS penalty
- `classify_state(overall_risk)` → `STABLE / ELEVATED / HIGH / CRITICAL`

These are **simple, interpretable formulas**, not ML — meant for explainability and iteration, not production use.

### 3. Human-Gated Proposals

When risk exceeds thresholds, `maybe_generate_proposal(...)` creates **recommendations** such as:

- “Pause travel — obstacle within unsafe margin”
- “Reduce cross-slope exposure and slow to crawl”
- “Back out, re-cut access path, and reassess ground”
- “Switch to local references — GNSS degraded”
- “Hold profile and reduce speed until risk stabilizes”

Each proposal includes:

- Unique ID and timestamp  
- Title and **human-readable rationale** (key conditions/metrics)  
- `PENDING / APPROVED / REJECTED / DEFERRED` status  
- Snapshot of critical telemetry at time of recommendation  

Operators (or supervisors) **approve/reject/defer** proposals via UI.  
Decisions are logged to the **audit trail**.

### 4. Visual Console

Main UI elements:

- **Global status bar**: tick, state badge, risk margin, open recommendations
- **Top metrics**: state, overall risk, speed, gear/RPM, grade/roll, blade load, slip + rollover risk
- **Machine timeline**:  
  - Overall risk (%) vs tick  
  - Grade (%) and roll (°) on secondary axis
- **Operator & ground picture**: ground firmness, moisture, GNSS quality, shift hours, micro-corrections
- **Cab attitude map**: roll vs pitch in a 2D “cabin” box
- **Risk breakdown bar chart**: rollover, slip, obstacle, GNSS penalty
- **Proposal panel**: select proposal, view rationale & snapshot, approve/reject/defer
- **Audit trail**: last 20 entries for alerts, proposals, controls

---

## Getting Started

### Requirements

- Python 3.10+ (recommended)
- Dependencies:
  - `streamlit`
  - `numpy`
  - `pandas`
  - `plotly`

### Install

```bash
pip install streamlit numpy pandas plotly
````

### Run

Save the script as `app.py`, then:

```bash
streamlit run app.py
```

Streamlit will open the console in your browser (default: `http://localhost:8501`).

---

## How to Use the Demo

1. **Start the simulation**

   * Click **“▶ Start Simulation”**
   * Synthetic ticks begin streaming (approx. 1 simulated minute per tick)

2. **Watch the HUD**

   * Track the **risk state** and **risk margin** in the status bar
   * See how grade, roll, moisture, and obstacles push risk from STABLE → CRITICAL
   * Use the **Cab Attitude Map** to visualize roll vs pitch

3. **Handle recommendations**

   * When risk crosses thresholds, **proposals** appear in the **Human-Gated Recommendations** panel
   * Select a proposal, review the rationale and snapshot
   * Click **Approve**, **Reject**, or **Defer** (only when status is `PENDING`)
   * All actions are recorded in the **Audit Trail**

4. **Pause / Reset**

   * **⏸ Pause** to freeze ticks
   * **⟲ Reset** to clear state, history, proposals, and audit entries

---

## Code Structure

* **Data models**

  * `TelemetryRow`: one tick of telemetry + risk + state
  * `Proposal`: recommendation object
  * `AuditEntry`: audit log entry

* **Core logic**

  * State initialization: `init_state()`
  * Risk helpers: `compute_*`, `classify_state`
  * Telemetry generator: `generate_tick(prev)`
  * Proposal engine: `maybe_generate_proposal`, `update_proposal_status`
  * Audit: `log_audit`

* **UI / layout**

  * Status bar: `render_status(latest)`
  * Controls: start / pause / reset buttons
  * Main layout: metrics, plots, proposal panel, audit trail

---

## Safety & Disclaimer

* **All telemetry is synthetic**.
* **Not for real machine control, dispatch, or operational decision-making.**
* Intended for **concept exploration, UI prototyping, and discussions** around safety, human-in-the-loop autonomy, and auditability.

---

## Possible Extensions

* Swap synthetic telemetry with a **real data feed** (with hard safety gates).
* Add **per-operator profiles** or shift logs.
* Integrate with a **fleet-level dashboard**.
* Record/export **JSON/CSV** of telemetry, proposals, and decisions for offline analysis.
* Plug in more advanced models (while keeping human-gated control).

```
```
