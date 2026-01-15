const stateBasePath = "../state";
const recordsBasePath = "../records";
const historyFiles = [
  "t=000001.json",
  "t=000002.json",
  "t=000003.json",
  "t=000004.json",
  "t=000005.json",
  "t=000006.json",
];

const statusClasses = {
  NOMINAL: "nominal",
  DEREGULATION_TRIGGERED: "warning",
  HIGH_ENTROPY: "warning",
  AUDIT_FAIL: "warning",
  SANDBOX_EXIT: "warning",
  CRITICAL_HALT: "critical",
};

const formatNumber = (value) => {
  if (typeof value !== "number") return "—";
  return value.toFixed(2);
};

const byId = (id) => document.getElementById(id);

const closeInfoTooltips = () => {
  document.querySelectorAll(".info-button.is-open").forEach((button) => {
    button.classList.remove("is-open");
    button.setAttribute("aria-expanded", "false");
  });
};

const initInfoTooltips = () => {
  const buttons = document.querySelectorAll(".info-button");
  if (buttons.length === 0) return;
  buttons.forEach((button) => {
    button.setAttribute("aria-expanded", "false");
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      const isOpen = button.classList.contains("is-open");
      closeInfoTooltips();
      if (!isOpen) {
        button.classList.add("is-open");
        button.setAttribute("aria-expanded", "true");
      }
    });
  });

  document.addEventListener("click", () => {
    closeInfoTooltips();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeInfoTooltips();
    }
  });
};

const setText = (id, value) => {
  const el = byId(id);
  if (el) {
    el.textContent = value ?? "—";
  }
};

const setLink = (id, value, href) => {
  const el = byId(id);
  if (el) {
    el.textContent = value ?? "—";
    el.href = href ?? "#";
  }
};

const renderList = (id, items, formatter) => {
  const el = byId(id);
  if (!el) return;
  el.innerHTML = "";
  if (!items || items.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No records.";
    el.appendChild(li);
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    const node = formatter ? formatter(item) : document.createTextNode(item);
    li.appendChild(node);
    el.appendChild(li);
  });
};

const artifactLink = (ref) => {
  const id = ref.replace("artifact:", "");
  const link = document.createElement("a");
  link.href = `${recordsBasePath}/artifacts/${id}.json`;
  link.textContent = ref;
  return link;
};

const ledgerLink = (ref) => {
  const id = ref.replace("hash:", "");
  return `${recordsBasePath}/ledger/${id}.json`;
};

const provenanceLink = (ref) => {
  const id = ref.replace("artifact:", "");
  return `${recordsBasePath}/provenance/${id}.json`;
};

const updateStatus = (status) => {
  const beacon = byId("status-beacon");
  if (!beacon) return;
  beacon.className = "status-beacon";
  const className = statusClasses[status];
  if (className) {
    beacon.classList.add(className);
  }
};

const renderUnits = (units) => {
  const container = byId("units-table");
  if (!container) return;
  container.innerHTML = "";
  if (!units || units.length === 0) {
    container.textContent = "No units reported.";
    return;
  }
  units.forEach((unit) => {
    const row = document.createElement("div");
    row.className = "table-row";
    row.innerHTML = `
      <div><strong>${unit.unit_id}</strong></div>
      <div>Jurisdiction: ${unit.jurisdiction}</div>
      <div>D_i: ${formatNumber(unit.D_i)}</div>
      <div>Spent: ${formatNumber(unit.discretion_spent_this_iter)}</div>
      <div>Variance memos: ${unit.variance_memos.length}</div>
    `;
    container.appendChild(row);
  });
};

const updateDashboard = (state) => {
  setText("project-id", state.meta.project_id);
  setText("meta-time", state.meta.timestamp);
  setText("meta-t", `t=${state.meta.t}`);
  setText("global-status", state.meta.global_status);
  setText(
    "last-command",
    `${state.commands.last_command.type} (${state.commands.last_command.id})`
  );
  updateStatus(state.meta.global_status);

  const adminRatio = state.physics.admin_ratio;
  const beta = state.B_t.Pi_t.beta;
  setText("admin-ratio", formatNumber(adminRatio));
  setText("beta", formatNumber(beta));

  const adminStatus = byId("admin-ratio-status");
  if (adminStatus) {
    adminStatus.className = "callout";
    if (adminRatio > beta) {
      adminStatus.textContent = "AdminRatio exceeds β. Deregulation protocol active.";
      adminStatus.classList.add("warn");
    } else {
      adminStatus.textContent = "AdminRatio within policy budget.";
    }
  }

  setText("goodhart-drift", formatNumber(state.physics.goodhart.drift_score));
  setText(
    "goodhart-disagreement",
    formatNumber(state.physics.goodhart.disagreement_rate)
  );
  setText("rule-entropy", formatNumber(state.physics.rule_entropy));
  setText(
    "rule-budget",
    `${state.B_t.R_t.rule_budget.current_count} / ${state.B_t.R_t.rule_budget.b}`
  );
  setText("policy-p", formatNumber(state.B_t.Pi_t.p));
  setText("policy-r", formatNumber(state.B_t.Pi_t.r));

  const rotation = state.B_t.Pi_t.metric_rotation;
  if (rotation) {
    setText(
      "rotation-countdown",
      `T-${rotation.next_rotation_t - state.meta.t} (${rotation.active_profile})`
    );
  }

  const audit = state.evaluation.audit;
  setText(
    "audit-status",
    audit.AuditPassed ? "Audit Passed" : "Audit Failed"
  );

  renderList("alerts-list", state.alerts, (alert) => {
    const container = document.createElement("div");
    container.innerHTML = `
      <strong>${alert.severity}</strong> · ${alert.type}
      <div>${alert.message}</div>
    `;
    const evidence = document.createElement("div");
    if (alert.evidence_refs.length > 0) {
      alert.evidence_refs.forEach((ref) => {
        evidence.appendChild(artifactLink(ref));
        evidence.appendChild(document.createElement("br"));
      });
    }
    container.appendChild(evidence);
    return container;
  });

  setLink("ledger-head", state.B_t.L_t.ledger_head, ledgerLink(state.B_t.L_t.ledger_head));
  setLink(
    "provenance-ref",
    state.B_t.L_t.provenance_ref,
    provenanceLink(state.B_t.L_t.provenance_ref)
  );

  renderList("recent-artifacts", state.B_t.L_t.recent_artifacts, artifactLink);
  renderList("recent-decisions", state.B_t.L_t.recent_decisions, artifactLink);
  renderList("recent-audits", state.B_t.L_t.recent_audits, artifactLink);
  renderList("recent-incidents", state.B_t.L_t.recent_incidents);

  setText("active-jurisdictions", state.topology.active_jurisdictions.join(", "));
  setText(
    "sandbox-status",
    state.topology.sandbox_mode ? "Sandbox Active" : "Sandbox Offline"
  );
  setText("sandbox-jurisdiction", state.topology.sandbox_jurisdiction);

  renderUnits(state.B_t.A_t.units);
};

const loadState = async (path) => {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to load ${path}`);
  }
  return response.json();
};

const initScrubber = () => {
  const select = byId("time-scrubber");
  if (!select) return;
  select.innerHTML = "";
  historyFiles.forEach((file) => {
    const option = document.createElement("option");
    option.value = `${stateBasePath}/history/${file}`;
    option.textContent = file.replace(".json", "");
    select.appendChild(option);
  });
  select.addEventListener("change", async (event) => {
    const path = event.target.value;
    const state = await loadState(path);
    updateDashboard(state);
  });
};

const boot = async () => {
  initInfoTooltips();
  initScrubber();
  const initialPath = `${stateBasePath}/latest.json`;
  const state = await loadState(initialPath);
  updateDashboard(state);
};

boot().catch((error) => {
  console.error(error);
});
