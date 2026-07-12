const API = "/api";

async function api(path, opts) {
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  setTimeout(() => t.classList.add("hidden"), 2600);
}

function pill(text, cls) {
  return `<span class="pill ${cls}">${text}</span>`;
}

function fmtDate(iso) {
  return new Date(iso).toLocaleString();
}

async function refresh() {
  const [health, incidents, risks] = await Promise.all([
    api("/health"),
    api("/incidents"),
    api("/risk-scores"),
  ]);

  const badge = document.getElementById("mode-badge");
  badge.textContent = `mode: ${health.datahub_mode} · LLM: ${health.llm_enabled ? "on" : "template"}`;

  const active = incidents.filter((i) => i.status === "open").length;
  const high = incidents.filter((i) => ["high", "critical"].includes(i.severity)).length;
  const writes = incidents.length * 2; // tag + glossary term per incident
  document.getElementById("stat-active").textContent = active;
  document.getElementById("stat-high").textContent = high;
  document.getElementById("stat-datasets").textContent = risks.length || "0";
  document.getElementById("stat-writes").textContent = writes;

  const body = document.getElementById("incidents-body");
  if (!incidents.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty">No incidents yet — click <strong>Run scan</strong>.</td></tr>`;
    return;
  }
  body.innerHTML = incidents
    .map(
      (i) => `<tr data-id="${i.id}">
        <td>${pill(i.severity, i.severity)}</td>
        <td>${i.dataset_key}</td>
        <td>${i.incident_type}</td>
        <td>${i.score}</td>
        <td>${pill(i.status, i.status)}</td>
        <td>${fmtDate(i.detected_at)}</td>
      </tr>`
    )
    .join("");

  body.querySelectorAll("tr[data-id]").forEach((row) => {
    row.addEventListener("click", () => openIncident(row.dataset.id));
  });
}

async function openIncident(id) {
  const inc = await api(`/incidents/${id}`);
  const impact = inc.impact_radius.length
    ? `<ul class="impact">${inc.impact_radius.map((u) => `<li><code>${shortUrn(u)}</code></li>`).join("")}</ul>`
    : "<p>None</p>";
  const writes = inc.writebacks.length
    ? `<ul class="writes">${inc.writebacks
        .map((w) => `<li><strong>${w.write_type}</strong>: <code>${w.value}</code> <em>(${w.mode})</em></li>`)
        .join("")}</ul>`
    : "<p>None</p>";

  const remediation = inc.remediation_artifact
    ? `<p>✅ Artifact: <code>${inc.remediation_artifact}</code></p>`
    : `<button class="btn primary" id="remediate-btn">Generate remediation</button>`;

  document.getElementById("modal-body").innerHTML = `
    <h3>${pill(inc.severity, inc.severity)} ${inc.incident_type} · ${inc.dataset_key}</h3>
    <div class="kv">
      <span class="k">URN</span><span><code>${shortUrn(inc.datahub_urn)}</code></span>
      <span class="k">Risk score</span><span>${inc.score}/100</span>
      <span class="k">Status</span><span>${pill(inc.status, inc.status)}</span>
      <span class="k">Detected</span><span>${fmtDate(inc.detected_at)}</span>
      <span class="k">DataHub</span><span><a href="${inc.datahub_link}" target="_blank" rel="noopener">Open in DataHub ↗</a></span>
    </div>
    <div class="section-title">Explanation</div>
    <p>${inc.description}</p>
    <div class="section-title">Impact radius (downstream)</div>
    ${impact}
    <div class="section-title">Metadata written back to DataHub</div>
    ${writes}
    <div class="section-title">Remediation</div>
    <div id="remediation-slot">${remediation}</div>
  `;

  const remBtn = document.getElementById("remediate-btn");
  if (remBtn) {
    remBtn.addEventListener("click", async () => {
      remBtn.disabled = true;
      remBtn.textContent = "Generating…";
      try {
        const r = await api(`/incidents/${id}/apply-remediation`, { method: "POST" });
        document.getElementById("remediation-slot").innerHTML =
          `<p>✅ Artifact: <code>${r.artifact_path}</code></p><p>${r.explanation}</p><pre>${escapeHtml(r.code)}</pre>`;
        toast("Remediation generated & incident resolved");
        refresh();
      } catch (e) {
        toast("Error: " + e.message);
        remBtn.disabled = false;
        remBtn.textContent = "Generate remediation";
      }
    });
  }

  document.getElementById("modal").classList.remove("hidden");
}

function shortUrn(urn) {
  const m = urn.match(/dataPlatform:[^,]+,([^,]+),/) || urn.match(/\(([^)]+)\)/);
  return m ? m[1] : urn;
}
function escapeHtml(s) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

document.getElementById("modal-close").addEventListener("click", () =>
  document.getElementById("modal").classList.add("hidden")
);
document.getElementById("modal").addEventListener("click", (e) => {
  if (e.target.id === "modal") document.getElementById("modal").classList.add("hidden");
});

document.getElementById("scan-btn").addEventListener("click", async () => {
  try {
    const r = await api("/scan", { method: "POST" });
    toast(`Scanned ${r.scanned_assets} assets · ${r.incidents_created} new incident(s)`);
    refresh();
  } catch (e) {
    toast("Error: " + e.message);
  }
});

async function simulate(dataset, issue_type) {
  try {
    const r = await api("/simulate-issue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset, issue_type }),
    });
    toast(`Simulated ${issue_type} on ${dataset} · ${r.incidents_created} new incident(s)`);
    refresh();
  } catch (e) {
    toast("Error: " + e.message);
  }
}
document.getElementById("sim-fresh").addEventListener("click", () => simulate("nyc-taxi", "freshness"));
document.getElementById("sim-qual").addEventListener("click", () => simulate("healthcare", "quality"));

refresh();
