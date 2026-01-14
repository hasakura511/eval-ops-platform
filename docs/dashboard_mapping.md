# Dashboard Page Mapping (v2.1 Aligned)

This document maps variables from **Bureaucratic Autoregression Spec v2.1** to the UI components of the Control Room dashboard.

## 1) Global Shell (always visible)

**Purpose:** global context, time navigation, high-level status, manual overrides.

**Primary fields:**
- `meta.project_id`
- `meta.t`
- `meta.timestamp`
- `meta.global_status`
- `commands.last_command`

**Components:**
- **Time Scrubber:** scrub historical `t` (requires persisted snapshots or ledger replay)
- **Status Beacon:** color by `global_status`
- **Command Panel:** show last command + ack (and link to command log in Records Office)

---

## 2) Page mapping table

| Dashboard View | Primary Purpose | Maps to Spec Variables / JSON Fields | Visual Components & Logic |
|---|---|---|---|
| **1. Executive Cockpit** | Governance & strategy | **Physics:** `physics.admin_ratio` vs `B_t.Pi_t.beta`, `physics.risk_thermometer` vs `B_t.Pi_t.r`<br>**Policy:** `B_t.Pi_t` (p, β, r, w_t, lambda_t, mu_t)<br>**Rule Health:** `B_t.R_t.rule_budget`, `physics.rule_entropy` | **Deregulation Trigger:** alert if `admin_ratio > beta`<br>**Risk Gauge:** warn if `evaluation.Risk(x_t) > r`<br>**Entropy Trend:** chart `rule_entropy` over time and top-k high-entropy rules (drill to rules)<br>**Policy Diff:** show \(\Pi_t\) changes (weights, rotation schedule) |
| **2. Inspectorate** | Audit & anti-gaming | `physics.goodhart.*`, `evaluation.audit`, `alerts[]` (GOODHART*)<br>`B_t.Pi_t.metric_rotation`<br>`B_t.L_t.recent_audits` | **Adversarial Feed:** latest failed audits + counterexamples<br>**Drift Heatmap:** by jurisdiction (requires audit summaries include jurisdiction tags)<br>**Rotation Countdown:** `metric_rotation.next_rotation_t - meta.t`<br>**Disagreement Rate Chart:** plot `goodhart.disagreement_rate` |
| **3. Records Office** | Traceability & debugging | `B_t.L_t.ledger_head`, `B_t.L_t.provenance_ref`<br>`B_t.L_t.recent_artifacts / decisions / audits / incidents` | **Provenance DAG Viewer:** Input → Unit → Artifact → Audit → Decision<br>**BlameTrace Viewer:** render `AuditReport.BlameTrace` paths (by node IDs)<br>**Immutable Log Browser:** search by artifact ID/hash<br>**Rule History Diff:** show \(R_t\) vs \(R_{t-1}\), sunset timers |
| **4. Operations (Units)** | Execution & constraints | `B_t.A_t.units[]` (jurisdiction, D_i, discretion_spent_this_iter, variance_memos)<br>`topology.active_jurisdictions` | **Jurisdiction Map:** which units active/blocked (blocked requires dependency graph refs)<br>**Discretion Wallet:** remaining \(D_i\) per unit, spend history<br>**Variance Memo Queue:** show active exceptions + link to memo artifacts |
| **5. Sandbox** | Innovation & experiments | `topology.sandbox_mode`, `topology.sandbox_jurisdiction`<br>(plus optional sandbox-specific `Pi_t_S` if implemented) | **Sandbox Status:** on/off + jurisdiction scope<br>**Decontamination Gate Panel:** show artifacts attempting to exit sandbox and their audit state<br>**Local Risk Gauge:** compare \(r_S\) vs \(r\) (if sandbox policy present) |

---

## 3) Derived metrics (computed in dashboard or backend)

To keep `state.json` lean, the dashboard may compute (or the backend may precompute) derived metrics:

- **AdminRatio trend:** moving average of `physics.admin_ratio`
- **Goodhart trend:** rolling `drift_score` and `disagreement_rate`
- **Top entropy rules:** from ledger counts of apply/waive (backend recommended)
- **Overhead share per role:** breakdown of `C(role)` to explain why admin ratio rose
- **Backlog / blocked units:** requires optional fields:
  - `operations.backlog_count`
  - `operations.blocked_units[]`
  - `H_t.dependency_graph_ref`

---

## 4) Data-flow contract for the dashboard

Minimum viable contract:
- Dashboard reads **one** JSON file: `state.json`
- Records Office endpoints (or static exports) resolve references:
  - `artifact:*` IDs
  - `hash:*` ledger heads
  - provenance graph for `provenance_ref`

Recommended directory convention for static deployment:
- `/state/state.json` (latest)
- `/state/history/t=000042.json` (snapshots)
- `/artifacts/<id>.json` (artifact bodies)
- `/provenance/<id>.json` (edges list)

---

## 5) Alignment checklist (UI must satisfy)

The dashboard is considered aligned only if it can answer these questions from its UI:

1) **Why did this deliverable pass?** (Acceptance gate internals + evidence refs)
2) **What rule/policy changed and why?** (diff + decision memo + ledger link)
3) **Where is discretion being spent?** (variance memos + D_i spend)
4) **Are we being Goodharted?** (audit disagreement + drift over time)
5) **Is bureaucracy bloating?** (admin ratio vs beta + rule budget + entropy)
