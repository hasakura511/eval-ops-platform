const DEFAULT_SNAPSHOT_PATH = "../state/control_room_latest.json";
const POLL_INTERVAL_MS = 8000;

const statusClasses = {
  running: "status-running",
  failed: "status-failed",
  pending: "status-pending",
  blocked: "status-blocked",
  complete: "status-complete",
  completed: "status-complete",
  paused: "status-paused",
};

const byId = (id) => document.getElementById(id);

const toArray = (value) => (Array.isArray(value) ? value : []);

const safeText = (value, fallback = "—") =>
  value === undefined || value === null || value === "" ? fallback : value;

const normalizeStatus = (value) =>
  typeof value === "string" ? value.toLowerCase() : "unknown";

const relativeTime = (value) => {
  if (!value) return "—";
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return "—";
  const diffMs = Date.now() - timestamp;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 0) return "in the future";
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
};

const metricValue = (metric) => {
  if (!metric) return "—";
  if (metric.unit) return `${metric.value} ${metric.unit}`;
  return metric.value;
};

const fetchSnapshot = async (path) => {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load snapshot (${response.status})`);
  }
  return response.json();
};

const buildRunIndex = (snapshot) => {
  const projects = toArray(snapshot.projects);
  const runs = [];

  projects.forEach((project) => {
    toArray(project.tracks).forEach((track) => {
      toArray(track.runs).forEach((run) => {
        runs.push({
          project,
          track,
          run,
        });
      });
    });
  });

  return runs;
};

const buildAlertIndex = (snapshot) => toArray(snapshot.alerts);

const setStatusChip = (el, status) => {
  const normalized = normalizeStatus(status);
  el.textContent = status ? status.toUpperCase() : "UNKNOWN";
  el.className = `chip status ${statusClasses[normalized] || "status-unknown"}`;
};

const renderHeader = (snapshot) => {
  setText("snapshot-time", snapshot.as_of);
  setText("snapshot-health", safeText(snapshot.health?.status, "Nominal"));
  setText(
    "snapshot-freshness",
    snapshot.health?.data_freshness_seconds !== undefined
      ? `${snapshot.health.data_freshness_seconds}s`
      : "—"
  );
  setText(
    "snapshot-alerts",
    snapshot.health?.active_alerts_count !== undefined
      ? snapshot.health.active_alerts_count
      : "0"
  );
};

const setText = (id, value) => {
  const el = byId(id);
  if (!el) return;
  el.textContent = safeText(value);
};

const renderFilters = (snapshot) => {
  const projectSelect = byId("filter-project");
  const trackSelect = byId("filter-track");
  const statusSelect = byId("filter-status");
  const ownerSelect = byId("filter-owner");

  if (!projectSelect || !trackSelect || !statusSelect || !ownerSelect) return;

  const projects = toArray(snapshot.projects);
  const tracks = new Map();
  const statuses = new Set();
  const owners = new Map();

  projects.forEach((project) => {
    toArray(project.tracks).forEach((track) => {
      tracks.set(track.track_id, track.name || track.track_id);
      toArray(track.runs).forEach((run) => {
        if (run.status) statuses.add(run.status);
        if (run.owner?.agent_id) {
          owners.set(run.owner.agent_id, run.owner.display_name || run.owner.agent_id);
        }
      });
    });
  });

  fillSelect(projectSelect, projects.map((project) => ({
    value: project.project_id,
    label: project.name || project.project_id,
  })));
  fillSelect(trackSelect, Array.from(tracks.entries()).map(([value, label]) => ({
    value,
    label,
  })));
  fillSelect(statusSelect, Array.from(statuses).sort().map((value) => ({
    value,
    label: value,
  })));
  fillSelect(ownerSelect, Array.from(owners.entries()).map(([value, label]) => ({
    value,
    label,
  })));

  applyFilterFromQuery();
};

const fillSelect = (select, options) => {
  const current = select.value;
  select.innerHTML = '<option value="">All</option>';
  options.forEach((option) => {
    const node = document.createElement("option");
    node.value = option.value;
    node.textContent = option.label;
    select.appendChild(node);
  });
  if (current) select.value = current;
};

const applyFilterFromQuery = () => {
  const params = new URLSearchParams(window.location.search);
  const applyValue = (id, key) => {
    const el = byId(id);
    if (!el) return;
    const value = params.get(key);
    if (value) el.value = value;
  };
  applyValue("filter-project", "project");
  applyValue("filter-track", "track");
  applyValue("filter-status", "status");
  applyValue("filter-owner", "owner");
  applyValue("filter-search", "search");
};

const collectFilters = () => ({
  project: byId("filter-project")?.value || "",
  track: byId("filter-track")?.value || "",
  status: byId("filter-status")?.value || "",
  owner: byId("filter-owner")?.value || "",
  search: (byId("filter-search")?.value || "").toLowerCase(),
});

const matchesFilter = (item, filters) => {
  if (filters.project && item.project.project_id !== filters.project) return false;
  if (filters.track && item.track.track_id !== filters.track) return false;
  if (filters.status && item.run.status !== filters.status) return false;
  if (filters.owner && item.run.owner?.agent_id !== filters.owner) return false;
  if (filters.search) {
    const haystack = [
      item.project.name,
      item.track.name,
      item.run.run_id,
      item.run.next_action,
      item.run.owner?.display_name,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    if (!haystack.includes(filters.search)) return false;
  }
  return true;
};

const renderWorkboard = (snapshot) => {
  const list = byId("workboard-list");
  if (!list) return;
  const filters = collectFilters();
  const runs = buildRunIndex(snapshot).filter((item) =>
    matchesFilter(item, filters)
  );

  list.innerHTML = "";

  if (runs.length === 0) {
    list.innerHTML = '<div class="empty">No runs match current filters.</div>';
    return;
  }

  runs.forEach((item) => {
    const { project, track, run } = item;
    const card = document.createElement("div");
    card.className = "run-card";

    const header = document.createElement("div");
    header.className = "run-header";

    const title = document.createElement("div");
    title.className = "run-title";
    title.innerHTML = `
      <div class="run-name">${safeText(run.run_id)}</div>
      <div class="run-subtitle">${safeText(project.name)} · ${safeText(track.name)}</div>
    `;

    const statusChip = document.createElement("span");
    setStatusChip(statusChip, run.status);

    const meta = document.createElement("div");
    meta.className = "run-meta";
    meta.innerHTML = `
      <div><strong>Owner</strong> ${safeText(run.owner?.display_name)}</div>
      <div><strong>Updated</strong> ${relativeTime(run.last_update_at)}</div>
      <div><strong>Failures</strong> ${safeText(run.failure_count, 0)}</div>
      <div><strong>Next</strong> ${safeText(run.next_action)}</div>
    `;

    const metrics = document.createElement("div");
    metrics.className = "chip-row";
    toArray(run.metrics_summary).forEach((metric) => {
      const chip = document.createElement("span");
      chip.className = "chip neutral";
      chip.textContent = `${metric.name}: ${metricValue(metric)}`;
      metrics.appendChild(chip);
    });

    const artifacts = document.createElement("div");
    artifacts.className = "artifact-links";
    toArray(run.artifact_refs).forEach((artifact) => {
      const link = document.createElement("a");
      link.href = artifact.href || "#";
      link.textContent = artifact.label || artifact.artifact_id;
      artifacts.appendChild(link);
    });

    const todoDrawer = document.createElement("details");
    todoDrawer.className = "todo-drawer";
    const summary = document.createElement("summary");
    summary.textContent = `Todos (${toArray(run.todos).length})`;
    todoDrawer.appendChild(summary);

    const todoList = document.createElement("div");
    todoList.className = "todo-list";

    if (toArray(run.todos).length === 0) {
      todoList.innerHTML = '<div class="empty">No todos assigned.</div>';
    } else {
      toArray(run.todos).forEach((todo) => {
        const todoItem = document.createElement("div");
        todoItem.className = "todo-item";
        todoItem.innerHTML = `
          <div>
            <div class="todo-title">${safeText(todo.title)}</div>
            <div class="todo-meta">
              ${safeText(todo.status)} · ${relativeTime(todo.updated_at)} · ${safeText(
          todo.owner_agent_id
        )}
            </div>
            <div class="todo-meta">${safeText(todo.blocking_reason)}</div>
          </div>
        `;
        const refs = document.createElement("div");
        refs.className = "todo-artifacts";
        toArray(todo.artifact_refs).forEach((artifact) => {
          const link = document.createElement("a");
          link.href = artifact.href || "#";
          link.textContent = artifact.label || artifact.artifact_id;
          refs.appendChild(link);
        });
        todoItem.appendChild(refs);
        todoList.appendChild(todoItem);
      });
    }

    todoDrawer.appendChild(todoList);

    header.appendChild(title);
    header.appendChild(statusChip);

    card.appendChild(header);
    card.appendChild(meta);
    if (metrics.children.length > 0) card.appendChild(metrics);
    if (artifacts.children.length > 0) card.appendChild(artifacts);
    card.appendChild(todoDrawer);

    list.appendChild(card);
  });
};

const renderSpotlight = (snapshot) => {
  const spotlight = byId("failure-spotlight");
  if (!spotlight) return;
  const runs = buildRunIndex(snapshot)
    .map((item) => ({
      ...item,
      failure_count: item.run.failure_count || 0,
    }))
    .filter((item) => item.failure_count > 0)
    .sort((a, b) => b.failure_count - a.failure_count)
    .slice(0, 5);

  spotlight.innerHTML = "";

  if (runs.length === 0) {
    spotlight.innerHTML = '<div class="empty">No failures reported.</div>';
    return;
  }

  runs.forEach((item) => {
    const card = document.createElement("div");
    card.className = "spotlight-card";
    card.innerHTML = `
      <div class="spotlight-title">${safeText(item.run.run_id)}</div>
      <div class="spotlight-meta">${safeText(item.project.name)} · ${safeText(
      item.track.name
    )}</div>
      <div class="spotlight-meta">Failures: ${safeText(
      item.run.failure_count
    )}</div>
    `;
    spotlight.appendChild(card);
  });
};

const renderTodoFeed = (snapshot) => {
  const feed = byId("todo-feed");
  if (!feed) return;
  const todos = [];
  buildRunIndex(snapshot).forEach((item) => {
    toArray(item.run.todos).forEach((todo) => {
      todos.push({
        todo,
        run: item.run,
        project: item.project,
        track: item.track,
      });
    });
  });

  todos.sort(
    (a, b) =>
      new Date(b.todo.updated_at || 0).getTime() -
      new Date(a.todo.updated_at || 0).getTime()
  );

  feed.innerHTML = "";

  if (todos.length === 0) {
    feed.innerHTML = '<div class="empty">No open todos.</div>';
    return;
  }

  todos.slice(0, 8).forEach((item) => {
    const row = document.createElement("div");
    row.className = "todo-feed-row";
    row.innerHTML = `
      <div>
        <div class="todo-title">${safeText(item.todo.title)}</div>
        <div class="todo-meta">${safeText(item.project.name)} · ${safeText(
      item.track.name
    )} · ${safeText(item.run.run_id)}</div>
      </div>
      <div class="todo-meta">${safeText(item.todo.status)} · ${relativeTime(
      item.todo.updated_at
    )}</div>
    `;
    feed.appendChild(row);
  });
};

const renderHierarchy = (snapshot) => {
  const tree = byId("hierarchy-tree");
  if (!tree) return;
  tree.innerHTML = "";

  const nodeIndex = new Map();

  const createNode = (type, id, label, status, extra) => {
    const node = document.createElement("button");
    node.type = "button";
    node.className = "hierarchy-node";
    node.dataset.nodeKey = `${type}:${id}`;
    node.innerHTML = `
      <div class="hierarchy-node-header">
        <span class="hierarchy-node-title">${label}</span>
        <span class="chip status">${safeText(status).toUpperCase()}</span>
      </div>
      <div class="hierarchy-node-meta">${safeText(extra)}</div>
    `;
    const chip = node.querySelector(".chip.status");
    setStatusChip(chip, status);
    return node;
  };

  toArray(snapshot.projects).forEach((project) => {
    const projectNode = createNode(
      "project",
      project.project_id,
      project.name || project.project_id,
      project.status,
      `${toArray(project.tracks).length} tracks`
    );
    nodeIndex.set(`project:${project.project_id}`, { type: "project", data: project });

    const projectGroup = document.createElement("div");
    projectGroup.className = "hierarchy-group";
    projectGroup.appendChild(projectNode);

    toArray(project.tracks).forEach((track) => {
      const trackNode = createNode(
        "track",
        track.track_id,
        track.name || track.track_id,
        track.status,
        `${toArray(track.runs).length} runs · ${safeText(track.type)}`
      );
      nodeIndex.set(`track:${track.track_id}`, { type: "track", data: track });
      const trackGroup = document.createElement("div");
      trackGroup.className = "hierarchy-group nested";
      trackGroup.appendChild(trackNode);

      toArray(track.runs).forEach((run) => {
        const runNode = createNode(
          "run",
          run.run_id,
          run.run_id,
          run.status,
          `${safeText(run.owner?.display_name)} · ${safeText(run.next_action)}`
        );
        nodeIndex.set(`run:${run.run_id}`, { type: "run", data: run });
        const runGroup = document.createElement("div");
        runGroup.className = "hierarchy-group nested";
        runGroup.appendChild(runNode);

        if (run.owner?.agent_id) {
          const agentNode = createNode(
            "agent",
            run.owner.agent_id,
            run.owner.display_name || run.owner.agent_id,
            run.owner.status || "active",
            run.owner.role || ""
          );
          nodeIndex.set(`agent:${run.owner.agent_id}`, {
            type: "agent",
            data: run.owner,
          });
          const agentGroup = document.createElement("div");
          agentGroup.className = "hierarchy-group nested";
          agentGroup.appendChild(agentNode);

          toArray(run.todos).forEach((todo) => {
            const todoNode = createNode(
              "todo",
              todo.todo_id,
              todo.title || todo.todo_id,
              todo.status,
              `Updated ${relativeTime(todo.updated_at)}`
            );
            nodeIndex.set(`todo:${todo.todo_id}`, { type: "todo", data: todo });
            const todoGroup = document.createElement("div");
            todoGroup.className = "hierarchy-group nested";
            todoGroup.appendChild(todoNode);
            agentGroup.appendChild(todoGroup);
          });
          runGroup.appendChild(agentGroup);
        }
        trackGroup.appendChild(runGroup);
      });
      projectGroup.appendChild(trackGroup);
    });

    tree.appendChild(projectGroup);
  });

  const detailPanel = byId("node-detail");
  if (!detailPanel) return;

  tree.querySelectorAll(".hierarchy-node").forEach((node) => {
    node.addEventListener("click", () => {
      const key = node.dataset.nodeKey;
      const entry = nodeIndex.get(key);
      if (!entry) return;
      renderNodeDetail(detailPanel, entry);
    });
  });
};

const renderNodeDetail = (panel, entry) => {
  panel.innerHTML = "";
  const header = document.createElement("div");
  header.className = "detail-header";
  header.textContent = `${entry.type.toUpperCase()} · ${safeText(
    entry.data.name || entry.data.run_id || entry.data.todo_id || entry.data.agent_id
  )}`;

  const list = document.createElement("div");
  list.className = "detail-list";

  Object.entries(entry.data).forEach(([key, value]) => {
    if (Array.isArray(value)) return;
    if (value && typeof value === "object") return;
    const row = document.createElement("div");
    row.className = "detail-row";
    row.innerHTML = `<span>${key}</span><span>${safeText(value)}</span>`;
    list.appendChild(row);
  });

  const artifacts = document.createElement("div");
  artifacts.className = "detail-artifacts";
  const artifactRefs = toArray(entry.data.artifact_refs);
  if (artifactRefs.length > 0) {
    const title = document.createElement("div");
    title.className = "detail-subtitle";
    title.textContent = "Artifacts";
    artifacts.appendChild(title);
    artifactRefs.forEach((artifact) => {
      const link = document.createElement("a");
      link.href = artifact.href || "#";
      link.textContent = artifact.label || artifact.artifact_id;
      artifacts.appendChild(link);
    });
  }

  panel.appendChild(header);
  panel.appendChild(list);
  if (artifactRefs.length > 0) panel.appendChild(artifacts);
};

const renderAlerts = (snapshot) => {
  const alerts = byId("alerts-rail");
  if (!alerts) return;
  const alertItems = buildAlertIndex(snapshot);
  alerts.innerHTML = "";

  if (alertItems.length === 0) {
    alerts.innerHTML = '<div class="empty">No alerts.</div>';
    return;
  }

  alertItems.forEach((alert) => {
    const card = document.createElement("div");
    card.className = "alert-card";
    card.innerHTML = `
      <div class="alert-header">
        <span class="chip ${alert.severity}">${safeText(alert.severity)}</span>
        <span>${relativeTime(alert.timestamp)}</span>
      </div>
      <div class="alert-message">${safeText(alert.message)}</div>
      <div class="alert-meta">Run: ${safeText(alert.run_id)}</div>
    `;
    const refs = document.createElement("div");
    refs.className = "alert-artifacts";
    toArray(alert.artifact_refs).forEach((artifact) => {
      const link = document.createElement("a");
      link.href = artifact.href || "#";
      link.textContent = artifact.label || artifact.artifact_id;
      refs.appendChild(link);
    });
    card.appendChild(refs);
    alerts.appendChild(card);
  });
};

const renderSnapshot = (snapshot) => {
  renderHeader(snapshot);
  renderFilters(snapshot);
  renderWorkboard(snapshot);
  renderSpotlight(snapshot);
  renderTodoFeed(snapshot);
  renderHierarchy(snapshot);
  renderAlerts(snapshot);
};

const startPolling = (path) => {
  const statusLabel = byId("snapshot-status");
  const load = async () => {
    try {
      const snapshot = await fetchSnapshot(path);
      renderSnapshot(snapshot);
      if (statusLabel) statusLabel.textContent = "Live";
    } catch (error) {
      if (statusLabel) statusLabel.textContent = "Offline";
      console.error(error);
    }
  };

  load();
  setInterval(load, POLL_INTERVAL_MS);
};

const initControls = () => {
  const controls = [
    "filter-project",
    "filter-track",
    "filter-status",
    "filter-owner",
    "filter-search",
  ];
  controls.forEach((id) => {
    const control = byId(id);
    if (!control) return;
    control.addEventListener("change", () => {
      fetchSnapshot(getSnapshotPath()).then(renderSnapshot).catch(console.error);
    });
    control.addEventListener("input", () => {
      fetchSnapshot(getSnapshotPath()).then(renderSnapshot).catch(console.error);
    });
  });
};

const getSnapshotPath = () => {
  const params = new URLSearchParams(window.location.search);
  return params.get("source") || DEFAULT_SNAPSHOT_PATH;
};

const boot = () => {
  initControls();
  startPolling(getSnapshotPath());
};

boot();
