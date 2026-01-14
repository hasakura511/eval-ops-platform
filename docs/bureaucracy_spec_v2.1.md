# Bureaucratic Autoregression Specification v2.1 (Aligned)

## 1. Overview & Objectives

This document specifies the architecture for a **Bureaucratic Autoregression** system—an agentic organization designed to mitigate classic institutional failure modes (Goodhart’s Law, Principal–Agent drift, Parkinson’s Law) through:

- **Formal state exposure** for governance and debugging:  
  \(\mathcal{B}_t = (H_t, R_t, A_t, \Pi_t, \mathcal{L}_t)\)
- **Immutable records** (append-only ledger + provenance graph)
- **Mathematically governed rule and policy evolution**
- **Explicit anti-bloat / anti-paralysis constraints**

The system is monitored via a **Control Room** dashboard reading a standardized telemetry packet (`state.json`) that exposes enough structure to answer:

1) *What happened?* (ledger + provenance)  
2) *Why did it pass/fail?* (acceptance gate internals)  
3) *Who/what must change?* (rule/policy updates with budgets + sunsets)

---

## 2. Formal State Definition

At iteration \(t = 0,1,2,\dots\), the bureaucracy state is:

\[\
\mathcal{B}_t = (H_t, R_t, A_t, \Pi_t, \mathcal{L}_t)\
\]

- \(H_t\): **Hierarchy / topology** (reporting graph, jurisdictions, escalation paths)  
- \(R_t\): **Rule set** (SOPs, gates, exception protocol), with **rule budget** and **sunsets**  
- \(A_t\): **Actors** (units/roles), with **mandates** \(M_i\) and **discretion budgets** \(D_i\)  
- \(\Pi_t\): **Policies** (audit probability \(p\), risk appetite \(r\), process budget \(\beta\), weights \(\mathbf{w}_t\), penalties \(\lambda_t,\mu_t\), metric-rotation profile)  
- \(\mathcal{L}_t\): **Ledger** (append-only log of artifacts, decisions, audits, incidents, and provenance edges)

Each iteration produces one or more **work outputs** \(x_t\) (artifacts or bundles).

---

## 3. Mathematical Framework (“The Physics”)

We use a **Regularized Institutional Loss** to penalize pathological bureaucracy (overhead, fragility, gaming) while allowing protective slowness where appropriate.

### 3.1 Evaluation and Acceptance Gate

Define the score of outputs \(x_t\):

\[\
\text{Score}(x_t) = \mathbf{w}_t^\top \mathbf{g}(x_t) \;-
\; \lambda_t \cdot \text{Risk}(x_t)\;-
\;\mu_t \cdot \text{Overhead}(x_t)\
\]

- \(\mathbf{g}(x_t) = (g_1,\dots,g_k)\): objective vector (quality/correctness/usability/etc.)
- \(\mathbf{w}_t\): weights (policy-controlled)
- \(\text{Risk}(x_t)\): risk estimate (including irreversibility penalties)
- \(\text{Overhead}(x_t)\): compliance/process cost (paperwork, review load, compute)

**Acceptance gate** (auditable decision rule):

\[\
\text{Accept}(x_t) \iff
\begin{cases}
\mathbf{g}(x_t)\ \text{meets thresholds} \\
\text{Risk}(x_t) \le r \\
\text{Overhead}(x_t) \le \beta \\
\text{AuditPassed}(x_t) = \text{true (if audited)}
\end{cases}
\]

### 3.2 Regularized Institutional Loss Function

The system optimizes the following loss \(\mathcal{J}_t\) over iterations \(t\):

\[\
\mathcal{J}_t =
\underbrace{\alpha \cdot \text{Gap}(x_t)}_{\text{Performance}} +
\underbrace{\gamma \cdot \text{IncidentCost}(I_t)}_{\text{Safety}} +
\underbrace{\delta \cdot \text{Overhead}(x_t)}_{\text{Efficiency}} +
\underbrace{\zeta \cdot \text{RuleEntropy}(R_t)}_{\text{Fragility}} +
\underbrace{\kappa \cdot \text{GoodhartDrift}(x_t, \text{audits}_t)}_{\text{Gaming}} +
\underbrace{\eta \cdot \text{DelayCost}(t)}_{\text{Latency}}
\]

#### Term Definitions

1) **RuleEntropy (Fragility)**  
Measures rules that are frequently waived/bent. High entropy suggests the rule is brittle or the domain is misclassified.

\[\
\text{RuleEntropy}(R_t) = \sum_{r \in R_t}
\left[ -p_{\text{apply}}(r)\log p_{\text{apply}}(r) - p_{\text{waive}}(r)\log p_{\text{waive}}(r) \right]\
\]

- \(p_{\text{apply}}(r)\), \(p_{\text{waive}}(r)\) are computed from the ledger \(\mathcal{L}_t\) over a sliding window \(W\), stratified by **jurisdiction** and **risk tier**.

**Action:** High entropy triggers a **Mandate Clarification Sweep** (repair classification / boundaries) and/or rule rewrite/deletion with a sunset.

2) **GoodhartDrift (Anti-gaming)**  
Measures divergence between the optimized metric and the audit metric.

\[\
\text{GoodhartDrift} = a_1 \cdot \text{Disagree}_t + a_2 \cdot \left\lVert g_{\text{primary}}(x_t) - g_{\text{audit}}(x_t)\right\rVert_1
\]

- \(\text{Disagree}_t = \Pr[\text{gate\_pass}(x)=1 \land \text{audit\_fail}(x)=1]\)

**Action:** Rising drift triggers **metric rotation** (change \(\mathbf{w}_t\) / rubric profile) and/or increased audit probability \(p\).

---

## 4. Anti-Red-Tape Constraint (“Deregulation Trigger”)

We define an administrative overhead ratio based on token/compute consumption \(C(\text{role})\):

\[\
\text{AdminRatio}_t = \frac{\sum C(\text{Executive}) + \sum C(\text{Director}) + \sum C(\text{Inspector}) + \sum C(\text{Records})}{\sum C(\text{All Roles})}\
\]

**Trigger Condition:**

\[\
\text{If } \text{AdminRatio}_t > \beta \implies \text{Trigger}(\text{DeregulationProtocol})\
\]

### 4.1 DeregulationProtocol (Aligned)

1) **Tiered Suspend**  
Pause audits only for **low-risk tiers**; preserve audits for high-risk/irreversible domains.

2) **Sunset by Utility + Entropy**  
Expire bottom \(q\%\) of rules by **KillScore**:

\[\
\text{UtilityScore}(r) = \frac{\text{FailuresCaught}(r) + \varepsilon}{\text{CostToApply}(r) + \varepsilon}
\]

\[\
\text{KillScore}(r) = w_1 \cdot \frac{1}{\text{UtilityScore}(r)} + w_2 \cdot \text{Entropy}(r)
\]

Rules that never catch failures **and** are frequently waived are deleted first.

3) **Compression Enforcement**  
Force summary of open decision memos; enforce “one memo per decision” and compression quotas per reporting hop.

4) **Mandate Clarification Sweep**  
If entropy is high due to misclassification, repair boundaries (jurisdiction/mandate), not only rule deletion.

---

## 5. Architectural Mitigations (“Safeguards”)

### 5.1 Guardian Capture (Who guards the guardians?)

- **Model Diversity:** Inspectorate MUST use a different model class or prompt profile than Operational Units. Logged in \(\mathcal{L}_t\).
- **Auditor Rotation:** Rotate audit assignments across jurisdictions to reduce capture and correlated blind spots.
- **Disagreement Metric:** If two auditors diverge systematically, escalate to Executive Council.
- **Amicus Curiae Hook:** External inputs enter as first-class artifacts (IDs + provenance), not “god mode” interrupts.

### 5.2 Recursive Latency (Paperwork Paralysis)

**Sparse Reporting with Full Traceability**:

- **Routine tasks:** no human memo required; must still produce:
  1) immutable ledger entry  
  2) artifact hash  
  3) provenance edge (Input ID → Output ID)
- **Spot checks:** retroactive decision memos required for \(p_{\text{spot}}\%\) of routine tasks.
- **Compression quotas:** enforce bounded summary size per upward hop.

### 5.3 Innovation Sandbox

A defined subgraph \(S \subset H_t\) with distinct physics:

- **Parameters:** higher risk appetite \(r_S \gg r_{\text{global}}\)
- **Isolation:** failures in \(S\) do not impact global \(\text{IncidentCost}\)
- **Still tracked:** entropy and Goodhart drift still monitored (gaming is gaming even in sandbox)
- **Decontamination Gate:** \(S \to H_{\text{main}}\) requires full audit + provenance link

---

## 6. Telemetry Standard: `state.json`

This schema is the single source of truth for the dashboard. It exposes \(\mathcal{B}_t\) and enough acceptance internals to debug governance decisions.

```json
{
  "meta": {
    "project_id": "PROJ-ALPHA",
    "t": 42,
    "timestamp": "2026-01-14T14:00:00Z",
    "global_status": "NOMINAL"
  },

  "B_t": {
    "H_t": { "org_chart_ref": "artifact:hierarchy@t42" },

    "R_t": {
      "rules": [
        {
          "id": "R-017",
          "text_ref": "artifact:rule@R-017",
          "created_t": 30,
          "expires_t": 50,
          "owner_role": "Executive",
          "risk_tier": "LOW"
        }
      ],
      "rule_budget": { "b": 1, "current_count": 23, "added_this_iter": 1, "deleted_this_iter": 1 }
    },

    "A_t": {
      "units": [
        {
          "unit_id": "ops-07",
          "mandate_ref": "artifact:mandate@ops-07",
          "jurisdiction": "backend-dev",
          "D_i": 0.35,
          "discretion_spent_this_iter": 0.10,
          "variance_memos": ["artifact:variance@v-991"]
        }
      ]
    },

    "Pi_t": {
      "p": 0.15,
      "beta": 0.15,
      "r": 0.30,
      "w_t": [0.4, 0.3, 0.3],
      "lambda_t": 1.0,
      "mu_t": 0.5,
      "metric_rotation": { "active_profile": "M-03", "next_rotation_t": 45 }
    },

    "L_t": {
      "ledger_head": "hash:abc123",
      "recent_artifacts": ["artifact:x@t42.1"],
      "recent_decisions": ["artifact:decision@d-2201"],
      "recent_audits": ["artifact:audit@a-552"],
      "recent_incidents": ["incident:i-771"],
      "provenance_ref": "artifact:provenance@t42"
    }
  },

  "topology": {
    "active_jurisdictions": ["backend-dev", "frontend-dev", "security-audit"],
    "sandbox_mode": true,
    "sandbox_jurisdiction": "experimental-features"
  },

  "physics": {
    "admin_ratio": 0.12,
    "rule_entropy": 0.04,
    "goodhart": { "disagreement_rate": 0.06, "drift_score": 0.12 },
    "risk_thermometer": 0.45
  },

  "evaluation": {
    "g(x_t)": { "quality": 0.88, "correctness": 0.91, "usability": 0.72 },
    "Risk(x_t)": 0.18,
    "Overhead(x_t)": 0.17,
    "Accept(x_t)": true,
    "audit": { "audited": true, "AuditPassed": true, "audit_ref": "artifact:audit@a-552" }
  },

  "registry": {
    "latest_block_hash": "0x9a7...",
    "pending_memos": 3,
    "amicus_briefs": 0
  },

  "alerts": [
    {
      "severity": "HIGH",
      "type": "GOODHART_DETECTED",
      "source": "Inspectorate-A",
      "message": "Unit-7 hit 'Coverage' but failed semantic validity.",
      "evidence_refs": ["artifact:audit@a-552", "artifact:x@t42.1"]
    }
  ],

  "commands": {
    "last_command": { "id": "cmd-901", "type": "FREEZE", "acked": true, "acked_by": "bureaucracy-loop" }
  }
}
```

---

## 7. Agent Role Templates (“The Constitution”)

These are role-level invariants (system prompts or contractual constraints) that enforce institutional design.

### 7.1 Role A: Operational Unit (Worker)

- **Mandate:** execute tasks within jurisdiction \(M_i\)
- **Discretion Budget:** \(D_i\). Spending discretion requires a `VarianceMemo` and ledger entry.
- **Required outputs (per task):**
  - `Artifact`
  - `SelfCheck` (assumptions, tests performed, likely failure points, confidence)
  - `VarianceMemo` (only if discretion spent)
- **Traceability:** every output must cite input IDs; Records Office must record provenance edge.

### 7.2 Role B: Inspectorate (Auditor)

- **Mandate:** adversarial review; cannot “fix,” only flag and evidence.
- **Inputs:** `Artifact` + optional `VarianceMemo`
- **Outputs:** `AuditReport` (Pass/Fail, Goodhart flags, Fragility score, `BlameTrace`)
- **Constraints:**
  - must log model/prompt profile used (diversity/capture checks)
  - must provide evidence refs (artifact IDs, tests, counterexamples)

### 7.3 Role C: Executive Council (Governor)

- **Mandate:** tune \(R_t\) and \(\Pi_t\); adjudicate disputes and amicus briefs.
- **Constraints:**
  - enforce **rule budget** (add-one-delete-one) and **sunsets**
  - if \(\text{AdminRatio}_t > \beta\), execute **DeregulationProtocol**
  - if Goodhart drift rises, trigger **Metric Rotation**
- **Outputs:** `DecisionMemo` (accept/reject + rationale + policy/rule updates)

---

## 8. Implementation Roadmap (Zero → Control Room)

1) **Telemetry Dummies**
- Generate synthetic `state.json` with full \(\mathcal{B}_t\) simulation.
- Dashboard turns RED when `admin_ratio > beta` or `goodhart.drift_score` exceeds threshold.

2) **Records Office (Append-only)**
- Implement ledger storage for artifacts, decisions, audits, incidents.
- Implement provenance DAG storage (`Input → Unit → Artifact → Audit → Decision`).

3) **Dashboard Shell**
- Build Executive, Inspectorate, Records, and Operations pages consuming `state.json`.
- Implement history scrubber (view \(t\) and diffs across iterations).

4) **Autoregression Loop**
- Implement update step for \((\Pi_{t+1}, R_{t+1})\) subject to rule budget + sunsets.
- Compute RuleEntropy and Goodhart metrics from the ledger.

5) **Inspectorate Activation**
- Enable model diversity policy, auditor rotation, and disagreement escalation.
- Track audit disagreement and metric drift per jurisdiction.

6) **Command Channel**
- Replace ad-hoc “command file” with append-only command log, including ack status and authority.
