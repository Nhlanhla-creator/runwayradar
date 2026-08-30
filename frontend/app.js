// ---- View routing -----------------------------------------------------------
const views = {
  landing: document.getElementById("view-landing"),
  signin: document.getElementById("view-signin"),
  dashboard: document.getElementById("view-dashboard"),
};

function show(view) {
  for (const v of Object.values(views)) v.hidden = true;
  views[view].hidden = false;
  window.scrollTo({ top: 0 });
}

function goLanding() { show("landing"); }
function goSignin() { show("signin"); }
function goDashboard() {
  show("dashboard");
  runLoop();
}

// ---- Landing / sign-in wiring ----------------------------------------------
document.getElementById("hero-cta").addEventListener("click", goSignin);
document.getElementById("nav-cta").addEventListener("click", goSignin);
document.getElementById("nav-signin").addEventListener("click", goSignin);
document.getElementById("back-to-landing").addEventListener("click", goLanding);
document.getElementById("signout").addEventListener("click", goLanding);

document.getElementById("signin-form").addEventListener("submit", (e) => {
  e.preventDefault();
  goDashboard();
});

// ---- Dashboard elements -----------------------------------------------------
const els = {
  runButton: document.getElementById("run-button"),
  uploadButton: document.getElementById("upload-button"),
  fileInput: document.getElementById("file-input"),
  resetButton: document.getElementById("reset-button"),
  exampleSelect: document.getElementById("example-select"),
  sourceChip: document.getElementById("source-chip"),
  loading: document.getElementById("loading"),
  loadingText: document.getElementById("loading-text"),
  dashSub: document.getElementById("dash-sub"),
  kpiBurnValue: document.getElementById("kpi-burn-value"),
  kpiBurnSub: document.getElementById("kpi-burn-sub"),
  kpiRunwayValue: document.getElementById("kpi-runway-value"),
  kpiRunwaySub: document.getElementById("kpi-runway-sub"),
  kpiCashValue: document.getElementById("kpi-cash-value"),
  kpiCashSub: document.getElementById("kpi-cash-sub"),
  kpiImpactValue: document.getElementById("kpi-impact-value"),
  kpiImpactSub: document.getElementById("kpi-impact-sub"),
  chartBurn: document.getElementById("chart-burn"),
  chartDonut: document.getElementById("chart-donut"),
  donutTotal: document.getElementById("donut-total"),
  donutLegend: document.getElementById("donut-legend"),
  flagsCount: document.getElementById("flags-count"),
  flagList: document.getElementById("flag-list"),
  anomaliesCount: document.getElementById("anomalies-count"),
  anomalyList: document.getElementById("anomaly-list"),
  traceList: document.getElementById("trace-list"),
  askForm: document.getElementById("ask-form"),
  askInput: document.getElementById("ask-input"),
  askAnswer: document.getElementById("ask-answer"),
  askStages: document.getElementById("ask-stages"),
  askAnswerText: document.getElementById("ask-answer-text"),
  askChips: document.getElementById("ask-chips"),
};

els.runButton.addEventListener("click", runLoop);
els.uploadButton.addEventListener("click", () => els.fileInput.click());
els.fileInput.addEventListener("change", uploadFile);
els.resetButton.addEventListener("click", resetData);
els.exampleSelect.addEventListener("change", () => {
  if (els.exampleSelect.value) loadExample(els.exampleSelect.value);
});
els.askForm.addEventListener("submit", askQuestion);
els.askChips.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  els.askInput.value = chip.dataset.q;
  askQuestion();
});

async function loadExamples() {
  try {
    const res = await fetch("/api/examples");
    const data = await res.json();
    for (const example of data.examples || []) {
      const option = document.createElement("option");
      option.value = example.id;
      option.textContent = example.name;
      els.exampleSelect.appendChild(option);
    }
  } catch (err) {
    console.warn("Could not load examples", err);
  }
}

async function loadExample(name) {
  els.exampleSelect.disabled = true;
  showLoading();
  els.loadingText.textContent = "Reading " + name + "…";
  try {
    const res = await fetch("/api/examples/" + encodeURIComponent(name), { method: "POST" });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      els.dashSub.textContent = "Example failed: " + (data.error || "unknown error");
      return;
    }
    els.sourceChip.textContent = data.source;
    els.resetButton.hidden = false;
    await revealTrace(data.trace);
    render(data);
  } catch (err) {
    els.dashSub.textContent = "Example error: " + err.message;
  } finally {
    hideLoading();
    els.exampleSelect.disabled = false;
  }
}

loadExamples();

// ---- Run the agent loop -----------------------------------------------------
async function runLoop() {
  els.runButton.disabled = true;
  showLoading();
  try {
    const res = await fetch("/api/run");
    const data = await res.json();
    await revealTrace(data.trace);
    render(data);
  } catch (err) {
    els.dashSub.textContent = "Error: " + err.message;
  } finally {
    hideLoading();
    els.runButton.disabled = false;
  }
}

function showLoading() { els.loading.hidden = false; }
function hideLoading() { els.loading.hidden = true; }

async function uploadFile() {
  const file = els.fileInput.files[0];
  if (!file) return;
  els.uploadButton.disabled = true;
  showLoading();
  els.loadingText.textContent = "Uploading " + file.name + "…";
  try {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/upload", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      els.dashSub.textContent = "Upload failed: " + (data.error || "unknown error");
      return;
    }
    els.sourceChip.textContent = file.name;
    els.resetButton.hidden = false;
    await revealTrace(data.trace);
    render(data);
  } catch (err) {
    els.dashSub.textContent = "Upload error: " + err.message;
  } finally {
    hideLoading();
    els.uploadButton.disabled = false;
    els.fileInput.value = "";
  }
}

async function resetData() {
  els.resetButton.disabled = true;
  showLoading();
  els.loadingText.textContent = "Resetting to sample data…";
  try {
    const res = await fetch("/api/reset", { method: "POST" });
    const data = await res.json();
    els.sourceChip.textContent = "sample data";
    els.resetButton.hidden = true;
    await revealTrace(data.trace);
    render(data);
  } catch (err) {
    els.dashSub.textContent = "Reset error: " + err.message;
  } finally {
    hideLoading();
    els.resetButton.disabled = false;
  }
}

// Reveal the trace step-by-step so the "agent is working" reads on screen.
async function revealTrace(trace) {
  els.traceList.innerHTML = "";
  const items = trace.map((step) => {
    const li = document.createElement("li");
    li.className = "trace-step";
    li.innerHTML =
      `<span class="trace-dot"></span>` +
      `<div class="trace-body">` +
      `<div class="trace-head">` +
      `<span class="trace-index">${step.id}</span>` +
      `<span class="step-name">${step.name}</span>` +
      `<span class="step-status pending">queued</span>` +
      `</div>` +
      `<div class="trace-detail" hidden></div>` +
      `</div>`;
    els.traceList.appendChild(li);
    return li;
  });

  for (let i = 0; i < items.length; i++) {
    const step = trace[i];
    const li = items[i];
    li.querySelector(".trace-dot").classList.add("active");
    li.querySelector(".step-status").className = "step-status running";
    li.querySelector(".step-status").textContent = "running…";
    els.loadingText.textContent = humanStage(step.name) + "…";
    await sleep(320);

    li.querySelector(".trace-dot").classList.remove("active");
    li.querySelector(".trace-dot").classList.add(step.status === "done" ? "done" : "failed");
    const statusEl = li.querySelector(".step-status");
    statusEl.className = "step-status " + (step.status === "done" ? "ok" : "bad");
    statusEl.textContent = step.status + " · " + step.duration_ms + "ms";

    const detail = li.querySelector(".trace-detail");
    if (Object.keys(step.output || {}).length) {
      detail.hidden = false;
      detail.innerHTML =
        `<details><summary>${summaryOf(step)}</summary>` +
        `<pre>${escapeHtml(JSON.stringify(step.output, null, 2))}</pre></details>`;
    }
  }
}

// ---- Render ----------------------------------------------------------------
function render(data) {
  if (!data.ok) {
    els.dashSub.textContent = "Pipeline failed: " + (data.error || "unknown error");
    return;
  }
  renderKpis(data.metrics);
  renderBurnChart(data.metrics.monthly_burn);
  renderDonut(data.metrics.category_totals);
  renderFlags(data.flagged);
  renderAnomalies(data.anomalies);
}

function renderKpis(m) {
  els.dashSub.textContent =
    "Analysed " + m.months_covered + " months · " + fmtMoney(m.total_spend) + " total spend";

  els.kpiBurnValue.textContent = fmtMoney(m.recent_monthly_burn) + "/mo";
  els.kpiBurnSub.textContent = "avg " + fmtMoney(m.avg_monthly_burn) + "/mo";

  els.kpiRunwayValue.textContent = m.runway_months.toFixed(1) + " mo";
  els.kpiRunwaySub.textContent = "at current burn";
  els.kpiRunwayValue.style.color = m.runway_months < 3 ? "var(--bad)" : m.runway_months < 6 ? "var(--warn)" : "var(--ok)";

  els.kpiCashValue.textContent = fmtMoney(m.starting_cash);
  els.kpiCashSub.textContent = "cash on hand";

  els.kpiImpactValue.textContent = fmtMoney(m.anomaly_cost_impact.monthly_equivalent) + "/mo";
  els.kpiImpactSub.textContent = (m.anomaly_cost_impact.fraction_of_burn * 100).toFixed(1) + "% of burn";
}

function renderFlags(flagged) {
  els.flagsCount.textContent = flagged.length + " items";
  els.flagList.innerHTML = "";
  flagged.forEach((f, i) => {
    const li = document.createElement("li");
    li.className = "flag";
    li.innerHTML =
      `<div class="flag-rank">${i + 1}</div>` +
      `<div class="flag-body">` +
      `<div class="flag-head">` +
      `<span class="flag-vendor">${escapeHtml(f.vendor)}</span>` +
      `<span class="flag-cost">${fmtMoney(f.annual_cost_estimate)}/yr</span>` +
      `</div>` +
      `<div class="flag-reason">${escapeHtml(f.recommendation)}</div>` +
      `</div>`;
    els.flagList.appendChild(li);
  });
}

function renderAnomalies(anomalies) {
  els.anomaliesCount.textContent = anomalies.length + " found";
  els.anomalyList.innerHTML = "";
  for (const a of anomalies) {
    const li = document.createElement("li");
    li.className = "anomaly";
    li.innerHTML =
      `<div class="anomaly-head">` +
      `<span class="anomaly-type">${escapeHtml(a.type)}</span>` +
      `<span class="anomaly-vendor">${escapeHtml(a.vendor)}</span>` +
      `<span class="anomaly-amount">${a.amount != null ? fmtMoney(a.amount) : "—"}</span>` +
      `</div>` +
      `<div class="anomaly-reason">${escapeHtml(a.reason)}</div>`;
    els.anomalyList.appendChild(li);
  }
}

// ---- Charts (hand-rolled SVG, no CDN) --------------------------------------
const PALETTE = ["#4ea1ff", "#3ddc97", "#ffb454", "#ff6b6b", "#b388ff", "#4dd0e1", "#f06292", "#aed581"];

function renderBurnChart(monthly) {
  const months = Object.keys(monthly);
  const values = months.map((k) => monthly[k]);
  const svg = els.chartBurn;
  const W = 640, H = 260, padL = 54, padR = 16, padT = 18, padB = 34;
  const max = Math.max(...values) * 1.15;

  let inner = "";
  // gridlines + y labels
  for (let i = 0; i <= 4; i++) {
    const y = padT + (H - padT - padB) * (i / 4);
    const val = max * (1 - i / 4);
    inner += `<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" class="gridline"/>`;
    inner += `<text x="${padL - 8}" y="${y + 4}" class="axis-label" text-anchor="end">$${Math.round(val / 1000)}k</text>`;
  }

  const x = (i) => padL + (W - padL - padR) * (i / (months.length - 1));
  const y = (v) => padT + (H - padT - padB) * (1 - v / max);

  // area fill
  const line = values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const area = `${x(0)},${H - padB} ${line} ${x(values.length - 1)},${H - padB}`;
  inner += `<polygon points="${area}" class="chart-area"/>`;
  inner += `<polyline points="${line}" class="chart-line"/>`;

  // dots + labels
  values.forEach((v, i) => {
    inner += `<circle cx="${x(i)}" cy="${y(v)}" r="4" class="chart-dot"/>`;
    const label = months[i].slice(5);
    inner += `<text x="${x(i)}" y="${H - padB + 18}" class="axis-label" text-anchor="middle">${label}</text>`;
  });

  svg.innerHTML = inner;
}

function renderDonut(categoryTotals) {
  const entries = Object.entries(categoryTotals);
  const total = entries.reduce((s, [, v]) => s + v, 0);
  els.donutTotal.textContent = fmtMoney(total);

  const svg = els.chartDonut;
  const cx = 100, cy = 100, r = 74, sw = 28;
  const C = 2 * Math.PI * r;

  let offset = 0;
  let arcs = "";
  let legend = "";
  entries.forEach(([name, val], i) => {
    const frac = val / total;
    const len = frac * C;
    const color = PALETTE[i % PALETTE.length];
    arcs += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="${sw}"
      stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-offset}"
      transform="rotate(-90 ${cx} ${cy})"/>`;
    offset += len;
    legend +=
      `<li><span class="legend-swatch" style="background:${color}"></span>` +
      `<span class="legend-name">${escapeHtml(name)}</span>` +
      `<span class="legend-val">${fmtMoney(val)} · ${(frac * 100).toFixed(0)}%</span></li>`;
  });
  svg.innerHTML = arcs;
  els.donutLegend.innerHTML = legend;
}

// ---- Ask --------------------------------------------------------------
async function askQuestion(e) {
  if (e) e.preventDefault();
  const q = els.askInput.value.trim();
  if (!q) return;

  els.askAnswer.hidden = false;
  els.askStages.innerHTML = "";
  els.askAnswerText.textContent = "Working…";

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    const data = await res.json();
    els.askAnswerText.textContent = data.answer;
    els.askStages.innerHTML = "";
    for (const s of data.stages_consulted || []) {
      const chip = document.createElement("span");
      chip.className = "stage-chip";
      chip.textContent = s;
      els.askStages.appendChild(chip);
    }
  } catch (err) {
    els.askAnswerText.textContent = "error: " + err.message;
  }
}

// ---- Helpers -----------------------------------------------------------
function summaryOf(step) {
  const o = step.output || {};
  if ("row_count" in o) return `${o.row_count} rows read`;
  if ("candidate_count" in o) return `${o.candidate_count} candidates`;
  if ("total_after_investigation" in o) return `${o.total_after_investigation} enriched`;
  if ("runway_months" in o) return `${o.runway_months} mo runway · ${fmtMoney(o.recent_monthly_burn)}/mo burn`;
  if ("recommendation_count" in o) return `${o.recommendation_count} recommendations`;
  if ("flagged_count" in o) return `${o.flagged_count} flagged`;
  return "done";
}

function humanStage(name) {
  return name.split("_").map((w) => w[0].toUpperCase() + w.slice(1)).join(" ");
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

function fmtMoney(n) {
  return "$" + Number(n).toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
