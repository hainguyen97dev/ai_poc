import { renderMarkdown, renderMermaidDiagrams } from "./markdown.js";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const dom = {
  agentSelect: $("#agent-select"),
  agentDescription: $("#agent-description"),
  docsLink: $("#docs-link"),
  connectionStatus: $("#connection-status"),
  healthButton: $("#health-button"),
  historySelect: $("#history-select"),
  usageBadge: $("#usage-badge"),
  usagePopover: $("#usage-popover"),
  usageBreakdown: $("#usage-breakdown"),
  taskType: $("#task-type"),
  form: $("#request-form"),
  exampleSelect: $("#example-select"),
  resetButton: $("#reset-button"),
  runButton: $("#run-button"),
  copyReportButton: $("#copy-report-button"),
  requestState: $("#request-state"),
  resultMeta: $("#result-meta"),
  metrics: $("#metrics"),
  emptyState: $("#empty-state"),
  loadingState: $("#loading-state"),
  analysisOutput: $("#analysis-output"),
  previewBanner: $("#preview-banner"),
  reasoningBlock: $("#reasoning-block"),
  reasoningContent: $("#reasoning-content"),
  chatPanel: $("#chat-panel"),
  chatMessages: $("#chat-messages"),
  chatForm: $("#chat-form"),
  chatInput: $("#chat-input"),
  chatSendButton: $("#chat-send-button"),
  versionSelect: $("#version-select"),
  refineButton: $("#refine-button"),
  toast: $("#toast"),
};

let agents = [];
let activeAgent = null;
let analysisText = "";
let toastTimer = null;
// The session currently shown in the chat panel — the full SessionResponse
// from GET /api/v1/sessions/{id} (see ada-service/main.py), refreshed after
// every chat message / refine so the panel always reflects the backend.
let activeSession = null;
// True while showing a static "Load example" preview (canned draft + chat,
// no backend session behind it) rather than a real run — see renderPreview().
let isPreview = false;

function endpoint(path) {
  return `${activeAgent.baseUrl.replace(/\/$/, "")}${path}`;
}

function setConnection(label, type = "neutral") {
  dom.connectionStatus.className = `status-chip status-${type}`;
  dom.connectionStatus.innerHTML = `<span class="status-dot" aria-hidden="true"></span><span>${label}</span>`;
}

function setRequestState(label, type = "neutral") {
  dom.requestState.className = `status-chip status-${type}`;
  dom.requestState.textContent = label;
}

function showToast(message) {
  clearTimeout(toastTimer);
  dom.toast.textContent = message;
  dom.toast.hidden = false;
  toastTimer = setTimeout(() => { dom.toast.hidden = true; }, 4500);
}

function splitList(value) {
  return value.split(/[\n,]/).map((item) => item.trim()).filter(Boolean);
}

function setValue(id, value = "") {
  const element = document.getElementById(id);
  if (!element) return;
  element.value = Array.isArray(value) ? value.join("\n") : (value ?? "");
}

function switchTask() {
  const selected = dom.taskType.value;
  $$('[data-task-panel]').forEach((panel) => {
    panel.hidden = panel.dataset.taskPanel !== selected;
  });
}

function humanizeTask(task) {
  const labels = {
    analyze_requirement: "Analyze requirement",
    gap_impact_analysis: "Gap & impact analysis",
    draft_adr: "Draft ADR",
  };
  return labels[task] || task || "Unknown";
}

function showReasoning(reasoning) {
  if (!reasoning) {
    dom.reasoningBlock.hidden = true;
    dom.reasoningContent.innerHTML = "";
    return;
  }
  dom.reasoningContent.innerHTML = renderMarkdown(reasoning);
  dom.reasoningBlock.hidden = false;
  renderMermaidDiagrams(dom.reasoningContent);
}

function resetResult() {
  analysisText = "";
  activeSession = null;
  isPreview = false;
  dom.previewBanner.hidden = true;
  dom.resultMeta.hidden = true;
  dom.metrics.hidden = true;
  dom.copyReportButton.hidden = true;
  dom.emptyState.hidden = false;
  dom.loadingState.hidden = true;
  dom.analysisOutput.hidden = true;
  dom.analysisOutput.textContent = "";
  showReasoning(null);
  dom.chatPanel.hidden = true;
  dom.chatMessages.innerHTML = "";
  dom.chatInput.value = "";
  setRequestState("Idle");
  setSessionUrlParam(null);
}

function renderResult(data, elapsedMs) {
  analysisText = data.analysis || data.detail || "No analysis content returned.";
  isPreview = false;
  dom.previewBanner.hidden = true;
  dom.emptyState.hidden = true;
  dom.loadingState.hidden = true;
  dom.resultMeta.hidden = false;
  dom.metrics.hidden = false;
  dom.copyReportButton.hidden = false;
  $("#result-task").textContent = humanizeTask(data.task_type || dom.taskType.value);
  $("#result-request-id").textContent = data.request_id || $("#requirement-id").value || $("#change-request-id").value || "Auto-generated";
  $("#result-review").textContent = data.review_status === "PENDING" ? "Pending SA review" : (data.review_status || "Not available");
  $("#metric-assumptions").textContent = data.assumptions_count ?? "—";
  $("#metric-questions").textContent = data.questions_count ?? "—";
  $("#metric-risks").textContent = data.risks_count ?? "—";
  $("#metric-elapsed").textContent = `${(elapsedMs / 1000).toFixed(1)}s`;
  showReasoning(data.reasoning);
  dom.analysisOutput.innerHTML = renderMarkdown(analysisText);
  dom.analysisOutput.hidden = false;
  renderMermaidDiagrams(dom.analysisOutput);
  setRequestState(data.status || "Completed", data.status === "SUCCESS" ? "online" : "warning");
}

// ---------------------------------------------------------------------------
// Chat + session history — talks to GET/POST /api/v1/sessions[...] (see
// ada-service/main.py). A session is created server-side on every /analyze
// call; this console just displays it and lets the SA converse and refine.
// ---------------------------------------------------------------------------

function sessionsBase() {
  return endpoint(activeAgent.endpoints.sessions);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// MiniMax/Anthropic completions have been observed taking 30-90+ seconds
// (see agent-sa/logs/ada.log) — long enough that a home router/VPN/proxy can
// silently drop the idle connection before the model ever replies. When that
// happens, fetch() rejects with a generic TypeError whose message is just
// "Failed to fetch" — indistinguishable, from the browser's side, from the
// server never having been reachable at all. Say so, so a slow reply doesn't
// read as "the console is broken".
function describeFetchError(error) {
  if (error instanceof TypeError) {
    return "Network error — possibly a slow/idle connection dropped while the model was still " +
      "thinking (this can take a minute or more). Check the ADA service is still running, then try again.";
  }
  return error.message;
}

function setSessionUrlParam(sessionId) {
  const url = new URL(window.location.href);
  if (sessionId) {
    url.searchParams.set("session", sessionId);
  } else {
    url.searchParams.delete("session");
  }
  window.history.replaceState({}, "", url);
}

function chatMessageHtml(m) {
  const reasoning = m.reasoning
    ? `<details class="chat-message-reasoning"><summary>Reasoning</summary><div>${renderMarkdown(m.reasoning)}</div></details>`
    : "";
  return `<div class="chat-message chat-message-${m.role} markdown-output">${renderMarkdown(m.content)}${reasoning}</div>`;
}

function renderChatMessages() {
  const messages = activeSession?.messages || [];
  if (!messages.length) {
    dom.chatMessages.innerHTML = `<p class="chat-empty">No messages yet — answer an open question above or ask ADA anything about this draft.</p>`;
    return;
  }
  dom.chatMessages.innerHTML = messages.map(chatMessageHtml).join("");
  dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
  renderMermaidDiagrams(dom.chatMessages);
}

function renderVersionSelect() {
  const versions = activeSession?.versions || [];
  dom.versionSelect.innerHTML = versions
    .map((v) => `<option value="${v.version_no}">v${v.version_no} — ${v.status}</option>`)
    .join("");
  const latest = versions[versions.length - 1];
  if (latest) dom.versionSelect.value = String(latest.version_no);
}

function showVersion(versionNo) {
  const version = (activeSession?.versions || []).find((v) => v.version_no === versionNo);
  if (!version) return;
  analysisText = version.content;
  showReasoning(version.reasoning);
  dom.analysisOutput.innerHTML = renderMarkdown(analysisText);
  dom.analysisOutput.hidden = false;
  renderMermaidDiagrams(dom.analysisOutput);
  dom.resultMeta.hidden = false;
  dom.metrics.hidden = false;
  dom.copyReportButton.hidden = false;
  $("#result-review").textContent = version.status === "COMPLETED" ? "Pending SA review" : version.status;
  $("#metric-assumptions").textContent = version.assumptions_count;
  $("#metric-questions").textContent = version.questions_count;
  $("#metric-risks").textContent = version.risks_count;
}

function renderPreview(preview) {
  if (!preview) return;
  activeSession = null;
  isPreview = true;
  analysisText = preview.analysis || "";

  dom.previewBanner.hidden = false;
  dom.emptyState.hidden = true;
  dom.loadingState.hidden = true;
  dom.resultMeta.hidden = true;
  dom.copyReportButton.hidden = true; // nothing real behind it yet — see preview banner
  dom.metrics.hidden = false;
  $("#metric-assumptions").textContent = preview.assumptions_count ?? "—";
  $("#metric-questions").textContent = preview.questions_count ?? "—";
  $("#metric-risks").textContent = preview.risks_count ?? "—";
  $("#metric-elapsed").textContent = "—";
  showReasoning(preview.reasoning);
  dom.analysisOutput.innerHTML = renderMarkdown(analysisText);
  dom.analysisOutput.hidden = false;
  renderMermaidDiagrams(dom.analysisOutput);
  setRequestState("Example", "neutral");

  const chat = preview.chat || [];
  dom.chatMessages.innerHTML = chat.length
    ? chat.map(chatMessageHtml).join("")
    : `<p class="chat-empty">This example has no sample conversation.</p>`;
  renderMermaidDiagrams(dom.chatMessages);
  dom.versionSelect.innerHTML = `<option value="1">v1 — example</option>`;
  dom.chatPanel.hidden = false;
  setChattable(false); // preview isn't a real session — nothing to POST to yet
}

function setChattable(chattable) {
  dom.chatInput.disabled = !chattable;
  dom.chatSendButton.disabled = !chattable;
  dom.refineButton.disabled = !chattable;
}

async function openSession(sessionId, { updateUrl = false } = {}) {
  if (!activeAgent) return;
  let session;
  try {
    const response = await fetch(`${sessionsBase()}/${encodeURIComponent(sessionId)}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    session = await response.json();
  } catch (error) {
    showToast(`Could not load session: ${error.message}`);
    return;
  }

  activeSession = session;
  isPreview = false;
  dom.previewBanner.hidden = true;
  dom.emptyState.hidden = true;
  dom.loadingState.hidden = true;
  const latest = activeSession.versions[activeSession.versions.length - 1];
  $("#result-task").textContent = humanizeTask(activeSession.task_type);
  // Show the human-facing analysis id (e.g. "REQ-001"), not the session's
  // own internal id — the latter can be a UUID and repeats-across-runs is
  // exactly why it's not the session key (see main.py's _persist_session).
  $("#result-request-id").textContent = latest?.analysis_id || activeSession.id;

  renderVersionSelect();
  if (latest) showVersion(latest.version_no);
  renderChatMessages();
  dom.chatPanel.hidden = false;
  setChattable(latest?.status === "COMPLETED");

  if (updateUrl) setSessionUrlParam(sessionId);
}

async function loadHistorySessions() {
  if (!activeAgent) return;
  try {
    const response = await fetch(sessionsBase());
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const sessions = await response.json();
    dom.historySelect.innerHTML =
      `<option value="">Recent sessions…</option>` +
      sessions
        .map(
          (s) =>
            `<option value="${s.id}">${humanizeTask(s.task_type)} · ${escapeHtml(s.subject_ref || s.id)}</option>`
        )
        .join("");
  } catch {
    // History is a convenience, not required to use the console — stay quiet.
  }
}

function humanizeUsageKind(kind) {
  return kind === "chat_reply" ? "Chat replies" : humanizeTask(kind);
}

async function loadUsageStats() {
  if (!activeAgent) return;
  try {
    const response = await fetch(endpoint(activeAgent.endpoints.usage));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const usage = await response.json();
    dom.usageBadge.querySelector("span").textContent = `${usage.total} request${usage.total === 1 ? "" : "s"}`;
    const entries = Object.entries(usage.by_kind || {}).filter(([, count]) => count > 0);
    dom.usageBreakdown.innerHTML = entries.length
      ? entries
          .map(([kind, count]) => `<li><span>${humanizeUsageKind(kind)}</span><strong>${count}</strong></li>`)
          .join("")
      : `<li class="usage-empty">No requests yet</li>`;
  } catch {
    // Usage is a convenience, not required to use the console — stay quiet.
  }
}

function toggleUsagePopover(forceShow) {
  const show = forceShow ?? dom.usagePopover.hidden;
  dom.usagePopover.hidden = !show;
  dom.usageBadge.setAttribute("aria-expanded", String(show));
}

async function handleChatSubmit(event) {
  event.preventDefault();
  if (!activeSession) return;
  const message = dom.chatInput.value.trim();
  if (!message) return;

  setChattable(false);
  const waiting = document.createElement("p");
  waiting.className = "chat-waiting";
  waiting.textContent = "Waiting for the model — this can take a minute or more…";
  dom.chatMessages.appendChild(waiting);
  dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;

  try {
    const response = await fetch(`${sessionsBase()}/${encodeURIComponent(activeSession.id)}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    dom.chatInput.value = "";
    await openSession(activeSession.id); // re-renders the chat list, replacing the waiting note
    loadUsageStats();
  } catch (error) {
    waiting.remove();
    showToast(`Message failed: ${describeFetchError(error)}`);
    setChattable(true);
  }
}

async function handleRefine() {
  if (!activeSession) return;
  dom.refineButton.disabled = true;
  dom.refineButton.classList.add("is-loading");
  showToast("Refining — this can take a minute or more…");
  try {
    const response = await fetch(`${sessionsBase()}/${encodeURIComponent(activeSession.id)}/refine`, {
      method: "POST",
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    activeSession = data;
    renderVersionSelect();
    const latest = activeSession.versions[activeSession.versions.length - 1];
    if (latest) showVersion(latest.version_no);
    renderChatMessages();
    setChattable(latest?.status === "COMPLETED");
    loadHistorySessions();
    loadUsageStats();
    showToast(`Draft refined — now v${latest?.version_no ?? "?"}`);
  } catch (error) {
    showToast(`Refine failed: ${describeFetchError(error)}`);
  } finally {
    dom.refineButton.disabled = false;
    dom.refineButton.classList.remove("is-loading");
  }
}

async function copyReport() {
  if (!analysisText) return;
  try {
    await navigator.clipboard.writeText(analysisText);
    showToast("Report copied to clipboard");
  } catch {
    showToast("Clipboard access is unavailable in this browser");
  }
}

function buildPayload() {
  const task = dom.taskType.value;
  const payload = {
    task_type: task,
    requirement_id: $("#requirement-id").value.trim() || null,
    context: {},
  };

  if (task === "analyze_requirement") {
    payload.requirement_doc = $("#requirement-doc").value.trim() || null;
    payload.context = {
      as_is_architecture: $("#as-is-architecture").value.trim() || null,
      tech_stack: splitList($("#tech-stack").value),
      constraints: splitList($("#requirement-constraints").value),
      known_issues: splitList($("#known-issues").value),
    };
  } else if (task === "gap_impact_analysis") {
    payload.change_request_id = $("#change-request-id").value.trim() || null;
    payload.change_description = $("#change-description").value.trim() || null;
    payload.context = {
      affected_modules: splitList($("#affected-modules").value),
      current_design_doc: $("#current-design-doc").value.trim() || null,
    };
  } else {
    payload.decision_title = $("#decision-title").value.trim() || null;
    payload.context = {
      options_to_evaluate: splitList($("#options-to-evaluate").value),
      constraints: splitList($("#adr-constraints").value),
    };
  }

  return payload;
}

function applySample(sample) {
  dom.form.reset();
  dom.taskType.value = sample.task_type;
  switchTask();
  setValue("requirement-id", sample.requirement_id);
  setValue("requirement-doc", sample.requirement_doc);
  setValue("change-request-id", sample.change_request_id);
  setValue("change-description", sample.change_description);
  setValue("decision-title", sample.decision_title);
  const context = sample.context || {};
  setValue("as-is-architecture", context.as_is_architecture);
  setValue("tech-stack", context.tech_stack);
  setValue("requirement-constraints", context.constraints);
  setValue("known-issues", context.known_issues);
  setValue("affected-modules", context.affected_modules);
  setValue("current-design-doc", context.current_design_doc);
  setValue("options-to-evaluate", context.options_to_evaluate);
  setValue("adr-constraints", context.constraints);
}

async function checkHealth({ quiet = false } = {}) {
  if (!activeAgent) return false;
  setConnection("Checking…", "warning");
  try {
    const response = await fetch(endpoint(activeAgent.endpoints.health), { signal: AbortSignal.timeout(5000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    setConnection(data.status === "healthy" ? "Connected" : data.status, "online");
    return true;
  } catch (error) {
    setConnection("Offline", "error");
    if (!quiet) showToast(`Cannot reach ${activeAgent.shortName}: ${error.message}`);
    return false;
  }
}

async function loadExample(taskType) {
  if (!taskType) return;
  try {
    const response = await fetch(endpoint(activeAgent.endpoints.samples));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const sample = data.samples?.[taskType];
    if (!sample) throw new Error("No sample exists for this task");
    applySample(sample);
    dom.exampleSelect.value = taskType;
    renderPreview(sample.preview);
    showToast("Example loaded");
  } catch (error) {
    showToast(`Could not load example: ${error.message}`);
  }
}

async function runAnalysis(event) {
  event.preventDefault();
  const online = await checkHealth({ quiet: true });
  if (!online) {
    showToast(`Start ${activeAgent.shortName} at ${activeAgent.baseUrl} first.`);
    return;
  }

  const payload = buildPayload();
  const startedAt = performance.now();
  dom.runButton.disabled = true;
  dom.runButton.classList.add("is-loading");
  isPreview = false;
  dom.previewBanner.hidden = true;
  dom.chatPanel.hidden = true;
  dom.emptyState.hidden = true;
  dom.analysisOutput.hidden = true;
  showReasoning(null);
  dom.resultMeta.hidden = true;
  dom.copyReportButton.hidden = true;
  dom.metrics.hidden = true;
  dom.loadingState.hidden = false;
  setRequestState("Running", "warning");

  try {
    const response = await fetch(endpoint(activeAgent.endpoints.analyze), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({ detail: `HTTP ${response.status}: invalid JSON response` }));
    const elapsed = performance.now() - startedAt;
    if (!response.ok) throw Object.assign(new Error(data.detail || `HTTP ${response.status}`), { data, elapsed });
    renderResult(data, elapsed);
    if (data.session_id) {
      await openSession(data.session_id, { updateUrl: true });
      loadHistorySessions();
      loadUsageStats();
    }
  } catch (error) {
    const detail = error.data ? error.data.detail : describeFetchError(error);
    renderResult(error.data || { status: "ERROR", detail }, error.elapsed || performance.now() - startedAt);
    setRequestState("Failed", "error");
    showToast(detail);
  } finally {
    dom.runButton.disabled = false;
    dom.runButton.classList.remove("is-loading");
  }
}

function activateAgent(id) {
  activeAgent = agents.find((agent) => agent.id === id) || agents[0];
  if (!activeAgent) return;
  dom.agentSelect.value = activeAgent.id;
  dom.agentDescription.textContent = `${activeAgent.shortName} · ${activeAgent.description} · ${activeAgent.baseUrl}`;
  dom.docsLink.href = endpoint(activeAgent.endpoints.docs);
  setConnection("Not checked");
  resetResult();
  checkHealth({ quiet: true });
  loadHistorySessions();
  loadUsageStats();
}

async function initialize() {
  // Read this before activateAgent()'s resetResult() strips ?session= from the URL.
  const requestedSessionId = new URL(window.location.href).searchParams.get("session");
  try {
    const response = await fetch("./agents.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const registry = await response.json();
    agents = registry.agents || [];
    if (!agents.length) throw new Error("Agent registry is empty");
    dom.agentSelect.innerHTML = agents.map((agent) => `<option value="${agent.id}">${agent.shortName} — ${agent.name}</option>`).join("");
    activateAgent(agents[0].id);

    if (requestedSessionId) await openSession(requestedSessionId, { updateUrl: true });
  } catch (error) {
    dom.agentDescription.textContent = "Could not load agent registry";
    showToast(`Console initialization failed: ${error.message}`);
  }
}

dom.agentSelect.addEventListener("change", () => activateAgent(dom.agentSelect.value));
dom.healthButton.addEventListener("click", () => checkHealth());
dom.historySelect.addEventListener("change", () => {
  if (dom.historySelect.value) openSession(dom.historySelect.value, { updateUrl: true });
});
dom.copyReportButton.addEventListener("click", copyReport);
dom.taskType.addEventListener("change", switchTask);
dom.exampleSelect.addEventListener("change", () => loadExample(dom.exampleSelect.value));
dom.resetButton.addEventListener("click", () => {
  dom.form.reset();
  dom.exampleSelect.value = "";
  switchTask();
  resetResult();
});
dom.form.addEventListener("submit", runAnalysis);
dom.chatForm.addEventListener("submit", handleChatSubmit);
dom.refineButton.addEventListener("click", handleRefine);
dom.versionSelect.addEventListener("change", () => showVersion(Number(dom.versionSelect.value)));
dom.usageBadge.addEventListener("click", (event) => {
  event.stopPropagation();
  toggleUsagePopover();
});
document.addEventListener("click", (event) => {
  if (!dom.usagePopover.hidden && !dom.usagePopover.contains(event.target)) toggleUsagePopover(false);
});

switchTask();
initialize();
