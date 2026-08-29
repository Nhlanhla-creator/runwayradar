const runButton = document.getElementById("run-button");
const runStatus = document.getElementById("run-status");
const metricsCard = document.getElementById("metrics-card");
const metricsBody = document.getElementById("metrics-body");
const traceCard = document.getElementById("trace-card");
const traceList = document.getElementById("trace-list");
const askCard = document.getElementById("ask-card");

runButton.addEventListener("click", runLoop);

async function runLoop() {
  runButton.disabled = true;
  runStatus.textContent = "running…";

  try {
    const res = await fetch("/api/run");
    const data = await res.json();
    render(data);
    runStatus.textContent = data.ok ? "done" : "failed";
  } catch (err) {
    runStatus.textContent = "error: " + err.message;
  } finally {
    runButton.disabled = false;
  }
}

function render(data) {
  metricsCard.hidden = false;
  metricsBody.textContent = data.ok
    ? `Read ${data.row_count} transactions.`
    : "Pipeline failed: " + (data.error || "unknown error");

  traceCard.hidden = false;
  traceList.innerHTML = "";
  for (const step of data.trace) {
    const li = document.createElement("li");
    const statusClass = "step-" + step.status;
    li.innerHTML =
      `<span class="step-name">${step.name}</span> ` +
      `<span class="${statusClass}">[${step.status}]</span> ` +
      `<span class="step-meta">${step.duration_ms}ms</span>`;
    traceList.appendChild(li);
  }

  askCard.hidden = false;
}
