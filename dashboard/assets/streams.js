const API_SNAPSHOT = "/api/control-room/snapshot";
const API_STREAMS = "/api/atp/streams";
const API_PACKET = (streamId, filename) =>
  `/api/atp/streams/${streamId}/packets/${filename}`;
const API_EVENTS = (streamId) =>
  `/api/atp/streams/${streamId}/packets/events.jsonl`;
const API_MANIFEST = (hash) => `/api/artifacts/${hash}/manifest`;
const API_ARTIFACT_FILE = (hash, file) =>
  `/api/artifacts/${hash}/files/${file}`;

const LOCAL_SNAPSHOT = "state/control_room_latest.json";
const LOCAL_STREAMS = "state/atp/index.json";
const LOCAL_PACKET = (streamId, filename) =>
  `state/atp/streams/${streamId}/${filename}`;
const LOCAL_EVENTS = (streamId) =>
  `state/atp/streams/${streamId}/events.jsonl`;

const byId = (id) => document.getElementById(id);

const state = {
  snapshot: null,
  index: null,
  activeStream: null,
};

const fetchJson = async (url) => {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}`);
  }
  return response.json();
};

const fetchText = async (url) => {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}`);
  }
  return response.text();
};

const fetchAvailable = async (url) => {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Unavailable: ${url}`);
  }
  return response;
};

const fetchWithFallback = async (primary, fallback) => {
  try {
    return await fetchJson(primary);
  } catch (error) {
    return await fetchJson(fallback);
  }
};

const fetchTextWithFallback = async (primary, fallback) => {
  try {
    return await fetchText(primary);
  } catch (error) {
    return await fetchText(fallback);
  }
};

const parsePacket = (text) => {
  const normalized = text.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  if (parts.length < 2) {
    return null;
  }
  const headerLines = parts[0].split("\n").filter(Boolean);
  const bodyLines = parts.slice(1).join("\n\n").split("\n");

  const headers = { ATP: headerLines[0] };
  headerLines.slice(1).forEach((line) => {
    const [key, ...rest] = line.split(":");
    headers[key.trim()] = rest.join(":").trim();
  });

  const sections = {
    GOAL: "",
    NOW: [],
    NEXT: [],
    RISKS: [],
    ACCEPT: [],
    ARTIFACTS: [],
    QUESTIONS: [],
    CONFIDENCE: null,
  };

  let active = null;
  bodyLines.forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line) {
      return;
    }
    if (line.startsWith("GOAL:")) {
      sections.GOAL = line.replace("GOAL:", "").trim();
      active = null;
      return;
    }
    if (line.startsWith("CONFIDENCE:")) {
      sections.CONFIDENCE = line.replace("CONFIDENCE:", "").trim();
      active = null;
      return;
    }
    if (line.endsWith(":") && sections[line.replace(":", "")] !== undefined) {
      active = line.replace(":", "");
      return;
    }
    if (line.startsWith("-") && active) {
      sections[active].push(line.replace(/^-\s*/, ""));
      return;
    }
  });

  return { headers, sections };
};

const manifestHashFromPath = (path) => {
  const match = path.match(/state\/artifacts\/([^/]+)\/manifest.json/);
  return match ? match[1] : null;
};

const renderStreamList = () => {
  const container = byId("stream-list");
  const index = state.index || { streams: {} };
  const snapshotStreams = (state.snapshot?.streams || []).reduce((acc, item) => {
    acc[item.id] = item;
    return acc;
  }, {});

  const streamIds = Object.keys(index.streams || {});
  if (!streamIds.length) {
    container.innerHTML = '<div class="empty">No streams found.</div>';
    return;
  }

  container.innerHTML = streamIds
    .sort()
    .map((streamId) => {
      const summary = snapshotStreams[streamId] || {};
      const status = summary.status || "unknown";
      const approval = summary.approval_state || "none";
      return `
        <button class="stream-card" data-stream-id="${streamId}">
          <div class="stream-card-title">${streamId}</div>
          <div class="stream-card-meta">
            <span>Latest seq: ${index.streams[streamId].latest_seq}</span>
            <span>Status: ${status}</span>
            <span>Approval: ${approval}</span>
          </div>
        </button>
      `;
    })
    .join("");

  container.querySelectorAll("[data-stream-id]").forEach((button) => {
    button.addEventListener("click", () => {
      selectStream(button.dataset.streamId);
    });
  });
};

const renderPacketChain = (streamId) => {
  const container = byId("stream-packets");
  const packetFiles = state.index?.streams?.[streamId]?.packet_files || [];
  if (!packetFiles.length) {
    container.innerHTML = '<div class="empty">No packets found.</div>';
    return;
  }

  container.innerHTML = packetFiles
    .map(
      (file) =>
        `<button class="stream-packet" data-packet-file="${file}">${file}</button>`
    )
    .join("");

  container.querySelectorAll("[data-packet-file]").forEach((button) => {
    button.addEventListener("click", () => {
      loadPacket(streamId, button.dataset.packetFile);
    });
  });
};

const renderTimeline = async (streamId) => {
  const container = byId("stream-timeline");
  try {
    const text = await fetchTextWithFallback(
      API_EVENTS(streamId),
      LOCAL_EVENTS(streamId)
    );
    const entries = text
      .split("\n")
      .filter(Boolean)
      .map((line) => {
        try {
          return JSON.parse(line);
        } catch (error) {
          return null;
        }
      })
      .filter(Boolean);
    if (!entries.length) {
      container.innerHTML = '<div class="empty">No events logged.</div>';
      return;
    }
    container.innerHTML = entries
      .map(
        (entry) => `
          <div class="timeline-item">
            <div class="timeline-title">${entry.type}</div>
            <div class="timeline-meta">${entry.ts || "—"} · ${entry.summary}</div>
          </div>
        `
      )
      .join("");
  } catch (error) {
    container.innerHTML = '<div class="empty">Events not available.</div>';
  }
};

const renderPacketDetail = async (packet, streamId, filename) => {
  const container = byId("stream-why-body");
  if (!packet) {
    container.innerHTML = '<div class="empty">Packet parse failed.</div>';
    return;
  }

  const manifestItems = packet.sections.ARTIFACTS.map((item) => {
    const path = item.split(":").slice(1).join(":").trim() || item;
    const hash = manifestHashFromPath(path);
    return { path, hash };
  });

  const manifestEntries = await Promise.all(
    manifestItems.map(async (item) => {
      const apiUrl = item.hash ? API_MANIFEST(item.hash) : item.path;
      const localUrl = item.path;
      try {
        await fetchAvailable(apiUrl);
        return {
          ...item,
          status: "available",
          url: apiUrl,
        };
      } catch (error) {
        try {
          await fetchAvailable(localUrl);
          return {
            ...item,
            status: "available",
            url: localUrl,
          };
        } catch (nestedError) {
          return {
            ...item,
            status: "missing",
            url: apiUrl,
          };
        }
      }
    })
  );

  const headerRows = Object.entries(packet.headers)
    .map(
      ([key, value]) => `
        <div class="kv-row">
          <div class="kv-key">${key}</div>
          <div class="kv-value">${value}</div>
        </div>
      `
    )
    .join("");

  const renderList = (items) =>
    items.length
      ? `<ul>${items.map((item) => `<li>${item}</li>`).join("")}</ul>`
      : '<div class="empty">—</div>';

  const artifactsHtml = manifestEntries
    .map((item) => {
      const label = item.status === "missing" ? "Missing" : "Available";
      const statusClass = item.status === "missing" ? "status-bad" : "status-ok";
      return `
        <div class="artifact-item ${statusClass}">
          <a href="${item.url}" target="_blank" rel="noreferrer">${item.path}</a>
          <span class="artifact-status">${label}</span>
        </div>
      `;
    })
    .join("");

  container.innerHTML = `
    <div class="packet-section">
      <h4>Headers</h4>
      <div class="kv-grid">${headerRows}</div>
    </div>
    <div class="packet-section">
      <h4>Goal</h4>
      <p>${packet.sections.GOAL || "—"}</p>
    </div>
    <div class="packet-section">
      <h4>Now</h4>
      ${renderList(packet.sections.NOW)}
    </div>
    <div class="packet-section">
      <h4>Next</h4>
      ${renderList(packet.sections.NEXT)}
    </div>
    <div class="packet-section">
      <h4>Risks</h4>
      ${renderList(packet.sections.RISKS)}
    </div>
    <div class="packet-section">
      <h4>Accept</h4>
      ${renderList(packet.sections.ACCEPT)}
    </div>
    <div class="packet-section">
      <h4>Artifacts</h4>
      ${artifactsHtml || '<div class="empty">No artifacts listed.</div>'}
    </div>
    <div class="packet-section">
      <h4>Questions</h4>
      ${renderList(packet.sections.QUESTIONS)}
    </div>
  `;
};

const loadPacket = async (streamId, filename) => {
  const text = await fetchTextWithFallback(
    API_PACKET(streamId, filename),
    LOCAL_PACKET(streamId, filename)
  );
  const parsed = parsePacket(text);
  await renderPacketDetail(parsed, streamId, filename);
};

const updateApproveButton = (streamId) => {
  const button = byId("approve-button");
  const stream = (state.snapshot?.streams || []).find(
    (item) => item.id === streamId
  );
  if (!stream) {
    button.disabled = true;
    return;
  }
  button.disabled = stream.approval_state !== "requested";
};

const selectStream = async (streamId) => {
  state.activeStream = streamId;
  const subtitle = byId("stream-detail-subtitle");
  subtitle.textContent = `Viewing stream ${streamId}`;

  renderPacketChain(streamId);
  renderTimeline(streamId);
  updateApproveButton(streamId);

  const packetFiles = state.index?.streams?.[streamId]?.packet_files || [];
  if (packetFiles.length) {
    await loadPacket(streamId, packetFiles[packetFiles.length - 1]);
  }
};

const openModal = () => {
  const modal = byId("approval-modal");
  if (modal) {
    modal.showModal();
  }
};

const closeModal = () => {
  const modal = byId("approval-modal");
  if (modal) {
    modal.close();
  }
};

const setupApproval = () => {
  const button = byId("approve-button");
  const form = byId("approval-form");
  const rationale = byId("approval-rationale");

  button.addEventListener("click", () => {
    if (button.disabled) return;
    rationale.value = "";
    openModal();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.activeStream) return;
    if (!rationale.value.trim()) {
      rationale.focus();
      return;
    }
    await fetch(`/api/atp/streams/${state.activeStream}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rationale: rationale.value.trim() }),
    });
    closeModal();
    await loadData();
    if (state.activeStream) {
      await selectStream(state.activeStream);
    }
  });

  document.querySelectorAll("[data-modal-close]").forEach((button) => {
    button.addEventListener("click", closeModal);
  });
};

const loadData = async () => {
  state.snapshot = await fetchWithFallback(API_SNAPSHOT, LOCAL_SNAPSHOT);
  state.index = await fetchWithFallback(API_STREAMS, LOCAL_STREAMS);
  const status = byId("streams-snapshot-status");
  status.textContent = state.snapshot?.as_of
    ? `Snapshot ${state.snapshot.as_of}`
    : "Snapshot loaded";
  renderStreamList();
};

const init = async () => {
  await loadData();
  setupApproval();
};

init();
