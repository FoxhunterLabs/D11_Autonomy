# ================================================================
# D11 SAFETY HUD — Predictive Risk Console (Demo)
# Heavy Equipment Operator Console · Synthetic Telemetry Only
# ================================================================
import time
import random
from dataclasses import dataclass, asdict
from typing import Dict, Any, List

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ------------------------------------------------
# Page Config
# ------------------------------------------------
st.set_page_config(
page_title="D11 Safety HUD — Predictive Risk Console",
layout="wide",
)

# ------------------------------------------------
# Header + Basic Styling
# ------------------------------------------------

st.markdown(
"""
<style>
.title {
font-size: 32px;
font-weight: 700;
letter-spacing: 1px;
color: #ffcc00;
text-transform: uppercase;
margin-bottom: 0px;
}
.subtitle {
font-size: 14px;
color: #CFD8DC;
margin-top: -6px;
margin-bottom: 12px;
}
.status-bar {
background-color: #111;
padding: 10px 14px;
border-radius: 6px;
margin-bottom: 12px;
display: flex;
justify-content: space-between;
font-size: 13px;
color: #ECEFF1;

}
.status-item span.label {
opacity: 0.7;
margin-right: 4px;
}
</style>
""",
unsafe_allow_html=True,
)

st.markdown("<div class='title'>D11 Safety HUD</div>", unsafe_allow_html=True)
st.markdown(
"<div class='subtitle'>Predictive Risk Console · Synthetic Mine Site · Human-Gated
Actions</div>",
unsafe_allow_html=True,
)

# ================================================================
# Data Structures
# ================================================================
@dataclass
class TelemetryRow:
tick: int
ts: float

# Machine state

speed_kph: float
gear: int
engine_rpm: int
grade_pct: float
roll_deg: float
pitch_deg: float
blade_load_pct: float
fuel_pct: float

# Environment / footing
ground_firmness: float # 0..1, lower = softer
moisture_index: float # 0..1
visibility: float # 0..1

# Sensing
gnss_hdop: float
gnss_jitter_m: float
obstacle_distance_m: float # 0..40, 999 = none
obstacle_bearing_deg: float

# Operator state
shift_hours: float
micro_corrections_per_min: float

# Risks
rollover_risk: float

slip_risk: float
obstacle_risk: float
gnss_confidence: float
overall_risk: float
state: str

@dataclass
class Proposal:
id: int
created_ts: float
title: str
rationale: str
status: str # PENDING / APPROVED / REJECTED / DEFERRED
snapshot: Dict[str, Any]

@dataclass
class AuditEntry:
ts: float
kind: str
summary: str
meta: Dict[str, Any] = None

# ================================================================

# Session State Init
# ================================================================
def init_state():
ss = st.session_state
ss.tick = 0
ss.running = False
ss.last_update = time.time()
ss.history: List[Dict[str, Any]] = []
ss.proposals: List[Proposal] = []
ss.audit: List[AuditEntry] = []
ss.next_proposal_id = 1

if "tick" not in st.session_state:
init_state()

ss = st.session_state

# ================================================================
# Risk & Physics Helpers
# ================================================================
def clamp(v: float, lo: float, hi: float) -> float:
return max(lo, min(hi, v))

def log_audit(kind: str, summary: str, meta: Dict[str, Any] | None = None):

ss.audit.append(AuditEntry(ts=time.time(), kind=kind, summary=summary, meta=meta
or {}))
ss.audit = ss.audit[-150:]

def compute_rollover_risk(grade_pct: float, roll_deg: float, speed_kph: float) -> float:
# Simple synthetic: cross-slope + speed pushes risk up
grade_factor = abs(grade_pct) / 25.0 # up to about 1
roll_factor = abs(roll_deg) / 20.0
speed_factor = speed_kph / 12.0
base = 55 * roll_factor + 30 * grade_factor + 25 * speed_factor
return float(clamp(base, 0, 100))

def compute_slip_risk(grade_pct: float, moisture: float, firmness: float, speed_kph: float) ->
float:
# Wet + soft + downhill + speed => higher slip
downhill_factor = clamp((grade_pct / 20.0), -1.2, 1.2)
downhill_factor = max(0.0, downhill_factor) # only downhill contributes
moisture_factor = moisture
softness_factor = 1.0 - firmness
speed_factor = speed_kph / 10.0
base = 40 * downhill_factor + 35 * moisture_factor + 35 * softness_factor + 20 *
speed_factor
return float(clamp(base, 0, 100))

def compute_gnss_confidence(hdop: float, jitter_m: float, visibility: float) -> float:
# Lower hdop + low jitter + good vis => higher confidence
hdop_term = clamp((3.5 - hdop) / 3.5, 0.0, 1.0)
jitter_term = clamp((3.0 - jitter_m) / 3.0, 0.0, 1.0)
vis_term = clamp(visibility, 0.0, 1.0)
conf = 0.45 * hdop_term + 0.35 * jitter_term + 0.20 * vis_term
return float(clamp(conf * 100.0, 0, 100))

def compute_obstacle_risk(distance_m: float, speed_kph: float) -> float:
if distance_m >= 80 or distance_m == 999:
return 0.0
# Very rough time-to-contact style metric
speed_mps = speed_kph / 3.6
if speed_mps < 0.1:
speed_mps = 0.1
ttc = distance_m / speed_mps # seconds
if ttc > 40:
base = 10
elif ttc > 20:
base = 35
elif ttc > 10:
base = 60
else:
base = 85
return float(clamp(base, 0, 100))

def compute_overall_risk(rollover: float, slip: float, obstacle: float, gnss_conf: float) ->
float:
# Weighted blend; low GNSS confidence nudges risk up
gnss_penalty = (100 - gnss_conf) * 0.25
base = 0.38 * rollover + 0.34 * slip + 0.28 * obstacle + gnss_penalty
return float(clamp(base, 0, 100))

def classify_state(overall_risk: float) -> str:
if overall_risk < 25:
return "STABLE"
if overall_risk < 50:
return "ELEVATED"
if overall_risk < 75:
return "HIGH"
return "CRITICAL"

# ================================================================
# Synthetic Telemetry Generator
# ================================================================
def generate_tick(prev: Dict[str, Any] | None) -> TelemetryRow:
tick = ss.tick + 1
base_ts = time.time()

rng = np.random.default_rng(seed=int(base_ts * 1000) % (2**32 - 1))

if prev is None:
speed_kph = 0.0
gear = 1
engine_rpm = 800
grade_pct = 0.0
roll_deg = 0.0
pitch_deg = 0.0
blade_load_pct = 0.0
fuel_pct = 90.0
ground_firmness = 0.7
moisture_index = 0.3
visibility = 0.9
gnss_hdop = 0.8
gnss_jitter_m = 0.3
obstacle_distance_m = 999.0
obstacle_bearing_deg = 0.0
shift_hours = 2.0
micro_corr = 22.0
else:
speed_kph = float(prev["speed_kph"])
grade_pct = float(prev["grade_pct"])
roll_deg = float(prev["roll_deg"])
pitch_deg = float(prev["pitch_deg"])

blade_load_pct = float(prev["blade_load_pct"])
fuel_pct = float(prev["fuel_pct"])
ground_firmness = float(prev["ground_firmness"])
moisture_index = float(prev["moisture_index"])
visibility = float(prev["visibility"])
gnss_hdop = float(prev["gnss_hdop"])
gnss_jitter_m = float(prev["gnss_jitter_m"])
obstacle_distance_m = float(prev["obstacle_distance_m"])
obstacle_bearing_deg = float(prev["obstacle_bearing_deg"])
shift_hours = float(prev["shift_hours"])
micro_corr = float(prev["micro_corrections_per_min"])
gear = int(prev["gear"])
engine_rpm = int(prev["engine_rpm"])

# Simple time-of-shift patterns
shift_hours += 1.0 / 60.0 # each tick ~1 minute of synthetic time

# Speed & gear pattern (slow work, sometimes reversing, sometimes moving)
mode = (tick // 40) % 4 # crawl, push, reposition, reverse
if mode == 0: # crawl
target_speed = 2.0
elif mode == 1: # pushing
target_speed = 5.0
elif mode == 2: # repositioning
target_speed = 8.0
else: # reverse

target_speed = 3.0

speed_kph += rng.normal(loc=(target_speed - speed_kph) * 0.25, scale=0.5)
speed_kph = float(clamp(speed_kph, 0.0, 12.0))

# Gear & RPM roughly track speed
gear = int(clamp(round(1 + speed_kph / 3.0), 1, 4))
engine_rpm = int(clamp(800 + speed_kph * 120 + rng.normal(0, 80), 800, 2100))

# Terrain grade evolves slowly, sometimes stepping to simulate benches / ramps
if tick % 50 == 0:
grade_pct += rng.normal(0, 4.0)
grade_pct += rng.normal(0, 0.5)
grade_pct = float(clamp(grade_pct, -22.0, 22.0))

# Roll/pitch wobble
roll_deg += rng.normal(grade_pct * 0.03, 1.0)
pitch_deg += rng.normal(grade_pct * 0.04, 0.8)
roll_deg = float(clamp(roll_deg, -18.0, 18.0))
pitch_deg = float(clamp(pitch_deg, -15.0, 15.0))

# Blade load (heavier during pushing phases)
if mode in (0, 1):
target_load = 70 + 20 * rng.random()
else:
target_load = 20 * rng.random()

blade_load_pct += rng.normal((target_load - blade_load_pct) * 0.3, 4.0)
blade_load_pct = float(clamp(blade_load_pct, 0.0, 115.0))

# Fuel burn
fuel_pct -= 0.03 + speed_kph * 0.01
fuel_pct = float(clamp(fuel_pct, 5.0, 100.0))

# Ground & moisture slowly drift (rain event style)
if tick % 120 == 0:
moisture_index += rng.normal(0.15, 0.05)
moisture_index += rng.normal(0.0, 0.01)
moisture_index = float(clamp(moisture_index, 0.1, 0.95))

ground_firmness += rng.normal(-0.015 * moisture_index, 0.01)
ground_firmness = float(clamp(ground_firmness, 0.25, 0.95))

# Visibility (dust, lighting)
visibility += rng.normal(-0.004, 0.01)
visibility = float(clamp(visibility, 0.3, 1.0))

# GNSS quality
gnss_hdop += rng.normal(0.02 * (1.0 - visibility), 0.04)
gnss_hdop = float(clamp(gnss_hdop, 0.5, 3.5))

gnss_jitter_m += rng.normal(0.05 * (1.0 - visibility), 0.06)
gnss_jitter_m = float(clamp(gnss_jitter_m, 0.15, 3.0))

# Obstacles: occasionally a truck or bench edge wanders into proximity
if rng.random() < 0.06:
obstacle_distance_m = float(rng.uniform(6.0, 35.0))
obstacle_bearing_deg = float(rng.uniform(-120, 120))
else:
# slowly relax away
obstacle_distance_m += 3.0
if obstacle_distance_m > 80:
obstacle_distance_m = 999.0

# Operator behaviour
micro_corr += rng.normal(0.1 * (abs(grade_pct) + abs(roll_deg)) / 20.0, 1.0)
micro_corr = float(clamp(micro_corr, 8.0, 60.0))

# --- Compute risks
rollover_risk = compute_rollover_risk(grade_pct, roll_deg, speed_kph)
slip_risk = compute_slip_risk(grade_pct, moisture_index, ground_firmness, speed_kph)
obstacle_risk = compute_obstacle_risk(obstacle_distance_m, speed_kph)
gnss_conf = compute_gnss_confidence(gnss_hdop, gnss_jitter_m, visibility)
overall_risk = compute_overall_risk(rollover_risk, slip_risk, obstacle_risk, gnss_conf)
state = classify_state(overall_risk)

return TelemetryRow(
tick=tick,
ts=base_ts,

speed_kph=speed_kph,
gear=gear,
engine_rpm=engine_rpm,
grade_pct=grade_pct,
roll_deg=roll_deg,
pitch_deg=pitch_deg,
blade_load_pct=blade_load_pct,
fuel_pct=fuel_pct,
ground_firmness=ground_firmness,
moisture_index=moisture_index,
visibility=visibility,
gnss_hdop=gnss_hdop,
gnss_jitter_m=gnss_jitter_m,
obstacle_distance_m=obstacle_distance_m,
obstacle_bearing_deg=obstacle_bearing_deg,
shift_hours=shift_hours,
micro_corrections_per_min=micro_corr,
rollover_risk=rollover_risk,
slip_risk=slip_risk,
obstacle_risk=obstacle_risk,
gnss_confidence=gnss_conf,
overall_risk=overall_risk,
state=state,
)

# ================================================================
# Proposal Engine
# ================================================================
def maybe_generate_proposal(latest: TelemetryRow):
# Limit outstanding proposals
open_pending = [p for p in ss.proposals if p.status == "PENDING"]
if len(open_pending) >= 4:
return

triggers: List[str] = []

if latest.overall_risk > 65:
triggers.append("high_overall_risk")
if latest.rollover_risk > 70:
triggers.append("rollover_exposure")
if latest.slip_risk > 70:
triggers.append("traction_margin_low")
if latest.obstacle_risk > 60:
triggers.append("obstacle_close")
if latest.gnss_confidence < 55:
triggers.append("low_gnss_conf")

if not triggers:
return

# Build human-legible proposal

if "obstacle_close" in triggers:
title = "Pause travel — obstacle within unsafe margin"
elif "rollover_exposure" in triggers:
title = "Reduce cross-slope exposure and slow to crawl"
elif "traction_margin_low" in triggers:
title = "Back out, re-cut access path, and reassess ground"
elif "low_gnss_conf" in triggers:
title = "Switch to local references — GNSS degraded"
else:
title = "Hold profile and reduce speed until risk stabilizes"

bits = []
if "high_overall_risk" in triggers:
bits.append(f"overall risk {latest.overall_risk:.1f}% > safe band")
if "rollover_exposure" in triggers:
bits.append(f"roll angle {latest.roll_deg:.1f}° on grade {latest.grade_pct:.1f}%")
if "traction_margin_low" in triggers:
bits.append(
f"slip risk elevated (moisture {latest.moisture_index:.2f}, firmness
{latest.ground_firmness:.2f})"
)
if "obstacle_close" in triggers and latest.obstacle_distance_m != 999:
bits.append(f"obstacle at {latest.obstacle_distance_m:.1f} m, bearing
{latest.obstacle_bearing_deg:.0f}°")
if "low_gnss_conf" in triggers:
bits.append(f"GNSS confidence {latest.gnss_confidence:.0f}%")

rationale = " · ".join(bits)

proposal = Proposal(
id=ss.next_proposal_id,
created_ts=time.time(),
title=title,
rationale=rationale,
status="PENDING",
snapshot={
"tick": latest.tick,
"overall_risk": latest.overall_risk,
"rollover_risk": latest.rollover_risk,
"slip_risk": latest.slip_risk,
"obstacle_risk": latest.obstacle_risk,
"gnss_confidence": latest.gnss_confidence,
"grade_pct": latest.grade_pct,
"roll_deg": latest.roll_deg,
"speed_kph": latest.speed_kph,
"obstacle_distance_m": latest.obstacle_distance_m,
},
)
ss.proposals.append(proposal)
ss.next_proposal_id += 1
log_audit("proposal", f"Proposal #{proposal.id}: {proposal.title}", {"rationale": rationale})

def update_proposal_status(prop: Proposal, new_status: str):
old = prop.status
prop.status = new_status
log_audit("decision", f"{new_status} → Proposal #{prop.id}", {"title": prop.title, "prev": old})

# ================================================================
# Global Status Bar
# ================================================================
def render_status(latest: TelemetryRow | None):
if latest is None:
clarity_label = "No data yet"
state_badge = "—"
else:
clarity_label = f"{100 - latest.overall_risk:.1f}% margin"
state_badge = latest.state

recent_state = state_badge
color = " " if recent_state == "STABLE" else \
" " if recent_state == "ELEVATED" else \
" " if recent_state == "HIGH" else " "

active_props = sum(1 for p in ss.proposals if p.status == "PENDING")

st.markdown(
f"""

<div class="status-bar">
<div class="status-item"><span class="label">Tick:</span> {ss.tick}</div>
<div class="status-item"><span class="label">State:</span> {color}
{recent_state}</div>
<div class="status-item"><span class="label">Risk Margin:</span>
{clarity_label}</div>
<div class="status-item"><span class="label">Open Recommendations:</span>
{active_props}</div>
</div>
""",
unsafe_allow_html=True,
)

# ================================================================
# Controls
# ================================================================
ctrl_left, ctrl_mid, ctrl_right = st.columns([1.3, 1, 1])

with ctrl_left:
if st.button("▶ Start Simulation", use_container_width=True):
ss.running = True
ss.last_update = time.time()
log_audit("control", "Simulation started", {})

with ctrl_mid:
if st.button("⏸ Pause", use_container_width=True):

ss.running = False
log_audit("control", "Simulation paused", {})

with ctrl_right:
if st.button("⟲ Reset", use_container_width=True):
init_state()
log_audit("control", "Simulation reset", {})

# ================================================================
# Simulation Step (auto-tick)
# ================================================================
DT_SECONDS = 1.0

if ss.running and (time.time() - ss.last_update) >= DT_SECONDS:
prev_row = ss.history[-1] if ss.history else None
latest_row = generate_tick(prev_row)
ss.tick = latest_row.tick
ss.history.append(asdict(latest_row))
ss.history = ss.history[-600:]
ss.last_update = time.time()

if latest_row.state in ("HIGH", "CRITICAL"):
log_audit(
"alert",
f"{latest_row.state} risk at tick {latest_row.tick}",
{"overall_risk": latest_row.overall_risk},

)
maybe_generate_proposal(latest_row)
st.rerun()

# ================================================================
# Main Layout
# ================================================================
latest = ss.history[-1] if ss.history else None
render_status(latest if latest else None)

if not ss.history:
st.info("Press **Start Simulation** to bring the D11 Safety HUD online. All data is
synthetic and non-operational.")
st.stop()

df = pd.DataFrame(ss.history)
latest = df.iloc[-1]

top_cols = st.columns(4)
with top_cols[0]:
st.metric("State", latest["state"])
st.metric("Overall Risk", f"{latest['overall_risk']:.1f}%")
with top_cols[1]:
st.metric("Speed", f"{latest['speed_kph']:.1f} km/h")
st.metric("Gear / RPM", f"{int(latest['gear'])} / {int(latest['engine_rpm'])} rpm")
with top_cols[2]:

st.metric("Grade / Roll", f"{latest['grade_pct']:.1f}% / {latest['roll_deg']:.1f}°")
st.metric("Blade Load", f"{latest['blade_load_pct']:.0f}%")
with top_cols[3]:
st.metric("Slip Risk", f"{latest['slip_risk']:.1f}%")
st.metric("Rollover Risk", f"{latest['rollover_risk']:.1f}%")

st.markdown("---")

left, right = st.columns([1.4, 1.0])

# ------------------------------------------------
# LEFT: Time Series & Machine Picture
# ------------------------------------------------
with left:
st.subheader("Machine Timeline (Last 120 Ticks)")

tail = df.tail(120)

fig = make_fig = go.Figure()
fig.add_trace(
go.Scatter(
x=tail["tick"],
y=tail["overall_risk"],
name="Overall Risk",
line=dict(width=2),
yaxis="y1",

)
)
fig.add_trace(
go.Scatter(
x=tail["tick"],
y=tail["roll_deg"],
name="Roll (°)",
line=dict(dash="dot"),
yaxis="y2",
)
)
fig.add_trace(
go.Scatter(
x=tail["tick"],
y=tail["grade_pct"],
name="Grade (%)",
line=dict(dash="dot"),
yaxis="y2",
)
)

fig.update_layout(
height=320,
margin=dict(l=40, r=10, t=10, b=40),
xaxis=dict(title="Tick"),
yaxis=dict(

title="Risk (%)",
range=[0, 100],
),
yaxis2=dict(
title="Grade / Roll",
overlaying="y",
side="right",
),
legend=dict(orientation="h", yanchor="bottom", y=-0.25),
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Operator & Ground Picture")

info_cols = st.columns(3)
with info_cols[0]:
st.metric("Ground Firmness", f"{latest['ground_firmness']:.2f}")
st.metric("Moisture Index", f"{latest['moisture_index']:.2f}")
with info_cols[1]:
st.metric("GNSS HDOP", f"{latest['gnss_hdop']:.2f}")
st.metric("GNSS Jitter", f"{latest['gnss_jitter_m']:.2f} m")
with info_cols[2]:
st.metric("Shift Hours", f"{latest['shift_hours']:.1f} h")
st.metric("Micro Corrections", f"{latest['micro_corrections_per_min']:.0f}/min")

# Simple cabin view: roll vs pitch

cabin_fig = go.Figure()
cabin_fig.add_shape(
type="rect",
x0=-15,
y0=-15,
x1=15,
y1=15,
line=dict(color="#888"),
)
cabin_fig.add_trace(
go.Scatter(
x=[latest["roll_deg"]],
y=[latest["pitch_deg"]],
mode="markers",
marker=dict(size=18),
name="Cab Attitude",
)
)
cabin_fig.update_layout(
title="Cab Attitude Map (Roll vs Pitch)",
xaxis=dict(title="Roll (°)", range=[-20, 20]),
yaxis=dict(title="Pitch (°)", range=[-18, 18]),
height=280,
margin=dict(l=40, r=10, t=40, b=40),
)
st.plotly_chart(cabin_fig, use_container_width=True)

# ------------------------------------------------
# RIGHT: Risk Breakdown, Proposals, Audit
# ------------------------------------------------
with right:
st.subheader("Risk Breakdown (Current Tick)")

risk_df = pd.DataFrame(
{
"Mode": ["Rollover", "Slip / Traction", "Obstacle", "GNSS Confidence"],
"Value": [
latest["rollover_risk"],
latest["slip_risk"],
latest["obstacle_risk"],
100 - latest["gnss_confidence"],
],
}
)

bar_fig = px.bar(
risk_df,
x="Mode",
y="Value",
range_y=[0, 100],
height=260,
)

bar_fig.update_layout(margin=dict(l=40, r=10, t=10, b=40))
st.plotly_chart(bar_fig, use_container_width=True)

st.markdown(
f"**GNSS Confidence:** {latest['gnss_confidence']:.1f}% · "
f"Obstacle Distance: {'None' if latest['obstacle_distance_m'] == 999 else
f'{latest['obstacle_distance_m']:.1f} m'}"
)

st.markdown("---")
st.subheader("Human-Gated Recommendations")

if not ss.proposals:
st.info("No recommendations yet. The console will surface proposals as risk climbs.")
else:
labels = [f"#{p.id} [{p.status}] {p.title}" for p in ss.proposals]
selected_label = st.selectbox("Select proposal", labels)
pid = int(selected_label.split(" ")[0].replace("#", ""))
prop = next(p for p in ss.proposals if p.id == pid)

st.markdown(f"**Title:** {prop.title}")
st.markdown(f"**Status:** `{prop.status}`")
st.markdown("**Rationale:**")
st.write(prop.rationale)
st.markdown("**Snapshot at Time of Recommendation:**")
st.json(prop.snapshot)

c1, c2, c3 = st.columns(3)
with c1:
if st.button("Approve", disabled=prop.status != "PENDING"):
update_proposal_status(prop, "APPROVED")
st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun()
with c2:
if st.button("Reject", disabled=prop.status != "PENDING"):
update_proposal_status(prop, "REJECTED")
st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun()
with c3:
if st.button("Defer", disabled=prop.status != "PENDING"):
update_proposal_status(prop, "DEFERRED")
st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun()

st.markdown("---")
st.subheader("Audit Trail (Last 20 Entries)")

if ss.audit:
audit_df = pd.DataFrame(
[
{
"Time": time.strftime("%H:%M:%S", time.localtime(a.ts)),
"Kind": a.kind,
"Summary": a.summary,
}

for a in ss.audit[-20:]
]
)
st.dataframe(audit_df, height=260, use_container_width=True)
else:
st.info("Audit log will populate as the system runs.")

# End of file
