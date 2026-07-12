const API = "/api";
const SEV_CLASS = { low: "low", medium: "medium", high: "high", critical: "critical" };
const SEV_VAR = { low: "--good", medium: "--warning", high: "--serious", critical: "--critical" };
const SEV_ORDER = ["critical", "high", "medium", "low"];
const SEV_BAR = { critical: "sev-critical", high: "sev-high", medium: "sev-medium", low: "sev-good" };

async function api(path, opts) {
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const e = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(e.detail || "Request failed");
  }
  return res.json();
}

/* ---------- helpers ---------- */
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
function sevColor(sev) { return cssVar(SEV_VAR[sev] || "--muted"); }
function pill(text, cls) { return `<span class="pill ${cls}"><span class="dot"></span>${escapeHtml(text)}</span>`; }
function statusPill(s) { return `<span class="pill status-${s}">${escapeHtml(s)}</span>`; }
function fmtDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) + " " +
         d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}
function shortUrn(urn) {
  let m = urn.match(/dataPlatform:[^,]+,([^,]+),/);
  if (m) return m[1];
  m = urn.match(/\(([^)]+)\)\s*$/);
  return m ? m[1].split(",").pop() : urn;
}
function kindOf(urn) {
  if (urn.includes("mlModel")) return "model";
  if (urn.includes("dashboard")) return "dashboard";
  return "dataset";
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* ---------- render ---------- */
function renderTiles(incidents, health) {
  const active = incidents.filter((i) => i.status === "open").length;
  const high = incidents.filter((i) => ["high", "critical"].includes(i.severity)).length;
  document.getElementById("stat-active").textContent = active;
  document.getElementById("stat-active-sub").textContent =
    incidents.length ? `${incidents.length} total detected` : "across monitored assets";
  document.getElementById("stat-high").textContent = high;
  document.getElementById("stat-assets").textContent = health.assets_monitored ?? "–";
  document.getElementById("stat-writes").textContent = incidents.length * 2;
}

function renderSeverity(incidents) {
  const box = document.getElementById("overview");
  if (!incidents.length) { box.hidden = true; return; }
  box.hidden = false;
  const counts = { critical: 0, high: 0, medium: 0, low: 0 };
  incidents.forEach((i) => { counts[i.severity] = (counts[i.severity] || 0) + 1; });
  const total = incidents.length;
  const bar = document.getElementById("sev-bar");
  const legend = document.getElementById("sev-legend");
  bar.innerHTML = SEV_ORDER.filter((s) => counts[s])
    .map((s) => `<span class="${SEV_BAR[s]}" style="width:${(counts[s] / total) * 100}%"></span>`).join("");
  legend.innerHTML = SEV_ORDER.map(
    (s) => `<span class="item"><span class="swatch ${SEV_BAR[s]}"></span>${s} <b>${counts[s]}</b></span>`
  ).join("");
}

function renderTable(incidents) {
  const rows = document.getElementById("rows");
  document.getElementById("inc-count").textContent =
    incidents.length ? `${incidents.length} incident${incidents.length > 1 ? "s" : ""}` : "";
  if (!incidents.length) {
    rows.innerHTML = `<tr><td colspan="6"><div class="empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2 4 5v6c0 5 3.4 8.6 8 11 4.6-2.4 8-6 8-11V5l-8-3Z" stroke-linejoin="round"/><path d="m9 12 2 2 4-4" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <div>No incidents detected yet.</div>
      <div class="cta"><button class="btn primary" onclick="document.getElementById('scan-btn').click()">Run a scan</button></div>
    </div></td></tr>`;
    return;
  }
  rows.innerHTML = incidents.map((i) => {
    const color = sevColor(i.severity);
    return `<tr data-id="${i.id}">
      <td>${pill(i.severity, SEV_CLASS[i.severity])}</td>
      <td><span class="asset">${escapeHtml(shortUrn(i.datahub_urn))}<small>${i.dataset_key}</small></span></td>
      <td>${escapeHtml(i.incident_type)}</td>
      <td><div class="score-cell"><span class="meter"><i style="width:${i.score}%;background:${color}"></i></span><span class="score-num">${i.score}</span></div></td>
      <td>${statusPill(i.status)}</td>
      <td class="tnum">${fmtDate(i.detected_at)}</td>
    </tr>`;
  }).join("");
  rows.querySelectorAll("tr[data-id]").forEach((r) =>
    r.addEventListener("click", () => openDrawer(r.dataset.id)));
}

async function refresh() {
  const [health, incidents] = await Promise.all([api("/health"), api("/incidents")]);
  document.getElementById("mode-text").textContent =
    `${health.datahub_mode} mode · LLM ${health.llm_enabled ? "on" : "template"}`;
  renderTiles(incidents, health);
  renderSeverity(incidents);
  renderTable(incidents);
}

/* ---------- drawer ---------- */
async function openDrawer(id) {
  const inc = await api(`/incidents/${id}`);
  const color = sevColor(inc.severity);
  document.getElementById("d-sub").textContent = `${inc.dataset_key} · ${inc.incident_type} incident`;
  document.getElementById("d-title").innerHTML = `${pill(inc.severity, SEV_CLASS[inc.severity])} ${escapeHtml(shortUrn(inc.datahub_urn))}`;

  const lineage = `<div class="lineage">
      <span class="node root">${escapeHtml(shortUrn(inc.datahub_urn))}</span>
      ${inc.impact_radius.map((u) => `<span class="arrow">→</span><span class="node"><span class="kind">${kindOf(u)}</span>${escapeHtml(shortUrn(u))}</span>`).join("")}
    </div>`;

  const writes = inc.writebacks.length
    ? `<div class="writes">${inc.writebacks.map((w) =>
        `<div class="write"><span class="kind">${w.write_type.replace("_", " ")}</span><span class="chip wtag">${escapeHtml(w.value)}</span><span style="color:var(--muted);font-size:12px">${w.mode}</span></div>`).join("")}</div>`
    : "<p style='color:var(--muted)'>None</p>";

  const remediation = inc.remediation_artifact
    ? `<div class="chip" style="margin-bottom:8px">✅ ${escapeHtml(inc.remediation_artifact)}</div>`
    : `<button class="btn primary" id="rem-btn">Generate remediation</button>`;

  document.getElementById("d-body").innerHTML = `
    <div class="gauge">
      <div class="row"><span class="n">${inc.score}<small>/100 risk</small></span><span>${pill(inc.severity, SEV_CLASS[inc.severity])}</span></div>
      <div class="track"><i style="width:${inc.score}%;background:${color}"></i></div>
    </div>
    <div class="dl">
      <span class="k">URN</span><span class="v"><span class="chip">${escapeHtml(inc.datahub_urn)}</span></span>
      <span class="k">Status</span><span class="v">${statusPill(inc.status)}</span>
      <span class="k">Detected</span><span class="v tnum">${fmtDate(inc.detected_at)}</span>
      <span class="k">DataHub</span><span class="v"><a href="${inc.datahub_link}" target="_blank" rel="noopener">Open in DataHub ↗</a></span>
    </div>
    <div class="block-title">Explanation</div>
    <div class="explain">${escapeHtml(inc.description)}</div>
    <div class="block-title">Impact radius — downstream assets at risk</div>
    ${lineage}
    <div class="block-title">Metadata written back to DataHub</div>
    ${writes}
    <div class="block-title">Remediation</div>
    <div id="rem-slot">${remediation}</div>
  `;

  const rb = document.getElementById("rem-btn");
  if (rb) rb.addEventListener("click", async () => {
    rb.disabled = true; rb.innerHTML = `<span class="spin"></span> Generating…`;
    try {
      const r = await api(`/incidents/${id}/apply-remediation`, { method: "POST" });
      document.getElementById("rem-slot").innerHTML =
        `<div class="chip" style="margin-bottom:8px">✅ ${escapeHtml(r.artifact_path)}</div>
         <div class="rem-explain">${escapeHtml(r.explanation)}</div>
         <pre>${escapeHtml(r.code)}</pre>`;
      toast("Remediation generated · incident resolved");
      refresh();
    } catch (e) { toast("Error: " + e.message); rb.disabled = false; rb.textContent = "Generate remediation"; }
  });

  document.getElementById("scrim").classList.add("open");
  document.getElementById("drawer").classList.add("open");
  document.getElementById("drawer").setAttribute("aria-hidden", "false");
}
function closeDrawer() {
  document.getElementById("scrim").classList.remove("open");
  document.getElementById("drawer").classList.remove("open");
  document.getElementById("drawer").setAttribute("aria-hidden", "true");
}

/* ---------- toast ---------- */
let toastTimer;
function toast(msg) {
  document.getElementById("toast-msg").textContent = msg;
  const t = document.getElementById("toast");
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2800);
}

/* ---------- actions ---------- */
async function withLoading(btn, labelEl, fn) {
  const original = labelEl ? labelEl.textContent : btn.textContent;
  btn.disabled = true;
  if (labelEl) labelEl.innerHTML = `<span class="spin"></span> Scanning…`; else btn.textContent = "…";
  try { await fn(); }
  finally { btn.disabled = false; if (labelEl) labelEl.textContent = original; else btn.textContent = original; }
}

document.getElementById("scan-btn").addEventListener("click", (e) =>
  withLoading(e.currentTarget, document.getElementById("scan-label"), async () => {
    const r = await api("/scan", { method: "POST" });
    toast(`Scanned ${r.scanned_assets} assets · ${r.incidents_created} new incident${r.incidents_created === 1 ? "" : "s"}`);
    await refresh();
  }));

async function simulate(dataset, issue_type, btn) {
  await withLoading(btn, null, async () => {
    const r = await api("/simulate-issue", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset, issue_type }),
    });
    toast(`Simulated ${issue_type} on ${dataset} · ${r.incidents_created} new incident${r.incidents_created === 1 ? "" : "s"}`);
    await refresh();
  });
}
document.getElementById("sim-fresh").addEventListener("click", (e) => simulate("nyc-taxi", "freshness", e.currentTarget));
document.getElementById("sim-qual").addEventListener("click", (e) => simulate("healthcare", "quality", e.currentTarget));

document.getElementById("d-close").addEventListener("click", closeDrawer);
document.getElementById("scrim").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

refresh().catch((e) => toast("Error: " + e.message));
