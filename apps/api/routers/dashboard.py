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
    input,
    select {
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

    .field input,
    .field select,
    .field textarea {
      height: 38px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0 10px;
      background: var(--surface);
      color: var(--text);
    }

    .field textarea {
      min-height: 76px;
      padding: 9px 10px;
      resize: vertical;
      line-height: 1.45;
      font: inherit;
    }

    .field.full {
      min-width: 0;
      width: 100%;
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

    .action-button.compact {
      min-width: 34px;
      padding: 0 7px;
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

    tr.selected-row td {
      background: #f2fbfa;
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

    .alert-list {
      display: grid;
      gap: 8px;
    }

    .dependency-list {
      display: grid;
      gap: 8px;
    }

    .dependency-item {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 6px 10px;
      align-items: center;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 10px;
      background: #fbfcfd;
    }

    .dependency-name {
      font-size: 13px;
      font-weight: 650;
      overflow-wrap: anywhere;
    }

    .dependency-detail {
      grid-column: 1 / -1;
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }

    .alert-item {
      display: grid;
      gap: 6px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 10px;
      background: #fbfcfd;
    }

    .alert-line {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-width: 0;
    }

    .alert-message {
      font-size: 13px;
      font-weight: 650;
      overflow-wrap: anywhere;
    }

    .alert-metric {
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }

    .timeline-list {
      display: grid;
      gap: 8px;
    }

    .timeline-item {
      display: grid;
      gap: 5px;
      border-left: 3px solid var(--accent);
      background: #fbfcfd;
      padding: 8px 10px;
    }

    .timeline-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-width: 0;
    }

    .timeline-title {
      font-size: 13px;
      font-weight: 650;
      overflow-wrap: anywhere;
    }

    .timeline-detail {
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }

    .feedback-form {
      display: grid;
      gap: 10px;
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--border);
    }

    .feedback-header,
    .feedback-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      font-size: 12px;
    }

    .feedback-header span:first-child {
      color: var(--text);
      font-size: 13px;
      font-weight: 650;
    }

    .feedback-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
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

      .feedback-grid {
        grid-template-columns: 1fr;
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
          <label for="audit-request-id">Request ID</label>
          <input id="audit-request-id" name="auditRequestId" autocomplete="off">
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
      <article class="metric">
        <div class="label">Gateway circuit</div>
        <div class="value" id="metric-circuit-open">-</div>
      </article>
      <article class="metric">
        <div class="label">월간 사용률</div>
        <div class="value" id="metric-usage">-</div>
      </article>
      <article class="metric">
        <div class="label">SLO 상태</div>
        <div class="value" id="metric-slo">-</div>
      </article>
      <article class="metric">
        <div class="label">Readiness</div>
        <div class="value" id="metric-readiness">-</div>
      </article>
      <article class="metric">
        <div class="label">Schema</div>
        <div class="value" id="metric-migrations">-</div>
      </article>
    </section>

    <section class="panel-grid">
      <div class="stack">
        <section class="panel">
          <header>
            <h2>Operations Alerts</h2>
            <span class="meta">threshold signals</span>
          </header>
          <div class="panel-body">
            <div class="alert-list" id="operations-alerts"></div>
          </div>
        </section>

        <section class="panel">
          <header>
            <h2>Incident Snapshot</h2>
            <span class="meta">root signals · actions</span>
          </header>
          <div class="panel-body">
            <div id="incident-snapshot"></div>
          </div>
        </section>

        <section class="panel">
          <header>
            <h2>Agent Run Preview</h2>
            <span class="meta">dry-run plan</span>
          </header>
          <div class="panel-body">
            <form class="stack" id="preview-form">
              <div class="field full">
                <label for="preview-message">Message</label>
                <textarea id="preview-message" name="message">
운영 보고서 생성 workflow를 실행해줘.
                </textarea>
              </div>
              <button class="refresh" id="preview-submit" type="submit">Preview</button>
            </form>
            <pre class="json" id="preview-result">{}</pre>
          </div>
        </section>

        <section class="panel">
          <header>
            <h2>Feedback Summary</h2>
            <span class="meta">human review signal</span>
          </header>
          <div class="panel-body">
            <div id="feedback-summary"></div>
          </div>
        </section>

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
                  <th>Request</th>
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
            <h2>Dependency Readiness</h2>
            <span class="meta">runtime dependencies</span>
          </header>
          <div class="panel-body">
            <div class="dependency-list" id="dependency-readiness"></div>
          </div>
        </section>

        <section class="panel">
          <header>
            <h2>Schema Migrations</h2>
            <span class="meta">database ledger</span>
          </header>
          <div class="panel-body">
            <div class="dependency-list" id="migration-status"></div>
          </div>
        </section>

        <section class="panel">
          <header>
            <h2>Recent Agent Runs</h2>
            <div class="action-group">
              <span class="meta">latest 8</span>
              <button class="action-button compact" id="export-runs-jsonl" type="button">
                JSONL
              </button>
              <button class="action-button compact" id="export-runs-csv" type="button">
                CSV
              </button>
            </div>
          </header>
          <div class="panel-body table-wrap">
            <table>
              <thead>
                <tr>
                  <th>시간</th>
                  <th>Status</th>
                  <th>Type</th>
                  <th>Query</th>
                  <th>Confidence</th>
                  <th>Timeline</th>
                </tr>
              </thead>
              <tbody id="agent-runs"></tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <header>
            <h2>Agent Run Timeline</h2>
            <span class="meta">diagnostics · trace · tool · audit</span>
          </header>
          <div class="panel-body">
            <div id="agent-run-diagnostics"></div>
            <div class="timeline-list" id="agent-run-timeline"></div>
            <form class="feedback-form" id="agent-feedback-form">
              <div class="feedback-header">
                <span>선택 실행 평가</span>
                <span id="selected-run-label">-</span>
              </div>
              <div class="feedback-grid">
                <div class="field">
                  <label for="feedback-rating">Rating</label>
                  <select id="feedback-rating" name="rating">
                    <option value="5">5 · accepted</option>
                    <option value="4">4 · useful</option>
                    <option value="3">3 · neutral</option>
                    <option value="2">2 · weak</option>
                    <option value="1">1 · rejected</option>
                  </select>
                </div>
                <div class="field">
                  <label for="feedback-outcome">Outcome</label>
                  <input id="feedback-outcome" name="outcome" value="accepted">
                </div>
                <div class="field">
                  <label for="feedback-submitted-by">Reviewer</label>
                  <input id="feedback-submitted-by" name="submittedBy" value="operator-01">
                </div>
              </div>
              <div class="field full">
                <label for="feedback-comment">Comment</label>
                <textarea id="feedback-comment" name="comment">
근거와 답변 구조가 충분합니다.
                </textarea>
              </div>
              <div class="field full">
                <label for="feedback-tags">Tags</label>
                <input id="feedback-tags" name="tags" value="grounded,useful">
              </div>
              <div class="feedback-actions">
                <button class="refresh" id="feedback-submit" type="submit">Feedback 저장</button>
                <span id="feedback-state"></span>
              </div>
            </form>
          </div>
        </section>

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
            <h2>Gateway Circuits</h2>
            <span class="meta">tool gateway state</span>
          </header>
          <div class="panel-body">
            <div class="dependency-list" id="gateway-circuits"></div>
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
      auditRequestId: document.querySelector("#audit-request-id"),
      apiKey: document.querySelector("#api-key"),
      previewForm: document.querySelector("#preview-form"),
      previewMessage: document.querySelector("#preview-message"),
      previewSubmit: document.querySelector("#preview-submit"),
      previewResult: document.querySelector("#preview-result"),
      feedbackForm: document.querySelector("#agent-feedback-form"),
      feedbackRating: document.querySelector("#feedback-rating"),
      feedbackOutcome: document.querySelector("#feedback-outcome"),
      feedbackSubmittedBy: document.querySelector("#feedback-submitted-by"),
      feedbackComment: document.querySelector("#feedback-comment"),
      feedbackTags: document.querySelector("#feedback-tags"),
      feedbackSubmit: document.querySelector("#feedback-submit"),
      feedbackState: document.querySelector("#feedback-state"),
      selectedRunLabel: document.querySelector("#selected-run-label"),
      exportRunsJsonl: document.querySelector("#export-runs-jsonl"),
      exportRunsCsv: document.querySelector("#export-runs-csv"),
      loadState: document.querySelector("#load-state"),
      generatedAt: document.querySelector("#generated-at"),
      documents: document.querySelector("#metric-documents"),
      approvals: document.querySelector("#metric-approvals"),
      runs: document.querySelector("#metric-runs"),
      latency: document.querySelector("#metric-latency"),
      confidence: document.querySelector("#metric-confidence"),
      fallbacks: document.querySelector("#metric-fallbacks"),
      circuitOpen: document.querySelector("#metric-circuit-open"),
      usage: document.querySelector("#metric-usage"),
      slo: document.querySelector("#metric-slo"),
      readiness: document.querySelector("#metric-readiness"),
      migrations: document.querySelector("#metric-migrations"),
      dependencyReadiness: document.querySelector("#dependency-readiness"),
      migrationStatus: document.querySelector("#migration-status"),
      operationsAlerts: document.querySelector("#operations-alerts"),
      incidentSnapshot: document.querySelector("#incident-snapshot"),
      feedbackSummary: document.querySelector("#feedback-summary"),
      toolDecisions: document.querySelector("#tool-decisions"),
      agentRuns: document.querySelector("#agent-runs"),
      agentDiagnostics: document.querySelector("#agent-run-diagnostics"),
      agentTimeline: document.querySelector("#agent-run-timeline"),
      auditEvents: document.querySelector("#audit-events"),
      approvalList: document.querySelector("#approval-list"),
      gatewayCircuits: document.querySelector("#gateway-circuits"),
      toolCatalog: document.querySelector("#tool-catalog"),
      evaluationMetrics: document.querySelector("#evaluation-metrics")
    };
    let selectedRunId = "";
    let latestAgentRuns = [];

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
      if (
        [
          "allowed",
          "executed",
          "succeeded",
          "low",
          "read",
          "ready",
          "applied",
          "up_to_date",
          "not_applicable",
          "closed",
          "healthy"
        ].includes(value)
      ) {
        return "ok";
      }
      if (
        [
          "approval_required",
          "pending",
          "medium",
          "write",
          "warning",
          "blocked",
          "degraded",
          "untracked",
          "not_tracked",
          "half_open"
        ]
          .includes(value)
      ) {
        return "warn";
      }
      if (
        [
          "denied",
          "rejected",
          "failed",
          "high",
          "critical",
          "unavailable",
          "checksum_mismatch",
          "open"
        ].includes(value)
      ) {
        return "danger";
      }
      return "";
    }

    function renderReadiness(readiness) {
      const dependencies = readiness.dependencies || [];
      els.readiness.textContent = escapeHtml(readiness.status || "-");
      els.readiness.title = [
        `env ${readiness.environment || "-"}`,
        `storage ${readiness.storage_backend || "-"}`,
        `vector ${readiness.vector_backend || "-"}`
      ].join(" · ");

      if (!dependencies.length) {
        els.dependencyReadiness.innerHTML = `
          <div class="empty">dependency 상태가 없습니다.</div>
        `;
        return;
      }

      els.dependencyReadiness.innerHTML = dependencies.map((dependency) => {
        const detail = Object.entries(dependency.detail || {})
          .map(([key, value]) => `${key}: ${value}`)
          .join(" · ");
        return `
          <div class="dependency-item">
            <span class="dependency-name">${escapeHtml(dependency.name)}</span>
            <span class="badge ${badgeClass(dependency.status)}">
              ${escapeHtml(dependency.status)}
            </span>
            <div class="dependency-detail">
              ${formatNumber(dependency.latency_ms)}ms${detail ? ` · ${escapeHtml(detail)}` : ""}
            </div>
          </div>
        `;
      }).join("");
    }

    function renderMigrations(status) {
      const migrations = status.migrations || [];
      els.migrations.textContent = escapeHtml(status.status || "-");
      els.migrations.title = [
        `backend ${status.storage_backend || "-"}`,
        `ledger ${status.ledger_available ? "available" : "missing"}`
      ].join(" · ");

      if (!migrations.length) {
        els.migrationStatus.innerHTML = `
          <div class="empty">migration 파일이 없습니다.</div>
        `;
        return;
      }

      els.migrationStatus.innerHTML = migrations.map((migration) => {
        const checksum = String(migration.checksum || "").slice(0, 12);
        const appliedChecksum = migration.applied_checksum
          ? String(migration.applied_checksum).slice(0, 12)
          : "-";
        const appliedAt = migration.applied_at ? formatTime(migration.applied_at) : "-";
        return `
          <div class="dependency-item">
            <span class="dependency-name">
              ${escapeHtml(migration.version)} · ${escapeHtml(migration.filename)}
            </span>
            <span class="badge ${badgeClass(migration.status)}">
              ${escapeHtml(migration.status)}
            </span>
            <div class="dependency-detail">
              file ${escapeHtml(checksum)}
              · db ${escapeHtml(appliedChecksum)}
              · ${escapeHtml(appliedAt)}
            </div>
          </div>
        `;
      }).join("");
    }

    function renderOperationsAlerts(alerts) {
      if (!alerts.length) {
        els.operationsAlerts.innerHTML = `<div class="empty">활성 alert가 없습니다.</div>`;
        return;
      }
      els.operationsAlerts.innerHTML = alerts.map((alert) => `
        <div class="alert-item">
          <div class="alert-line">
            <span class="alert-message">${escapeHtml(alert.message)}</span>
            <span class="badge ${badgeClass(alert.severity)}">
              ${escapeHtml(alert.severity)}
            </span>
          </div>
          <div class="alert-metric">
            ${escapeHtml(alert.metric)}:
            ${escapeHtml(alert.actual_value)} / ${escapeHtml(alert.threshold)}
          </div>
        </div>
      `).join("");
    }

    function renderIncidentSnapshot(snapshot) {
      const causes = snapshot.suspected_causes || [];
      const actions = snapshot.recommended_actions || [];
      els.incidentSnapshot.innerHTML = `
        <div class="alert-item">
          <div class="alert-line">
            <span class="alert-message">${escapeHtml(snapshot.summary)}</span>
            <span class="badge ${badgeClass(snapshot.severity)}">
              ${escapeHtml(snapshot.severity)}
            </span>
          </div>
          <div class="alert-metric">
            ${escapeHtml(snapshot.status)}
            · alerts ${formatNumber(snapshot.active_alert_count)}
          </div>
        </div>
        <div class="timeline-list">
          ${causes.slice(0, 3).map((cause) => `
            <div class="timeline-item">
              <div class="timeline-title">${escapeHtml(cause)}</div>
            </div>
          `).join("")}
          ${actions.slice(0, 3).map((action) => `
            <div class="timeline-item">
              <div class="timeline-detail">${escapeHtml(action)}</div>
            </div>
          `).join("")}
        </div>
      `;
    }

    function renderFeedbackSummary(summary) {
      els.feedbackSummary.innerHTML = `
        <div class="alert-item">
          <div class="alert-line">
            <span class="alert-message">
              평균 rating ${formatRatio(summary.average_rating)}
            </span>
            <span class="badge ${summary.negative_count > 0 ? "warn" : "ok"}">
              ${formatNumber(summary.feedback_count)}
            </span>
          </div>
          <div class="alert-metric">
            positive ${formatNumber(summary.positive_count)}
            · negative ${formatNumber(summary.negative_count)}
          </div>
        </div>
        <div class="bars">
          ${Object.entries(summary.outcome_counts || {}).map(([key, value]) => `
            <div class="bar-row">
              <div class="bar-label">${escapeHtml(key)}</div>
              <div class="bar-track">
                <div class="bar-fill" style="width: ${Math.max(8, value * 20)}%"></div>
              </div>
              <div class="bar-value">${formatNumber(value)}</div>
            </div>
          `).join("") || `<div class="empty">feedback 데이터가 없습니다.</div>`}
        </div>
      `;
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

    function renderGatewayCircuits(statuses) {
      if (!statuses.length) {
        els.gatewayCircuits.innerHTML = `
          <div class="empty">gateway circuit 상태가 없습니다.</div>
        `;
        return;
      }

      els.gatewayCircuits.innerHTML = statuses.map((status) => {
        const remaining = Math.round(Number(status.open_remaining_ms || 0));
        return `
          <div class="dependency-item">
            <span class="dependency-name">${escapeHtml(status.tool_name)}</span>
            <span class="badge ${badgeClass(status.state)}">
              ${escapeHtml(status.state)}
            </span>
            <div class="dependency-detail">
              failures ${formatNumber(status.failure_streak)}
              / ${formatNumber(status.failure_threshold)}
              · open ${formatNumber(remaining)}ms
            </div>
          </div>
        `;
      }).join("");
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

    function renderAgentRuns(runs) {
      latestAgentRuns = runs;
      if (!runs.length) {
        els.agentRuns.innerHTML = `
          <tr>
            <td colspan="6" class="empty">Agent 실행 이력이 없습니다.</td>
          </tr>
        `;
        return;
      }
      els.agentRuns.innerHTML = runs.map((run) => `
        <tr class="${run.run_id === selectedRunId ? "selected-row" : ""}">
          <td>${formatTime(run.created_at)}</td>
          <td>
            <span class="badge ${badgeClass(run.status)}">
              ${escapeHtml(run.status)}
            </span>
          </td>
          <td>${escapeHtml(run.query_type)}</td>
          <td>${escapeHtml(run.redacted_query_preview)}</td>
          <td>${formatRatio(run.confidence)}</td>
          <td>
            <div class="action-group">
              <button
                class="action-button compact"
                type="button"
                data-run-action="view"
                data-run-id="${escapeHtml(run.run_id)}"
              >
                보기
              </button>
              <button
                class="action-button compact"
                type="button"
                data-run-action="replay"
                data-run-id="${escapeHtml(run.run_id)}"
              >
                Replay
              </button>
            </div>
          </td>
        </tr>
      `).join("");
    }

    function renderSelectedRunLabel() {
      if (!selectedRunId) {
        els.selectedRunLabel.textContent = "-";
        els.feedbackSubmit.disabled = true;
        return;
      }
      els.selectedRunLabel.textContent = selectedRunId.slice(0, 8);
      els.feedbackSubmit.disabled = false;
    }

    function renderAgentTimeline(items) {
      if (!items.length) {
        els.agentTimeline.innerHTML = `<div class="empty">선택된 실행 timeline이 없습니다.</div>`;
        return;
      }
      els.agentTimeline.innerHTML = items.map((item) => `
        <div class="timeline-item">
          <div class="timeline-head">
            <span class="timeline-title">${escapeHtml(item.title)}</span>
            <span class="badge ${badgeClass(item.status)}">
              ${escapeHtml(item.source)}
            </span>
          </div>
          <div class="timeline-detail">
            ${escapeHtml(item.event_type)}
            · ${escapeHtml(item.status)}
            · ${formatTime(item.occurred_at)}
          </div>
        </div>
      `).join("");
    }

    function renderAgentDiagnostics(diagnostics) {
      if (!diagnostics) {
        els.agentDiagnostics.innerHTML = `
          <div class="empty">선택된 실행 diagnostics가 없습니다.</div>
        `;
        return;
      }
      const signals = diagnostics.signals || [];
      const actions = diagnostics.recommended_actions || [];
      els.agentDiagnostics.innerHTML = `
        <div class="alert-item">
          <div class="alert-line">
            <span class="alert-message">
              Quality ${formatRatio(diagnostics.quality_score)}
            </span>
            <span class="badge ${badgeClass(diagnostics.severity)}">
              ${escapeHtml(diagnostics.severity)}
            </span>
          </div>
          <div class="alert-metric">
            ${escapeHtml(diagnostics.status)}
            · confidence ${formatRatio(diagnostics.metrics?.confidence)}
            · citations ${formatNumber(diagnostics.metrics?.citation_count)}
            · feedback ${formatNumber(diagnostics.metrics?.feedback_count)}
          </div>
        </div>
        <div class="timeline-list">
          ${signals.slice(0, 4).map((signal) => `
            <div class="timeline-item">
              <div class="timeline-head">
                <span class="timeline-title">${escapeHtml(signal.code)}</span>
                <span class="badge ${badgeClass(signal.severity)}">
                  ${escapeHtml(signal.severity)}
                </span>
              </div>
              <div class="timeline-detail">${escapeHtml(signal.message)}</div>
            </div>
          `).join("") || `<div class="empty">활성 diagnostic signal이 없습니다.</div>`}
          ${actions.slice(0, 2).map((action) => `
            <div class="timeline-item">
              <div class="timeline-detail">${escapeHtml(action)}</div>
            </div>
          `).join("")}
        </div>
      `;
    }

    function renderAuditEvents(events) {
      if (!events.length) {
        els.auditEvents.innerHTML = `
          <tr>
            <td colspan="5" class="empty">감사 이벤트가 없습니다.</td>
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
          <td>${escapeHtml(event.payload?.request_id || "-")}</td>
        </tr>
      `).join("");
    }

    function buildAuditEventsUrl() {
      const params = new URLSearchParams({
        tenant_id: els.tenant.value || "default",
        limit: "10"
      });
      const requestId = els.auditRequestId.value.trim();
      if (requestId) {
        params.set("request_id", requestId);
      }
      return `/v1/audit/events?${params.toString()}`;
    }

    async function fetchJson(url) {
      const response = await fetch(url, { headers: requestHeaders() });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      return response.json();
    }

    async function fetchReadiness() {
      const response = await fetch("/v1/readiness", { headers: requestHeaders() });
      if (!response.ok && response.status !== 503) {
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

    async function previewAgentRun() {
      const tenantId = els.tenant.value || "default";
      const message = els.previewMessage.value.trim();
      if (!message) {
        els.previewResult.textContent = JSON.stringify({ error: "message is empty" }, null, 2);
        return;
      }
      els.previewSubmit.disabled = true;
      try {
        const preview = await postJson("/v1/agents/runs/preview", {
          tenant_id: tenantId,
          scenario: "operations",
          message,
          actor_scopes: ["records:read", "workflow:request"]
        });
        els.previewResult.textContent = JSON.stringify(preview, null, 2);
      } catch (error) {
        els.previewResult.textContent = JSON.stringify({ error: error.message }, null, 2);
      } finally {
        els.previewSubmit.disabled = false;
      }
    }

    async function submitAgentFeedback() {
      if (!selectedRunId) {
        els.feedbackState.className = "error";
        els.feedbackState.textContent = "선택된 실행 이력이 없습니다.";
        return;
      }
      const tenantId = els.tenant.value || "default";
      const tags = els.feedbackTags.value
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean);
      els.feedbackSubmit.disabled = true;
      els.feedbackState.className = "";
      els.feedbackState.textContent = "저장 중입니다.";
      try {
        await postJson(`/v1/agents/runs/${selectedRunId}/feedback`, {
          tenant_id: tenantId,
          rating: Number(els.feedbackRating.value),
          outcome: els.feedbackOutcome.value.trim() || "reviewed",
          submitted_by: els.feedbackSubmittedBy.value.trim() || "operator-01",
          comment: els.feedbackComment.value.trim() || null,
          tags
        });
        els.feedbackState.textContent = "저장되었습니다.";
        await refreshDashboard();
      } catch (error) {
        els.feedbackState.className = "error";
        els.feedbackState.textContent = `저장 실패: ${error.message}`;
      } finally {
        renderSelectedRunLabel();
      }
    }

    async function replayAgentRun(runId) {
      if (!runId) {
        return;
      }
      const tenantId = els.tenant.value || "default";
      els.loadState.className = "";
      els.loadState.textContent = "Agent run을 재실행하는 중입니다.";
      try {
        const replay = await postJson(
          `/v1/agents/runs/${encodeURIComponent(runId)}/replay`,
          {
            tenant_id: tenantId,
            user_id: els.feedbackSubmittedBy.value.trim() || "operator-01",
            actor_scopes: ["records:read", "workflow:request"]
          }
        );
        selectedRunId = replay.replayed_run.run_id;
        els.loadState.textContent = [
          "Replay 완료",
          `quality delta ${formatRatio(replay.diff.quality_score_delta)}`,
          `confidence delta ${formatRatio(replay.diff.confidence_delta)}`
        ].join(" · ");
        await refreshDashboard();
      } catch (error) {
        els.loadState.className = "error";
        els.loadState.textContent = `Replay 실패: ${error.message}`;
      }
    }

    async function exportAgentRuns(format) {
      const tenantId = encodeURIComponent(els.tenant.value || "default");
      const eventLimit = encodeURIComponent(els.eventLimit.value || "500");
      const extension = format === "csv" ? "csv" : "jsonl";
      els.loadState.className = "";
      els.loadState.textContent = `Agent run ${extension.toUpperCase()} export 생성 중입니다.`;
      try {
        const response = await fetch(
          `/v1/agents/runs/export?tenant_id=${tenantId}&limit=${eventLimit}&format=${format}`,
          { headers: requestHeaders() }
        );
        if (!response.ok) {
          throw new Error(`${response.status} ${response.statusText}`);
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `agent-runs.${extension}`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
        els.loadState.textContent = `Agent run ${extension.toUpperCase()} export가 생성되었습니다.`;
      } catch (error) {
        els.loadState.className = "error";
        els.loadState.textContent = `Agent run export 실패: ${error.message}`;
      }
    }

    async function loadAgentTimeline(runId) {
      if (!runId) {
        renderAgentTimeline([]);
        renderAgentDiagnostics(null);
        renderSelectedRunLabel();
        return;
      }
      const tenantId = encodeURIComponent(els.tenant.value || "default");
      try {
        const encodedRunId = encodeURIComponent(runId);
        const [timeline, diagnostics] = await Promise.all([
          fetchJson(`/v1/agents/runs/${encodedRunId}/timeline?tenant_id=${tenantId}`),
          fetchJson(`/v1/agents/runs/${encodedRunId}/diagnostics?tenant_id=${tenantId}`)
        ]);
        renderAgentTimeline(timeline);
        renderAgentDiagnostics(diagnostics);
        renderSelectedRunLabel();
      } catch (error) {
        els.agentDiagnostics.innerHTML = `
          <div class="empty">Diagnostics 조회 실패: ${escapeHtml(error.message)}</div>
        `;
        els.agentTimeline.innerHTML = `
          <div class="empty">Timeline 조회 실패: ${escapeHtml(error.message)}</div>
        `;
        renderSelectedRunLabel();
      }
    }

    async function refreshDashboard() {
      const tenantId = encodeURIComponent(els.tenant.value || "default");
      const eventLimit = encodeURIComponent(els.eventLimit.value || "500");
      els.refresh.disabled = true;
      els.loadState.className = "";
      els.loadState.textContent = "데이터를 불러오는 중입니다.";

      try {
        const [
          readiness,
          migrations,
          summary,
          usage,
          slo,
          incident,
          feedback,
          alerts,
          runs,
          approvals,
          events,
          gatewayCircuits,
          tools
        ] = await Promise.all([
          fetchReadiness(),
          fetchJson("/v1/operations/migrations/status"),
          fetchJson(`/v1/operations/summary?tenant_id=${tenantId}&event_limit=${eventLimit}`),
          fetchJson(`/v1/operations/usage?tenant_id=${tenantId}`),
          fetchJson(`/v1/operations/slo?tenant_id=${tenantId}&event_limit=${eventLimit}`),
          fetchJson(
            `/v1/operations/incidents/snapshot?tenant_id=${tenantId}&event_limit=${eventLimit}`
          ),
          fetchJson(`/v1/operations/feedback/summary?tenant_id=${tenantId}`),
          fetchJson(`/v1/operations/alerts?tenant_id=${tenantId}&event_limit=${eventLimit}`),
          fetchJson(`/v1/agents/runs?tenant_id=${tenantId}&limit=8`),
          fetchJson(`/v1/approvals/pending?tenant_id=${tenantId}`),
          fetchJson(buildAuditEventsUrl()),
          fetchJson("/v1/tools/gateway/status"),
          fetchJson("/v1/tools")
        ]);

        els.documents.textContent = formatNumber(summary.document_count);
        els.approvals.textContent = formatNumber(summary.pending_approval_count);
        els.runs.textContent = formatNumber(summary.agent_run_count);
        els.latency.textContent = formatLatency(summary.average_latency_ms);
        els.confidence.textContent = formatRatio(summary.average_confidence);
        els.fallbacks.textContent = formatNumber(summary.gateway_fallback_count);
        els.circuitOpen.textContent = formatNumber(summary.gateway_circuit_open_count);
        els.usage.textContent = `${Math.round(Number(usage.usage_ratio || 0) * 100)}%`;
        els.usage.title = [
          formatNumber(usage.agent_runs_used),
          formatNumber(usage.monthly_agent_run_quota)
        ].join(" / ");
        els.slo.textContent = escapeHtml(slo.status);
        els.slo.title = [
          `success ${formatRatio(slo.success_rate)}`,
          `p95 ${formatLatency(slo.p95_latency_ms)}`
        ].join(" · ");
        els.generatedAt.textContent = `Generated ${formatTime(summary.generated_at)}`;

        renderReadiness(readiness);
        renderMigrations(migrations);
        if (!runs.some((run) => run.run_id === selectedRunId)) {
          selectedRunId = runs.length ? runs[0].run_id : "";
        }
        renderOperationsAlerts(alerts);
        renderIncidentSnapshot(incident);
        renderFeedbackSummary(feedback);
        renderAgentRuns(runs);
        await loadAgentTimeline(selectedRunId);
        renderBars(els.toolDecisions, summary.tool_decision_counts);
        renderApprovals(approvals);
        renderGatewayCircuits(gatewayCircuits);
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

    els.previewForm.addEventListener("submit", (event) => {
      event.preventDefault();
      previewAgentRun();
    });

    els.feedbackForm.addEventListener("submit", (event) => {
      event.preventDefault();
      submitAgentFeedback();
    });

    els.exportRunsJsonl.addEventListener("click", () => {
      exportAgentRuns("jsonl");
    });

    els.exportRunsCsv.addEventListener("click", () => {
      exportAgentRuns("csv");
    });

    els.approvalList.addEventListener("click", (event) => {
      const button = event.target.closest("[data-approval-action]");
      if (!button) {
        return;
      }
      decideApproval(button.dataset.approvalId, button.dataset.approvalAction);
    });

    els.agentRuns.addEventListener("click", (event) => {
      const button = event.target.closest("[data-run-id]");
      if (!button) {
        return;
      }
      selectedRunId = button.dataset.runId;
      if (button.dataset.runAction === "replay") {
        replayAgentRun(selectedRunId);
        return;
      }
      renderAgentRuns(latestAgentRuns);
      loadAgentTimeline(selectedRunId);
    });

    refreshDashboard();
  </script>
</body>
</html>
"""
