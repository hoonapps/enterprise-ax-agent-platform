from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def get_dashboard() -> HTMLResponse:
    return HTMLResponse(content=_DASHBOARD_HTML)


_DASHBOARD_HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Enterprise AX Agent Operations</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --surface: #ffffff;
      --surface-muted: #eef1f4;
      --border: #d8dde3;
      --text: #1d2733;
      --muted: #657080;
      --accent: #126f6a;
      --accent-strong: #0d5652;
      --warn-bg: #fff6db;
      --warn-text: #765600;
      --danger-bg: #fde8e8;
      --danger-text: #9b1c1c;
      --ok-bg: #e6f4ea;
      --ok-text: #146c2e;
      font-family:
        Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
    }

    button,
    input {
      font: inherit;
    }

    .shell {
      width: min(1440px, 100%);
      margin: 0 auto;
      padding: 24px;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }

    .title h1 {
      margin: 0;
      font-size: 24px;
      line-height: 1.25;
      letter-spacing: 0;
    }

    .title p {
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 14px;
    }

    .controls {
      display: flex;
      align-items: flex-end;
      gap: 10px;
      flex-wrap: wrap;
    }

    .field {
      display: grid;
      gap: 5px;
      min-width: 150px;
    }

    .field label {
      font-size: 12px;
      color: var(--muted);
    }

    .field input {
      height: 38px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0 10px;
      background: var(--surface);
      color: var(--text);
    }

    .refresh {
      height: 38px;
      border: 1px solid var(--accent-strong);
      border-radius: 6px;
      padding: 0 14px;
      background: var(--accent);
      color: white;
      cursor: pointer;
    }

    .refresh:disabled {
      opacity: 0.68;
      cursor: wait;
    }

    .action-group {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }

    .action-button {
      min-height: 30px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0 9px;
      background: var(--surface);
      color: var(--text);
      cursor: pointer;
      font-size: 12px;
      font-weight: 650;
    }

    .action-button.approve {
      border-color: #8bbd98;
      color: var(--ok-text);
    }

    .action-button.reject {
      border-color: #e0a0a0;
      color: var(--danger-text);
    }

    .action-button:disabled {
      opacity: 0.58;
      cursor: wait;
    }

    .statusbar {
      min-height: 30px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
      color: var(--muted);
      font-size: 13px;
    }

    .error {
      color: var(--danger-text);
      font-weight: 600;
    }

    .metric-grid {
      display: grid;
      grid-template-columns: repeat(6, minmax(130px, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }

    .metric {
      min-height: 96px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--surface);
      padding: 14px;
    }

    .metric .label {
      color: var(--muted);
      font-size: 13px;
    }

    .metric .value {
      margin-top: 10px;
      font-size: 26px;
      font-weight: 720;
      line-height: 1.1;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }

    .panel-grid {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 14px;
      align-items: start;
    }

    .panel {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--surface);
      min-width: 0;
    }

    .panel header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid var(--border);
      padding: 12px 14px;
    }

    .panel h2 {
      margin: 0;
      font-size: 15px;
      line-height: 1.4;
      letter-spacing: 0;
    }

    .panel .meta {
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }

    .panel-body {
      padding: 12px 14px 14px;
    }

    .stack {
      display: grid;
      gap: 14px;
    }

    .bars {
      display: grid;
      gap: 9px;
    }

    .bar-row {
      display: grid;
      grid-template-columns: minmax(120px, 1fr) 3fr 52px;
      align-items: center;
      gap: 9px;
      min-height: 26px;
      font-size: 13px;
    }

    .bar-label {
      color: var(--text);
      overflow-wrap: anywhere;
    }

    .bar-track {
      height: 8px;
      border-radius: 999px;
      background: var(--surface-muted);
      overflow: hidden;
    }

    .bar-fill {
      height: 100%;
      width: 0%;
      background: var(--accent);
    }

    .bar-value {
      text-align: right;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }

    .table-wrap {
      width: 100%;
      overflow-x: auto;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }

    th,
    td {
      padding: 10px 8px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
    }

    th {
      color: var(--muted);
      font-weight: 650;
      white-space: nowrap;
    }

    td {
      overflow-wrap: anywhere;
    }

    tr:last-child td {
      border-bottom: 0;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      border-radius: 999px;
      padding: 0 8px;
      font-size: 12px;
      font-weight: 650;
      background: var(--surface-muted);
      color: var(--text);
      white-space: nowrap;
    }

    .badge.ok {
      background: var(--ok-bg);
      color: var(--ok-text);
    }

    .badge.warn {
      background: var(--warn-bg);
      color: var(--warn-text);
    }

    .badge.danger {
      background: var(--danger-bg);
      color: var(--danger-text);
    }

    .empty {
      color: var(--muted);
      padding: 12px 0;
      font-size: 13px;
    }

    .json {
      margin: 0;
      max-height: 240px;
      overflow: auto;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: #fbfcfd;
      padding: 12px;
      color: #223044;
      font-size: 12px;
      line-height: 1.45;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    @media (max-width: 1180px) {
      .metric-grid {
        grid-template-columns: repeat(3, minmax(150px, 1fr));
      }

      .panel-grid {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 720px) {
      .shell {
        padding: 16px;
      }

      .topbar {
        align-items: stretch;
        flex-direction: column;
      }

      .controls,
      .field,
      .refresh {
        width: 100%;
      }

      .metric-grid {
        grid-template-columns: 1fr 1fr;
      }

      .bar-row {
        grid-template-columns: 1fr;
        gap: 5px;
      }

      .bar-value {
        text-align: left;
      }
    }

    @media (max-width: 480px) {
      .metric-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="topbar" aria-labelledby="page-title">
      <div class="title">
        <h1 id="page-title">Enterprise AX Agent Operations</h1>
        <p>Agent 실행, 승인 대기, tool 상태, 감사 이벤트를 한 화면에서 확인합니다.</p>
      </div>
      <form class="controls" id="controls">
        <div class="field">
          <label for="tenant-id">Tenant</label>
          <input id="tenant-id" name="tenant" value="default" autocomplete="off">
        </div>
        <div class="field">
          <label for="event-limit">Event limit</label>
          <input id="event-limit" name="eventLimit" type="number" min="10" value="500">
        </div>
        <div class="field">
          <label for="api-key">API Key</label>
          <input id="api-key" name="apiKey" type="password" autocomplete="off">
        </div>
        <button class="refresh" id="refresh" type="submit">새로고침</button>
      </form>
    </section>

    <section class="statusbar" aria-live="polite">
      <span id="load-state">데이터를 불러오는 중입니다.</span>
      <span id="generated-at"></span>
    </section>

    <section class="metric-grid" aria-label="운영 지표">
      <article class="metric">
        <div class="label">문서</div>
        <div class="value" id="metric-documents">-</div>
      </article>
      <article class="metric">
        <div class="label">승인 대기</div>
        <div class="value" id="metric-approvals">-</div>
      </article>
      <article class="metric">
        <div class="label">Agent 실행</div>
        <div class="value" id="metric-runs">-</div>
      </article>
      <article class="metric">
        <div class="label">평균 지연</div>
        <div class="value" id="metric-latency">-</div>
      </article>
      <article class="metric">
        <div class="label">평균 신뢰도</div>
        <div class="value" id="metric-confidence">-</div>
      </article>
      <article class="metric">
        <div class="label">Gateway fallback</div>
        <div class="value" id="metric-fallbacks">-</div>
      </article>
    </section>

    <section class="panel-grid">
      <div class="stack">
        <section class="panel">
          <header>
            <h2>Tool Decision</h2>
            <span class="meta">runtime decision count</span>
          </header>
          <div class="panel-body">
            <div class="bars" id="tool-decisions"></div>
          </div>
        </section>

        <section class="panel">
          <header>
            <h2>Audit Events</h2>
            <span class="meta">latest 10</span>
          </header>
          <div class="panel-body table-wrap">
            <table>
              <thead>
                <tr>
                  <th>시간</th>
                  <th>이벤트</th>
                  <th>리소스</th>
                  <th>Actor</th>
                </tr>
              </thead>
              <tbody id="audit-events"></tbody>
            </table>
          </div>
        </section>
      </div>

      <div class="stack">
        <section class="panel">
          <header>
            <h2>Approval Flow</h2>
            <span class="meta">pending queue</span>
          </header>
          <div class="panel-body">
            <div id="approval-list"></div>
          </div>
        </section>

        <section class="panel">
          <header>
            <h2>Tool Catalog</h2>
            <span class="meta">registered tools</span>
          </header>
          <div class="panel-body table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Tool</th>
                  <th>Action</th>
                  <th>Scope</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody id="tool-catalog"></tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <header>
            <h2>Latest Evaluation</h2>
            <span class="meta">quality signal</span>
          </header>
          <div class="panel-body">
            <pre class="json" id="evaluation-metrics">{}</pre>
          </div>
        </section>
      </div>
    </section>
  </main>

  <script>
    const els = {
      controls: document.querySelector("#controls"),
      refresh: document.querySelector("#refresh"),
      tenant: document.querySelector("#tenant-id"),
      eventLimit: document.querySelector("#event-limit"),
      apiKey: document.querySelector("#api-key"),
      loadState: document.querySelector("#load-state"),
      generatedAt: document.querySelector("#generated-at"),
      documents: document.querySelector("#metric-documents"),
      approvals: document.querySelector("#metric-approvals"),
      runs: document.querySelector("#metric-runs"),
      latency: document.querySelector("#metric-latency"),
      confidence: document.querySelector("#metric-confidence"),
      fallbacks: document.querySelector("#metric-fallbacks"),
      toolDecisions: document.querySelector("#tool-decisions"),
      auditEvents: document.querySelector("#audit-events"),
      approvalList: document.querySelector("#approval-list"),
      toolCatalog: document.querySelector("#tool-catalog"),
      evaluationMetrics: document.querySelector("#evaluation-metrics")
    };

    function formatNumber(value) {
      return Number(value || 0).toLocaleString("ko-KR");
    }

    function formatLatency(value) {
      const rounded = Math.round(Number(value || 0));
      return `${rounded.toLocaleString("ko-KR")}ms`;
    }

    function formatRatio(value) {
      return Number(value || 0).toFixed(2);
    }

    function formatTime(value) {
      if (!value) {
        return "-";
      }
      return new Intl.DateTimeFormat("ko-KR", {
        dateStyle: "short",
        timeStyle: "medium"
      }).format(new Date(value));
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => {
        const entities = {
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;"
        };
        return entities[char];
      });
    }

    function badgeClass(value) {
      if (["allowed", "executed", "succeeded", "low", "read"].includes(value)) {
        return "ok";
      }
      if (["approval_required", "pending", "medium", "write"].includes(value)) {
        return "warn";
      }
      if (["denied", "rejected", "failed", "high"].includes(value)) {
        return "danger";
      }
      return "";
    }

    function renderBars(target, counts) {
      const entries = Object.entries(counts || {}).sort((left, right) => {
        return right[1] - left[1];
      });
      if (entries.length === 0) {
        target.innerHTML = `<div class="empty">집계된 데이터가 없습니다.</div>`;
        return;
      }
      const max = Math.max(...entries.map((entry) => entry[1]), 1);
      target.innerHTML = entries.map(([key, value]) => {
        const width = Math.max(4, Math.round((value / max) * 100));
        return `
          <div class="bar-row">
            <div class="bar-label">${escapeHtml(key)}</div>
            <div class="bar-track">
              <div class="bar-fill" style="width: ${width}%"></div>
            </div>
            <div class="bar-value">${formatNumber(value)}</div>
          </div>
        `;
      }).join("");
    }

    function renderApprovals(approvals) {
      if (!approvals.length) {
        els.approvalList.innerHTML = `<div class="empty">승인 대기 요청이 없습니다.</div>`;
        return;
      }
      els.approvalList.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Tool</th>
                <th>Status</th>
                <th>요청자</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${approvals.map((approval) => `
                <tr>
                  <td>${escapeHtml(approval.tool_name)}</td>
                  <td>
                    <span class="badge ${badgeClass(approval.status)}">
                      ${escapeHtml(approval.status)}
                    </span>
                  </td>
                  <td>${escapeHtml(approval.requested_by)}</td>
                  <td>
                    <div class="action-group">
                      <button
                        class="action-button approve"
                        type="button"
                        data-approval-action="approve"
                        data-approval-id="${escapeHtml(approval.id)}"
                      >
                        승인
                      </button>
                      <button
                        class="action-button reject"
                        type="button"
                        data-approval-action="reject"
                        data-approval-id="${escapeHtml(approval.id)}"
                      >
                        반려
                      </button>
                    </div>
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `;
    }

    function renderTools(tools) {
      els.toolCatalog.innerHTML = tools.map((tool) => `
        <tr>
          <td>${escapeHtml(tool.name)}</td>
          <td>
            <span class="badge ${badgeClass(tool.action_type)}">
              ${escapeHtml(tool.action_type)}
            </span>
          </td>
          <td>${escapeHtml(tool.required_scope || "-")}</td>
          <td>
            <span class="badge ${badgeClass(tool.risk_level)}">
              ${escapeHtml(tool.risk_level)}
            </span>
          </td>
        </tr>
      `).join("");
    }

    function renderAuditEvents(events) {
      if (!events.length) {
        els.auditEvents.innerHTML = `
          <tr>
            <td colspan="4" class="empty">감사 이벤트가 없습니다.</td>
          </tr>
        `;
        return;
      }
      els.auditEvents.innerHTML = events.map((event) => `
        <tr>
          <td>${formatTime(event.created_at)}</td>
          <td>${escapeHtml(event.event_type)}</td>
          <td>${escapeHtml(event.resource_type)}</td>
          <td>${escapeHtml(event.actor_id)}</td>
        </tr>
      `).join("");
    }

    async function fetchJson(url) {
      const response = await fetch(url, { headers: requestHeaders() });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      return response.json();
    }

    async function postJson(url, payload) {
      const response = await fetch(url, {
        method: "POST",
        headers: requestHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      return response.json();
    }

    function requestHeaders(extraHeaders = {}) {
      const headers = {
        "Accept": "application/json",
        ...extraHeaders
      };
      const apiKey = els.apiKey.value.trim();
      if (apiKey) {
        headers["X-API-Key"] = apiKey;
      }
      return headers;
    }

    async function decideApproval(approvalId, action) {
      const actor = window.prompt("처리자 ID를 입력하세요.", "operator-01");
      if (!actor) {
        return;
      }
      const tenantId = els.tenant.value || "default";
      const payload = {
        tenant_id: tenantId,
        [action === "approve" ? "approved_by" : "rejected_by"]: actor
      };
      if (action === "reject") {
        const reason = window.prompt("반려 사유를 입력하세요.", "요청 근거가 부족합니다.");
        if (!reason) {
          return;
        }
        payload.reason = reason;
      }

      els.refresh.disabled = true;
      els.loadState.className = "";
      els.loadState.textContent = action === "approve"
        ? "승인 처리 중입니다."
        : "반려 처리 중입니다.";
      try {
        await postJson(`/v1/approvals/${approvalId}/${action}`, payload);
        await refreshDashboard();
      } catch (error) {
        els.loadState.className = "error";
        els.loadState.textContent = `승인 상태 변경 실패: ${error.message}`;
      } finally {
        els.refresh.disabled = false;
      }
    }

    async function refreshDashboard() {
      const tenantId = encodeURIComponent(els.tenant.value || "default");
      const eventLimit = encodeURIComponent(els.eventLimit.value || "500");
      els.refresh.disabled = true;
      els.loadState.className = "";
      els.loadState.textContent = "데이터를 불러오는 중입니다.";

      try {
        const [summary, approvals, events, tools] = await Promise.all([
          fetchJson(`/v1/operations/summary?tenant_id=${tenantId}&event_limit=${eventLimit}`),
          fetchJson(`/v1/approvals/pending?tenant_id=${tenantId}`),
          fetchJson(`/v1/audit/events?tenant_id=${tenantId}&limit=10`),
          fetchJson("/v1/tools")
        ]);

        els.documents.textContent = formatNumber(summary.document_count);
        els.approvals.textContent = formatNumber(summary.pending_approval_count);
        els.runs.textContent = formatNumber(summary.agent_run_count);
        els.latency.textContent = formatLatency(summary.average_latency_ms);
        els.confidence.textContent = formatRatio(summary.average_confidence);
        els.fallbacks.textContent = formatNumber(summary.gateway_fallback_count);
        els.generatedAt.textContent = `Generated ${formatTime(summary.generated_at)}`;

        renderBars(els.toolDecisions, summary.tool_decision_counts);
        renderApprovals(approvals);
        renderTools(tools);
        renderAuditEvents(events);
        els.evaluationMetrics.textContent = JSON.stringify(
          summary.latest_evaluation_metrics || {},
          null,
          2
        );
        els.loadState.textContent = "운영 데이터가 갱신되었습니다.";
      } catch (error) {
        els.loadState.className = "error";
        els.loadState.textContent = `데이터 갱신 실패: ${error.message}`;
      } finally {
        els.refresh.disabled = false;
      }
    }

    els.controls.addEventListener("submit", (event) => {
      event.preventDefault();
      refreshDashboard();
    });

    els.approvalList.addEventListener("click", (event) => {
      const button = event.target.closest("[data-approval-action]");
      if (!button) {
        return;
      }
      decideApproval(button.dataset.approvalId, button.dataset.approvalAction);
    });

    refreshDashboard();
  </script>
</body>
</html>
"""
