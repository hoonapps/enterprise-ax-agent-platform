import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from apps.api.adapters.persistence.in_memory import (
    InMemoryWebhookDeliveryRepository,
    InMemoryWebhookSubscriptionRepository,
)
from apps.api.application.webhooks import WebhookDispatcher
from apps.api.core.config import get_settings
from apps.api.core.container import get_container
from apps.api.core.security import parse_api_key_credentials
from apps.api.domain.models import (
    AuditEvent,
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookHttpResult,
    WebhookSubscription,
)
from apps.api.main import create_app


class FakeWebhookHttpClient:
    def __init__(self, result: WebhookHttpResult) -> None:
        self.result = result
        self.requests: list[dict[str, object]] = []

    def post_json(
        self,
        *,
        url: str,
        payload: dict[str, object],
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> WebhookHttpResult:
        self.requests.append(
            {
                "url": url,
                "payload": payload,
                "headers": headers,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.result


def _clear_runtime_caches() -> None:
    get_settings.cache_clear()
    get_container.cache_clear()
    parse_api_key_credentials.cache_clear()


def test_request_context_headers_echo_request_id():
    client = TestClient(create_app())

    response = client.get("/health", headers={"X-Request-ID": "request-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-123"
    assert float(response.headers["X-Process-Time-Ms"]) >= 0


def test_request_context_headers_generate_request_id():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    UUID(response.headers["X-Request-ID"])
    assert float(response.headers["X-Process-Time-Ms"]) >= 0


def test_http_error_response_includes_request_id_without_changing_detail():
    client = TestClient(create_app())
    run_id = uuid4()

    response = client.get(
        f"/v1/agents/runs/{run_id}",
        headers={"X-Request-ID": "error-trace-001"},
    )

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "error-trace-001"
    assert response.json()["detail"] == "Agent 실행 이력을 찾을 수 없습니다."
    assert response.json()["request_id"] == "error-trace-001"


def test_validation_error_response_includes_request_id():
    client = TestClient(create_app())

    response = client.post(
        "/v1/documents/ingest",
        headers={"X-Request-ID": "validation-trace-001"},
        json={
            "tenant_id": "default",
            "title": "짧은 문서",
            "content": "too short",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert response.headers["X-Request-ID"] == "validation-trace-001"
    assert body["request_id"] == "validation-trace-001"
    assert isinstance(body["detail"], list)


def test_audit_events_include_request_id_from_http_context():
    client = TestClient(create_app())

    ingest = client.post(
        "/v1/documents/ingest",
        headers={"X-Request-ID": "audit-trace-001"},
        json={
            "tenant_id": "default",
            "title": "Request context 문서",
            "content": "감사 이벤트는 HTTP request id와 연결되어야 한다.",
            "source_uri": "test://request-context",
        },
    )
    assert ingest.status_code == 200

    events = client.get("/v1/audit/events?tenant_id=default&event_type=document.ingested")

    assert events.status_code == 200
    assert events.json()[0]["payload"]["request_id"] == "audit-trace-001"


def test_audit_events_can_filter_and_export_by_request_id():
    client = TestClient(create_app())
    tenant_id = "request-filter"

    first = client.post(
        "/v1/documents/ingest",
        headers={"X-Request-ID": "request-filter-001"},
        json={
            "tenant_id": tenant_id,
            "title": "Request filter A",
            "content": "request id 필터 테스트를 위한 첫 번째 감사 이벤트 문서입니다.",
            "source_uri": "test://request-filter-a",
        },
    )
    second = client.post(
        "/v1/documents/ingest",
        headers={"X-Request-ID": "request-filter-002"},
        json={
            "tenant_id": tenant_id,
            "title": "Request filter B",
            "content": "request id 필터 테스트를 위한 두 번째 감사 이벤트 문서입니다.",
            "source_uri": "test://request-filter-b",
        },
    )
    assert first.status_code == 200
    assert second.status_code == 200

    events = client.get(
        "/v1/audit/events",
        params={
            "tenant_id": tenant_id,
            "event_type": "document.ingested",
            "request_id": "request-filter-001",
        },
    )
    exported = client.get(
        "/v1/audit/export",
        params={"tenant_id": tenant_id, "format": "jsonl", "request_id": "request-filter-001"},
    )

    assert events.status_code == 200
    body = events.json()
    assert len(body) == 1
    assert body[0]["payload"]["request_id"] == "request-filter-001"
    assert exported.status_code == 200
    exported_lines = [json.loads(line) for line in exported.text.splitlines() if line]
    assert len(exported_lines) == 1
    assert exported_lines[0]["payload"]["request_id"] == "request-filter-001"


def test_health_and_agent_flow():
    client = TestClient(create_app())

    tools = client.get("/v1/tools")
    assert tools.status_code == 200
    assert {tool["name"] for tool in tools.json()} >= {
        "internal-records.lookup",
        "workflow.request-change",
    }

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ingest = client.post(
        "/v1/documents/ingest",
        json={
            "tenant_id": "default",
            "title": "Agentic RAG 운영 모델",
            "content": (
                "Agentic RAG는 질문 유형을 분류하고 검색 전략을 선택한다. "
                "리스크 질문은 보안과 감사로그를 함께 봐야 한다."
            ),
            "source_uri": "test://agentic-rag",
        },
    )
    assert ingest.status_code == 200
    assert ingest.json()["chunk_count"] == 1

    run = client.post(
        "/v1/agents/runs",
        json={
            "tenant_id": "default",
            "scenario": "operations",
            "message": "Agentic RAG 리스크를 정리해줘",
        },
    )
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "succeeded"
    assert body["citations"]
    assert body["trace"]
    assert body["tool_executions"] == []


def test_agent_run_preview_does_not_persist_run_or_audit_event():
    client = TestClient(create_app())
    tenant_id = "run-preview"

    response = client.post(
        "/v1/agents/runs/preview",
        json={
            "tenant_id": tenant_id,
            "scenario": "operations",
            "message": "운영 보고서 생성 workflow를 실행해줘. 연락처는 010-1234-5678",
            "actor_scopes": ["workflow:request"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query_type"] == "action"
    assert body["redaction_count"] == 1
    assert "[REDACTED_PHONE]" in body["redacted_query"]
    assert body["retrieval_strategy"] == "action-grounding"
    assert body["quota_allowed"] is True
    assert body["tool_name"] == "workflow.request-change"
    assert body["tool_action_type"] == "write"
    assert body["tool_risk_level"] == "high"

    runs = client.get(f"/v1/agents/runs?tenant_id={tenant_id}")
    events = client.get(f"/v1/audit/events?tenant_id={tenant_id}")
    assert runs.status_code == 200
    assert events.status_code == 200
    assert runs.json() == []
    assert events.json() == []


def test_agent_run_history_lists_recent_runs_with_filters():
    client = TestClient(create_app())
    tenant_id = "run-history"

    client.post(
        "/v1/documents/ingest",
        json={
            "tenant_id": tenant_id,
            "title": "실행 이력 정책",
            "content": (
                "Agent 실행 이력은 상태, 질문 유형, 신뢰도, trace 개수를 "
                "확인할 수 있어야 한다."
            ),
            "source_uri": "test://run-history",
        },
    )
    succeeded = client.post(
        "/v1/agents/runs",
        json={
            "tenant_id": tenant_id,
            "scenario": "operations",
            "message": "실행 이력 정책을 정리해줘",
        },
    )
    blocked = client.post(
        "/v1/agents/runs",
        json={
            "tenant_id": tenant_id,
            "scenario": "finance-ops",
            "message": "고객 계좌로 100만원 송금 실행해줘",
        },
    )
    assert succeeded.status_code == 200
    assert blocked.status_code == 200

    listed = client.get(f"/v1/agents/runs?tenant_id={tenant_id}&limit=10")
    blocked_only = client.get(f"/v1/agents/runs?tenant_id={tenant_id}&status=blocked")
    scenario_only = client.get(f"/v1/agents/runs?tenant_id={tenant_id}&scenario=operations")

    assert listed.status_code == 200
    body = listed.json()
    assert [item["status"] for item in body] == ["blocked", "succeeded"]
    assert body[0]["redacted_query_preview"]
    assert body[0]["trace_step_count"] >= 1
    assert "answer" not in body[0]

    assert blocked_only.status_code == 200
    assert len(blocked_only.json()) == 1
    assert blocked_only.json()[0]["status"] == "blocked"

    assert scenario_only.status_code == 200
    assert len(scenario_only.json()) == 1
    assert scenario_only.json()[0]["scenario"] == "operations"


def test_agent_run_timeline_combines_trace_tool_and_audit_events():
    client = TestClient(create_app())
    tenant_id = "run-timeline"

    client.post(
        "/v1/documents/ingest",
        json={
            "tenant_id": tenant_id,
            "title": "Timeline 정책",
            "content": (
                "Agent timeline은 trace, tool execution, audit event를 "
                "한 실행 단위로 묶어야 한다."
            ),
            "source_uri": "test://run-timeline",
        },
    )
    run = client.post(
        "/v1/agents/runs",
        json={
            "tenant_id": tenant_id,
            "scenario": "operations",
            "message": "정책 문서를 근거로 workflow 생성 실행을 처리해줘",
        },
    )
    assert run.status_code == 200
    run_id = run.json()["run_id"]

    timeline = client.get(f"/v1/agents/runs/{run_id}/timeline?tenant_id={tenant_id}")

    assert timeline.status_code == 200
    body = timeline.json()
    sources = {item["source"] for item in body}
    event_types = {item["event_type"] for item in body}
    assert {"trace", "tool", "audit"}.issubset(sources)
    assert "tool_runtime" in event_types
    assert "workflow.request-change" in event_types
    assert "agent.answer.generated" in event_types
    assert body == sorted(body, key=lambda item: item["sequence"])
    audit_items = [item for item in body if item["source"] == "audit"]
    assert audit_items[0]["detail"]["payload"]


def test_api_returns_tool_execution_for_action_request():
    client = TestClient(create_app())

    client.post(
        "/v1/documents/ingest",
        json={
            "tenant_id": "default",
            "title": "업무 실행 정책",
            "content": (
                "외부 상태를 변경하는 업무 실행은 승인 대기 상태로 전환하고 "
                "감사로그에 남겨야 한다."
            ),
            "source_uri": "test://tool-policy",
        },
    )

    run = client.post(
        "/v1/agents/runs",
        json={
            "tenant_id": "default",
            "scenario": "operations",
            "message": "정책 문서를 근거로 보고서 생성 요청을 처리해줘",
        },
    )

    assert run.status_code == 200
    body = run.json()
    assert body["tool_executions"]
    assert body["tool_executions"][0]["decision"] == "approval_required"

    pending = client.get("/v1/approvals/pending?tenant_id=default")
    assert pending.status_code == 200
    approvals = pending.json()
    assert approvals
    assert approvals[0]["status"] == "pending"

    approval_id = approvals[0]["id"]
    approved = client.post(
        f"/v1/approvals/{approval_id}/approve",
        json={"tenant_id": "default", "approved_by": "operator-01"},
    )
    assert approved.status_code == 200
    approved_body = approved.json()
    assert approved_body["status"] == "executed"
    assert approved_body["replay_result"]["status"] == "succeeded"

    replay_again = client.post(
        f"/v1/approvals/{approval_id}/approve",
        json={"tenant_id": "default", "approved_by": "operator-01"},
    )
    assert replay_again.status_code == 200
    assert replay_again.json()["replay_result"] == approved_body["replay_result"]


def test_api_rejects_pending_approval_without_replay():
    client = TestClient(create_app())

    client.post(
        "/v1/documents/ingest",
        json={
            "tenant_id": "default",
            "title": "업무 실행 정책",
            "content": "외부 상태를 변경하는 업무 실행은 승인 또는 반려 기록을 남겨야 한다.",
            "source_uri": "test://approval-reject-policy",
        },
    )

    run = client.post(
        "/v1/agents/runs",
        json={
            "tenant_id": "default",
            "scenario": "operations",
            "message": "정책 문서를 근거로 보고서 생성 요청을 처리해줘",
        },
    )
    assert run.status_code == 200

    pending = client.get("/v1/approvals/pending?tenant_id=default")
    approval_id = pending.json()[0]["id"]

    rejected = client.post(
        f"/v1/approvals/{approval_id}/reject",
        json={
            "tenant_id": "default",
            "rejected_by": "operator-02",
            "reason": "요청 근거가 부족하여 실행하지 않습니다.",
        },
    )
    assert rejected.status_code == 200
    rejected_body = rejected.json()
    assert rejected_body["status"] == "rejected"
    assert rejected_body["approved_by"] == "operator-02"
    assert rejected_body["replay_result"]["decision"] == "rejected"

    pending_after = client.get("/v1/approvals/pending?tenant_id=default")
    assert pending_after.status_code == 200
    assert pending_after.json() == []

    approve_after_reject = client.post(
        f"/v1/approvals/{approval_id}/approve",
        json={"tenant_id": "default", "approved_by": "operator-01"},
    )
    assert approve_after_reject.status_code == 200
    assert approve_after_reject.json()["status"] == "rejected"
    assert approve_after_reject.json()["replay_result"] == rejected_body["replay_result"]


def test_mcp_tool_boundary_lists_and_calls_tools():
    client = TestClient(create_app())

    initialized = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": "init-1", "method": "initialize"},
    )
    assert initialized.status_code == 200
    assert initialized.json()["result"]["capabilities"]["tools"]

    listed = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": "list-1", "method": "tools/list"},
    )
    assert listed.status_code == 200
    tools = listed.json()["result"]["tools"]
    assert {tool["name"] for tool in tools} >= {
        "internal-records.lookup",
        "workflow.request-change",
    }
    assert tools[0]["inputSchema"]

    called = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "call-1",
            "method": "tools/call",
            "params": {
                "tenant_id": "default",
                "actor_id": "operator-01",
                "actor_scopes": ["records:read"],
                "name": "internal-records.lookup",
                "arguments": {"query": "최근 승인 대기 업무 조회"},
            },
        },
    )
    assert called.status_code == 200
    result = called.json()["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["decision"] == "allowed"
    assert result["structuredContent"]["status"] == "succeeded"


def test_mcp_write_tool_requires_scope_and_creates_approval():
    client = TestClient(create_app())

    denied = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "call-denied",
            "method": "tools/call",
            "params": {
                "tenant_id": "default",
                "actor_id": "operator-01",
                "actor_scopes": [],
                "name": "workflow.request-change",
                "arguments": {"request": "보고서 생성 workflow 실행"},
            },
        },
    )
    assert denied.status_code == 200
    assert denied.json()["result"]["isError"] is True
    assert denied.json()["result"]["structuredContent"]["decision"] == "denied"

    pending_before = client.get("/v1/approvals/pending?tenant_id=default")
    assert pending_before.status_code == 200
    assert pending_before.json() == []

    approval_required = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "call-approval",
            "method": "tools/call",
            "params": {
                "tenant_id": "default",
                "actor_id": "operator-01",
                "actor_scopes": ["workflow:request"],
                "name": "workflow.request-change",
                "arguments": {"request": "보고서 생성 workflow 실행"},
            },
        },
    )
    assert approval_required.status_code == 200
    body = approval_required.json()["result"]["structuredContent"]
    assert body["decision"] == "approval_required"
    assert body["status"] == "pending_approval"

    pending_after = client.get("/v1/approvals/pending?tenant_id=default")
    assert pending_after.status_code == 200
    approvals = pending_after.json()
    assert len(approvals) == 1
    assert approvals[0]["tool_name"] == "workflow.request-change"


def test_evaluation_run_scores_grounded_answers():
    client = TestClient(create_app())

    ingest = client.post(
        "/v1/documents/ingest",
        json={
            "tenant_id": "default",
            "title": "Agent 운영 평가 기준",
            "content": (
                "Agent 실행은 개인정보 마스킹, 권한 검사, 감사로그를 포함해야 한다. "
                "쓰기성 tool은 승인 대기 상태로 전환한다."
            ),
            "source_uri": "test://evaluation-policy",
        },
    )
    assert ingest.status_code == 200

    evaluated = client.post(
        "/v1/evaluations/runs",
        json={
            "tenant_id": "default",
            "name": "운영 정책 회귀 평가",
            "scenario": "operations",
            "cases": [
                {
                    "input_query": "Agent 운영 정책을 정리해줘",
                    "expected_facts": ["개인정보 마스킹", "감사로그"],
                },
                {
                    "input_query": "쓰기성 tool 실행 기준은?",
                    "expected_facts": ["승인 대기 상태"],
                },
            ],
        },
    )

    assert evaluated.status_code == 200
    body = evaluated.json()
    assert body["status"] == "completed"
    assert body["metrics"]["case_count"] == 2
    assert body["metrics"]["average_score"] >= 0.7
    assert body["metrics"]["failed_count"] == 0
    assert all(case["score"] >= 0.7 for case in body["cases"])

    fetched = client.get(f"/v1/evaluations/runs/{body['id']}?tenant_id=default")
    assert fetched.status_code == 200
    assert fetched.json()["metrics"] == body["metrics"]


def test_audit_events_can_be_filtered_and_exported():
    client = TestClient(create_app())

    ingested = client.post(
        "/v1/documents/ingest",
        json={
            "tenant_id": "default",
            "title": "감사 이벤트 export 정책",
            "content": "감사 이벤트는 JSONL 또는 CSV로 export할 수 있어야 한다.",
            "source_uri": "test://audit-export",
        },
    )
    assert ingested.status_code == 200

    listed = client.get("/v1/audit/events?tenant_id=default&event_type=document.ingested")
    assert listed.status_code == 200
    assert listed.json()
    assert {event["event_type"] for event in listed.json()} == {"document.ingested"}

    exported_jsonl = client.get(
        "/v1/audit/export?tenant_id=default&event_type=document.ingested&format=jsonl"
    )
    assert exported_jsonl.status_code == 200
    assert exported_jsonl.headers["content-type"].startswith("application/x-ndjson")
    lines = [line for line in exported_jsonl.text.splitlines() if line]
    assert lines
    decoded = [json.loads(line) for line in lines]
    assert {event["event_type"] for event in decoded} == {"document.ingested"}
    assert decoded[0]["payload"]["title"] == "감사 이벤트 export 정책"

    exported_csv = client.get(
        "/v1/audit/export?tenant_id=default&event_type=document.ingested&format=csv"
    )
    assert exported_csv.status_code == 200
    assert exported_csv.headers["content-type"].startswith("text/csv")
    assert "event_type" in exported_csv.text
    assert "document.ingested" in exported_csv.text


def test_operations_summary_aggregates_runtime_signals():
    client = TestClient(create_app())

    client.post(
        "/v1/documents/ingest",
        json={
            "tenant_id": "default",
            "title": "운영 요약 정책",
            "content": (
                "Agent 실행은 감사 이벤트와 confidence를 남긴다. "
                "쓰기성 tool은 승인 대기 상태로 전환한다."
            ),
            "source_uri": "test://operations-summary",
        },
    )
    client.post(
        "/v1/agents/runs",
        json={
            "tenant_id": "default",
            "scenario": "operations",
            "message": "운영 요약 정책을 설명해줘",
        },
    )
    client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "summary-approval",
            "method": "tools/call",
            "params": {
                "tenant_id": "default",
                "actor_id": "operator-01",
                "actor_scopes": ["workflow:request"],
                "name": "workflow.request-change",
                "arguments": {"request": "운영 보고서 생성 workflow 실행"},
            },
        },
    )
    evaluated = client.post(
        "/v1/evaluations/runs",
        json={
            "tenant_id": "default",
            "name": "운영 요약 평가",
            "scenario": "operations",
            "cases": [
                {
                    "input_query": "운영 요약 정책을 설명해줘",
                    "expected_facts": ["감사 이벤트", "confidence"],
                }
            ],
        },
    )
    assert evaluated.status_code == 200

    summary = client.get("/v1/operations/summary?tenant_id=default")

    assert summary.status_code == 200
    body = summary.json()
    assert body["document_count"] >= 1
    assert body["agent_run_count"] >= 1
    assert body["pending_approval_count"] >= 1
    assert body["event_counts"]["document.ingested"] >= 1
    assert body["tool_decision_counts"]["approval_required"] >= 1
    assert body["approval_counts"]["requested"] >= 1
    assert body["latest_evaluation_metrics"]["case_count"] == 1


def test_monthly_usage_quota_blocks_agent_runs_and_reports_operations_usage(monkeypatch):
    with monkeypatch.context() as scoped:
        scoped.setenv("MONTHLY_AGENT_RUN_QUOTA", "1")
        _clear_runtime_caches()
        client = TestClient(create_app())
        tenant_id = "usage-quota"

        first = client.post(
            "/v1/agents/runs",
            json={
                "tenant_id": tenant_id,
                "scenario": "operations",
                "message": "월간 사용량 guard가 없는 상태에서 첫 실행은 허용되어야 한다.",
            },
        )
        second = client.post(
            "/v1/agents/runs",
            json={
                "tenant_id": tenant_id,
                "scenario": "operations",
                "message": "월간 사용량 quota를 초과한 두 번째 실행은 차단되어야 한다.",
            },
        )

        assert first.status_code == 200
        assert first.json()["status"] == "succeeded"
        assert second.status_code == 200
        blocked = second.json()
        assert blocked["status"] == "blocked"
        assert blocked["policy"]["decision"] == "quota_exceeded"
        assert any(step["step"] == "quota_guard" for step in blocked["trace"])

        usage = client.get(f"/v1/operations/usage?tenant_id={tenant_id}")
        assert usage.status_code == 200
        usage_body = usage.json()
        assert usage_body["monthly_agent_run_quota"] == 1
        assert usage_body["agent_runs_used"] == 2
        assert usage_body["agent_runs_remaining"] == 0
        assert usage_body["exceeded"] is True

        alerts = client.get(f"/v1/operations/alerts?tenant_id={tenant_id}")
        assert alerts.status_code == 200
        assert "monthly_agent_run_quota" in {alert["code"] for alert in alerts.json()}

        events = client.get(
            f"/v1/audit/events?tenant_id={tenant_id}&event_type=agent.quota.exceeded"
        )
        assert events.status_code == 200
        assert len(events.json()) == 1

    _clear_runtime_caches()


def test_operations_slo_calculates_runtime_service_objectives():
    client = TestClient(create_app())
    container = get_container()
    tenant_id = "slo-test"

    for status, latency_ms, confidence in [
        ("succeeded", 1200, 0.82),
        ("succeeded", 1800, 0.88),
        ("blocked", 4200, 0.2),
    ]:
        container.base_audit_log.append(
            AuditEvent(
                tenant_id=tenant_id,
                actor_type="agent",
                actor_id="test",
                event_type="agent.answer.generated",
                resource_type="agent_run",
                payload={
                    "latency_ms": latency_ms,
                    "confidence": confidence,
                    "status": status,
                },
            )
        )

    response = client.get(
        f"/v1/operations/slo?tenant_id={tenant_id}"
        "&latency_target_ms=3000&success_rate_target=0.8"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_count"] == 3
    assert body["success_count"] == 2
    assert body["blocked_count"] == 1
    assert body["success_rate"] == 0.667
    assert body["blocked_rate"] == 0.333
    assert body["p95_latency_ms"] == 4200.0
    assert body["status"] == "breached"


def test_operations_incident_snapshot_combines_alerts_slo_and_actions():
    client = TestClient(create_app())
    container = get_container()
    tenant_id = "incident-snapshot"

    container.base_audit_log.append(
        AuditEvent(
            tenant_id=tenant_id,
            actor_type="agent",
            actor_id="test",
            event_type="agent.answer.generated",
            resource_type="agent_run",
            payload={
                "latency_ms": 5200,
                "confidence": 0.22,
                "status": "blocked",
            },
        )
    )

    response = client.get(f"/v1/operations/incidents/snapshot?tenant_id={tenant_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["severity"] == "critical"
    assert body["status"] == "open"
    assert body["active_alert_count"] >= 1
    assert any("성공률" in cause for cause in body["suspected_causes"])
    assert any("timeline" in action for action in body["recommended_actions"])


def test_operations_alerts_detect_runtime_threshold_breaches():
    client = TestClient(create_app())
    container = get_container()
    tenant_id = "alerts-test"

    container.base_audit_log.append(
        AuditEvent(
            tenant_id=tenant_id,
            actor_type="agent",
            actor_id="test",
            event_type="agent.answer.generated",
            resource_type="agent_run",
            payload={
                "latency_ms": 4200,
                "confidence": 0.31,
                "status": "succeeded",
            },
        )
    )
    container.base_audit_log.append(
        AuditEvent(
            tenant_id=tenant_id,
            actor_type="agent",
            actor_id="test",
            event_type="tool.allowed",
            resource_type="tool_call",
            payload={
                "output_payload": {
                    "_gateway": {
                        "fallback_used": True,
                    }
                }
            },
        )
    )
    container.base_audit_log.append(
        AuditEvent(
            tenant_id=tenant_id,
            actor_type="system",
            actor_id="evaluation",
            event_type="evaluation.completed",
            resource_type="evaluation_run",
            payload={
                "metrics": {
                    "case_count": 4,
                    "pass_rate": 0.5,
                }
            },
        )
    )

    response = client.get(
        "/v1/operations/alerts",
        params={
            "tenant_id": tenant_id,
            "max_average_latency_ms": 3000,
            "min_average_confidence": 0.55,
            "max_gateway_fallbacks": 0,
            "min_evaluation_pass_rate": 0.85,
        },
    )

    assert response.status_code == 200
    alerts = response.json()
    codes = {alert["code"] for alert in alerts}
    assert codes == {
        "agent_latency_high",
        "answer_confidence_low",
        "tool_gateway_fallback",
        "evaluation_pass_rate_low",
    }
    severities = {alert["code"]: alert["severity"] for alert in alerts}
    assert severities["agent_latency_high"] == "warning"
    assert severities["tool_gateway_fallback"] == "critical"


def test_retention_prune_supports_dry_run_and_terminal_cleanup():
    client = TestClient(create_app())
    container = get_container()
    tenant_id = "retention-test"
    now = datetime.now(UTC)
    old_event = AuditEvent(
        tenant_id=tenant_id,
        actor_type="system",
        actor_id="test",
        event_type="retention.old",
        resource_type="retention",
        payload={"state": "old"},
        created_at=now - timedelta(days=120),
    )
    fresh_event = AuditEvent(
        tenant_id=tenant_id,
        actor_type="system",
        actor_id="test",
        event_type="retention.fresh",
        resource_type="retention",
        payload={"state": "fresh"},
        created_at=now,
    )
    delivered = WebhookDelivery(
        tenant_id=tenant_id,
        subscription_id=uuid4(),
        event_id=old_event.id,
        event_type=old_event.event_type,
        target_url="https://example.com/webhook",
        payload={"id": str(old_event.id)},
        status=WebhookDeliveryStatus.DELIVERED,
        created_at=now - timedelta(days=40),
        delivered_at=now - timedelta(days=39),
    )
    pending = WebhookDelivery(
        tenant_id=tenant_id,
        subscription_id=uuid4(),
        event_id=fresh_event.id,
        event_type=fresh_event.event_type,
        target_url="https://example.com/webhook",
        payload={"id": str(fresh_event.id)},
        status=WebhookDeliveryStatus.PENDING,
        created_at=now - timedelta(days=40),
    )
    container.base_audit_log.append(old_event)
    container.base_audit_log.append(fresh_event)
    container.webhook_deliveries.save(delivered)
    container.webhook_deliveries.save(pending)

    dry_run = client.post(
        "/v1/operations/retention/prune",
        json={
            "tenant_id": tenant_id,
            "audit_older_than_days": 90,
            "webhook_older_than_days": 30,
        },
    )

    assert dry_run.status_code == 200
    dry_body = dry_run.json()
    assert dry_body["dry_run"] is True
    assert dry_body["audit_events_matched"] == 1
    assert dry_body["webhook_deliveries_matched"] == 1
    assert dry_body["audit_events_deleted"] == 0
    assert dry_body["webhook_deliveries_deleted"] == 0
    assert container.base_audit_log.count_events_before(
        tenant_id,
        now - timedelta(days=90),
    ) == 1

    executed = client.post(
        "/v1/operations/retention/prune",
        json={
            "tenant_id": tenant_id,
            "audit_older_than_days": 90,
            "webhook_older_than_days": 30,
            "dry_run": False,
        },
    )

    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["dry_run"] is False
    assert executed_body["audit_events_deleted"] == 1
    assert executed_body["webhook_deliveries_deleted"] == 1
    assert container.webhook_deliveries.get(tenant_id, str(delivered.id)) is None
    assert container.webhook_deliveries.get(tenant_id, str(pending.id)) is not None

    remaining_events = container.base_audit_log.list_events(tenant_id=tenant_id, limit=10)
    event_types = {event.event_type for event in remaining_events}
    assert "retention.old" not in event_types
    assert "retention.fresh" in event_types
    assert "retention.pruned" in event_types


def test_operator_dashboard_serves_backend_console():
    client = TestClient(create_app())

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Enterprise AX Agent Operations" in response.text
    assert "/v1/agents/runs/preview" in response.text
    assert "preview-result" in response.text
    assert "/v1/operations/summary" in response.text
    assert "/v1/operations/usage" in response.text
    assert "/v1/operations/slo" in response.text
    assert "/v1/operations/incidents/snapshot" in response.text
    assert "/v1/operations/alerts" in response.text
    assert "/v1/agents/runs" in response.text
    assert "/timeline" in response.text
    assert "agent-run-timeline" in response.text
    assert "metric-usage" in response.text
    assert "metric-slo" in response.text
    assert "incident-snapshot" in response.text
    assert "/v1/approvals/pending" in response.text
    assert "/v1/audit/events" in response.text
    assert "audit-request-id" in response.text
    assert "request_id" in response.text
    assert "/v1/tools" in response.text
    assert "data-approval-action=\"approve\"" in response.text
    assert "data-approval-action=\"reject\"" in response.text
    assert "X-API-Key" in response.text


def test_api_key_auth_can_protect_operational_apis(monkeypatch):
    with monkeypatch.context() as scoped:
        scoped.setenv("AUTH_ENABLED", "true")
        scoped.setenv(
            "API_KEY_CREDENTIALS",
            "ops-key:operator-01:operations:read|tools:read",
        )
        _clear_runtime_caches()
        client = TestClient(create_app())

        missing_key = client.get("/v1/operations/summary?tenant_id=default")
        assert missing_key.status_code == 401

        invalid_key = client.get(
            "/v1/operations/summary?tenant_id=default",
            headers={"X-API-Key": "wrong-key"},
        )
        assert invalid_key.status_code == 401

        allowed = client.get(
            "/v1/operations/summary?tenant_id=default",
            headers={"X-API-Key": "ops-key"},
        )
        assert allowed.status_code == 200

        forbidden = client.post(
            "/v1/documents/ingest",
            headers={"X-API-Key": "ops-key"},
            json={
                "tenant_id": "default",
                "title": "권한 테스트 문서",
                "content": "문서 쓰기 scope가 없으면 적재할 수 없다.",
                "source_uri": "test://auth-scope",
            },
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"]["missing_scopes"] == ["documents:write"]

    _clear_runtime_caches()


def test_api_key_auth_requires_operations_write_for_retention(monkeypatch):
    with monkeypatch.context() as scoped:
        scoped.setenv("AUTH_ENABLED", "true")
        scoped.setenv(
            "API_KEY_CREDENTIALS",
            "read-key:operator-01:operations:read;write-key:operator-02:operations:write",
        )
        _clear_runtime_caches()
        client = TestClient(create_app())

        denied = client.post(
            "/v1/operations/retention/prune",
            headers={"X-API-Key": "read-key"},
            json={"tenant_id": "default"},
        )
        allowed = client.post(
            "/v1/operations/retention/prune",
            headers={"X-API-Key": "write-key"},
            json={"tenant_id": "default"},
        )

        assert denied.status_code == 403
        assert denied.json()["detail"]["missing_scopes"] == ["operations:write"]
        assert allowed.status_code == 200
        assert allowed.json()["dry_run"] is True

    _clear_runtime_caches()


def test_api_key_auth_restricts_tenant_access(monkeypatch):
    with monkeypatch.context() as scoped:
        scoped.setenv("AUTH_ENABLED", "true")
        scoped.setenv(
            "API_KEY_CREDENTIALS",
            "tenant-a-key:operator-a:operations:read|documents:write|mcp:use@tenant-a",
        )
        _clear_runtime_caches()
        client = TestClient(create_app())
        headers = {"X-API-Key": "tenant-a-key"}

        allowed_summary = client.get(
            "/v1/operations/summary?tenant_id=tenant-a",
            headers=headers,
        )
        assert allowed_summary.status_code == 200

        denied_summary = client.get(
            "/v1/operations/summary?tenant_id=tenant-b",
            headers=headers,
        )
        assert denied_summary.status_code == 403
        assert denied_summary.json()["detail"]["tenant_id"] == "tenant-b"

        allowed_ingest = client.post(
            "/v1/documents/ingest",
            headers=headers,
            json={
                "tenant_id": "tenant-a",
                "title": "Tenant A 문서",
                "content": "Tenant 제한 key는 허용된 tenant의 문서만 적재할 수 있다.",
                "source_uri": "test://tenant-a",
            },
        )
        assert allowed_ingest.status_code == 200

        denied_mcp = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": "tenant-denied",
                "method": "tools/call",
                "params": {
                    "tenant_id": "tenant-b",
                    "actor_id": "operator-a",
                    "actor_scopes": ["records:read"],
                    "name": "internal-records.lookup",
                    "arguments": {"query": "tenant b 조회"},
                },
            },
        )
        assert denied_mcp.status_code == 403

    _clear_runtime_caches()


def test_idempotency_key_replays_document_ingest_response():
    client = TestClient(create_app())
    request = {
        "tenant_id": "default",
        "title": "멱등 문서 적재",
        "content": "Idempotency-Key가 같으면 같은 문서 적재 응답을 replay해야 한다.",
        "source_uri": "test://idempotent-document",
    }
    headers = {"Idempotency-Key": "doc-ingest-001"}

    first = client.post("/v1/documents/ingest", json=request, headers=headers)
    second = client.post("/v1/documents/ingest", json=request, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()

    documents = client.get("/v1/documents?tenant_id=default")
    assert documents.status_code == 200
    matching = [
        document
        for document in documents.json()
        if document["source_uri"] == "test://idempotent-document"
    ]
    assert len(matching) == 1

    conflict = client.post(
        "/v1/documents/ingest",
        json={**request, "title": "다른 payload"},
        headers=headers,
    )
    assert conflict.status_code == 409


def test_idempotency_key_replays_agent_run_response():
    client = TestClient(create_app())
    client.post(
        "/v1/documents/ingest",
        json={
            "tenant_id": "default",
            "title": "Agent 멱등 실행 기준",
            "content": "Agent 실행 요청은 같은 Idempotency-Key에서 같은 응답을 반환해야 한다.",
            "source_uri": "test://idempotent-agent",
        },
    )
    request = {
        "tenant_id": "default",
        "scenario": "operations",
        "message": "Agent 멱등 실행 기준을 설명해줘",
    }
    headers = {"Idempotency-Key": "agent-run-001"}

    first = client.post("/v1/agents/runs", json=request, headers=headers)
    second = client.post("/v1/agents/runs", json=request, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()

    conflict = client.post(
        "/v1/agents/runs",
        json={**request, "message": "다른 질문"},
        headers=headers,
    )
    assert conflict.status_code == 409


def test_document_ingest_updates_ontology_graph():
    client = TestClient(create_app())

    ingest = client.post(
        "/v1/documents/ingest",
        json={
            "tenant_id": "default",
            "title": "Agentic RAG 온톨로지 운영 모델",
            "content": (
                "Agentic RAG 플랫폼은 문서 검색, 정책 감사, 승인 워크플로우, "
                "Knowledge Graph를 연결한다. 운영자는 감사 이벤트와 tool 실행 이력을 추적한다."
            ),
            "source_uri": "test://ontology-agentic-rag",
            "metadata": {
                "domain": "operations",
                "system": ["approval", "audit"],
            },
        },
    )
    assert ingest.status_code == 200

    graph = client.get("/v1/ontology/graph?tenant_id=default")

    assert graph.status_code == 200
    body = graph.json()
    assert body["tenant_id"] == "default"
    assert body["nodes"]
    assert body["edges"]
    node_types = {node["node_type"] for node in body["nodes"]}
    assert "document" in node_types
    assert "classification" in node_types
    assert "concept" in node_types
    assert "metadata:domain" in node_types
    relations = {edge["relation"] for edge in body["edges"]}
    assert {"classified_as", "mentions", "has_metadata"} <= relations
    labels = {node["label"] for node in body["nodes"]}
    assert "Agentic RAG 온톨로지 운영 모델" in labels


def test_webhook_subscription_creates_audit_delivery_outbox():
    client = TestClient(create_app())

    subscription = client.post(
        "/v1/webhooks/subscriptions",
        json={
            "tenant_id": "default",
            "name": "document-ingest-outbox",
            "target_url": "https://workflow.internal/hooks/documents",
            "event_types": ["document.ingested"],
        },
    )
    assert subscription.status_code == 200
    subscription_body = subscription.json()
    assert subscription_body["event_types"] == ["document.ingested"]

    ingest = client.post(
        "/v1/documents/ingest",
        json={
            "tenant_id": "default",
            "title": "Webhook outbox 문서",
            "content": "문서 적재 감사 이벤트는 webhook delivery outbox에 pending 상태로 쌓인다.",
            "source_uri": "test://webhook-outbox",
        },
    )
    assert ingest.status_code == 200

    deliveries = client.get("/v1/webhooks/deliveries?tenant_id=default&status=pending")

    assert deliveries.status_code == 200
    body = deliveries.json()
    assert len(body) == 1
    assert body[0]["subscription_id"] == subscription_body["id"]
    assert body[0]["event_type"] == "document.ingested"
    assert body[0]["status"] == "pending"
    assert body[0]["payload"]["payload"]["title"] == "Webhook outbox 문서"

    delivered = client.post(
        f"/v1/webhooks/deliveries/{body[0]['id']}/mark-delivered",
        json={"tenant_id": "default"},
    )
    assert delivered.status_code == 200
    assert delivered.json()["status"] == "delivered"
    assert delivered.json()["attempt_count"] == 1


def test_webhook_delivery_payload_includes_request_id():
    client = TestClient(create_app())

    subscription = client.post(
        "/v1/webhooks/subscriptions",
        json={
            "tenant_id": "default",
            "name": "request-context-workflow",
            "target_url": "https://workflow.internal/hooks/request-context",
            "event_types": ["document.ingested"],
        },
    )
    assert subscription.status_code == 200

    ingest = client.post(
        "/v1/documents/ingest",
        headers={"X-Request-ID": "webhook-trace-001"},
        json={
            "tenant_id": "default",
            "title": "Webhook request context 문서",
            "content": "Webhook delivery payload는 request id를 포함해야 한다.",
            "source_uri": "test://webhook-request-context",
        },
    )
    assert ingest.status_code == 200

    deliveries = client.get("/v1/webhooks/deliveries?tenant_id=default&status=pending")

    assert deliveries.status_code == 200
    assert deliveries.json()[0]["payload"]["payload"]["request_id"] == "webhook-trace-001"


def test_webhook_dispatcher_signs_and_marks_delivered():
    subscriptions = InMemoryWebhookSubscriptionRepository()
    deliveries = InMemoryWebhookDeliveryRepository()
    subscription = subscriptions.save(
        WebhookSubscription(
            tenant_id="default",
            name="signed-dispatch",
            target_url="https://workflow.internal/hooks/signed",
            event_types=["document.ingested"],
            secret="secret-01",
        )
    )
    delivery = deliveries.save(
        WebhookDelivery(
            tenant_id="default",
            subscription_id=subscription.id,
            event_id=subscription.id,
            event_type="document.ingested",
            target_url=subscription.target_url,
            payload={"event_type": "document.ingested", "value": "ok"},
        )
    )
    http_client = FakeWebhookHttpClient(WebhookHttpResult(status_code=204))
    dispatcher = WebhookDispatcher(
        subscriptions=subscriptions,
        deliveries=deliveries,
        http_client=http_client,
        timeout_seconds=2.5,
        max_attempts=5,
    )

    dispatched = dispatcher.dispatch(tenant_id="default", delivery_id=str(delivery.id))

    assert dispatched is not None
    assert dispatched.status == "delivered"
    assert dispatched.attempt_count == 1
    assert dispatched.delivered_at is not None
    assert http_client.requests
    headers = http_client.requests[0]["headers"]
    assert isinstance(headers, dict)
    assert headers["X-AX-Delivery-Id"] == str(delivery.id)
    assert headers["X-AX-Signature"].startswith("sha256=")
    assert http_client.requests[0]["timeout_seconds"] == 2.5


def test_webhook_dispatcher_marks_failed_with_retry_time():
    subscriptions = InMemoryWebhookSubscriptionRepository()
    deliveries = InMemoryWebhookDeliveryRepository()
    subscription = subscriptions.save(
        WebhookSubscription(
            tenant_id="default",
            name="failed-dispatch",
            target_url="https://workflow.internal/hooks/fail",
            event_types=["*"],
        )
    )
    delivery = deliveries.save(
        WebhookDelivery(
            tenant_id="default",
            subscription_id=subscription.id,
            event_id=subscription.id,
            event_type="approval.rejected",
            target_url=subscription.target_url,
            payload={"event_type": "approval.rejected"},
        )
    )
    dispatcher = WebhookDispatcher(
        subscriptions=subscriptions,
        deliveries=deliveries,
        http_client=FakeWebhookHttpClient(
            WebhookHttpResult(status_code=503, response_body="unavailable")
        ),
        timeout_seconds=1,
        max_attempts=5,
    )

    dispatched = dispatcher.dispatch(tenant_id="default", delivery_id=str(delivery.id))

    assert dispatched is not None
    assert dispatched.status == "failed"
    assert dispatched.attempt_count == 1
    assert dispatched.next_attempt_at is not None
    assert "HTTP 503" in str(dispatched.last_error)


def test_webhook_dispatcher_moves_exhausted_delivery_to_dead_letter():
    subscriptions = InMemoryWebhookSubscriptionRepository()
    deliveries = InMemoryWebhookDeliveryRepository()
    subscription = subscriptions.save(
        WebhookSubscription(
            tenant_id="default",
            name="dead-letter-dispatch",
            target_url="https://workflow.internal/hooks/dead-letter",
            event_types=["*"],
        )
    )
    delivery = deliveries.save(
        replace(
            WebhookDelivery(
                tenant_id="default",
                subscription_id=subscription.id,
                event_id=subscription.id,
                event_type="document.ingested",
                target_url=subscription.target_url,
                payload={"event_type": "document.ingested"},
            ),
            status=WebhookDeliveryStatus.FAILED,
            attempt_count=5,
            next_attempt_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    http_client = FakeWebhookHttpClient(WebhookHttpResult(status_code=204))
    dispatcher = WebhookDispatcher(
        subscriptions=subscriptions,
        deliveries=deliveries,
        http_client=http_client,
        timeout_seconds=1,
        max_attempts=5,
    )

    dispatched = dispatcher.dispatch(tenant_id="default", delivery_id=str(delivery.id))

    assert dispatched is not None
    assert dispatched.status == "dead_letter"
    assert dispatched.next_attempt_at is None
    assert "maximum delivery attempts exceeded" in str(dispatched.last_error)
    assert http_client.requests == []


def test_webhook_dispatcher_dispatches_due_deliveries_batch():
    subscriptions = InMemoryWebhookSubscriptionRepository()
    deliveries = InMemoryWebhookDeliveryRepository()
    subscription = subscriptions.save(
        WebhookSubscription(
            tenant_id="default",
            name="batch-dispatch",
            target_url="https://workflow.internal/hooks/batch",
            event_types=["*"],
        )
    )
    pending = deliveries.save(
        WebhookDelivery(
            tenant_id="default",
            subscription_id=subscription.id,
            event_id=subscription.id,
            event_type="document.ingested",
            target_url=subscription.target_url,
            payload={"event_type": "document.ingested"},
        )
    )
    due_failed = deliveries.save(
        replace(
            WebhookDelivery(
                tenant_id="default",
                subscription_id=subscription.id,
                event_id=subscription.id,
                event_type="approval.rejected",
                target_url=subscription.target_url,
                payload={"event_type": "approval.rejected"},
            ),
            status=WebhookDeliveryStatus.FAILED,
            attempt_count=1,
            next_attempt_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )
    future_failed = deliveries.save(
        replace(
            WebhookDelivery(
                tenant_id="default",
                subscription_id=subscription.id,
                event_id=subscription.id,
                event_type="evaluation.completed",
                target_url=subscription.target_url,
                payload={"event_type": "evaluation.completed"},
            ),
            status=WebhookDeliveryStatus.FAILED,
            attempt_count=1,
            next_attempt_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    http_client = FakeWebhookHttpClient(WebhookHttpResult(status_code=204))
    dispatcher = WebhookDispatcher(
        subscriptions=subscriptions,
        deliveries=deliveries,
        http_client=http_client,
        timeout_seconds=1,
        max_attempts=5,
    )

    dispatched = dispatcher.dispatch_pending(tenant_id="default", limit=10)

    assert {delivery.id for delivery in dispatched} == {pending.id, due_failed.id}
    assert {delivery.status for delivery in dispatched} == {"delivered"}
    assert len(http_client.requests) == 2
    assert deliveries.get("default", str(future_failed.id)).status == "failed"


def test_webhook_delivery_claim_lease_prevents_duplicate_batch_dispatch():
    deliveries = InMemoryWebhookDeliveryRepository()
    delivery = deliveries.save(
        WebhookDelivery(
            tenant_id="default",
            subscription_id=uuid4(),
            event_id=uuid4(),
            event_type="document.ingested",
            target_url="https://workflow.internal/hooks/lease",
            payload={"event_type": "document.ingested"},
        )
    )
    now = datetime.now(UTC)

    first_claim = deliveries.claim_dispatchable(
        tenant_id="default",
        now=now,
        lease_until=now + timedelta(minutes=1),
        limit=10,
    )
    second_claim = deliveries.claim_dispatchable(
        tenant_id="default",
        now=now,
        lease_until=now + timedelta(minutes=1),
        limit=10,
    )
    expired_claim = deliveries.claim_dispatchable(
        tenant_id="default",
        now=now + timedelta(minutes=2),
        lease_until=now + timedelta(minutes=3),
        limit=10,
    )

    assert [item.id for item in first_claim] == [delivery.id]
    assert first_claim[0].status == WebhookDeliveryStatus.DISPATCHING
    assert second_claim == []
    assert [item.id for item in expired_claim] == [delivery.id]


def test_webhook_dispatch_pending_api_returns_empty_batch():
    client = TestClient(create_app())

    response = client.post(
        "/v1/webhooks/deliveries/dispatch-pending",
        json={"tenant_id": "empty-batch", "limit": 10},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_webhook_retry_api_resets_failed_delivery_to_pending():
    client = TestClient(create_app())

    subscription = client.post(
        "/v1/webhooks/subscriptions",
        json={
            "tenant_id": "default",
            "name": "retry-workflow",
            "target_url": "https://workflow.internal/hooks/retry",
            "event_types": ["document.ingested"],
        },
    )
    assert subscription.status_code == 200
    ingest = client.post(
        "/v1/documents/ingest",
        json={
            "tenant_id": "default",
            "title": "Webhook retry 문서",
            "content": "실패한 webhook delivery는 수동 retry로 다시 pending 상태가 될 수 있다.",
            "source_uri": "test://webhook-retry",
        },
    )
    assert ingest.status_code == 200
    deliveries = client.get("/v1/webhooks/deliveries?tenant_id=default&status=pending")
    assert deliveries.status_code == 200
    delivery_id = deliveries.json()[0]["id"]

    failed = client.post(
        f"/v1/webhooks/deliveries/{delivery_id}/mark-failed",
        json={"tenant_id": "default", "error": "manual failure"},
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"

    retried = client.post(
        f"/v1/webhooks/deliveries/{delivery_id}/retry",
        json={"tenant_id": "default"},
    )

    assert retried.status_code == 200
    body = retried.json()
    assert body["status"] == "pending"
    assert body["attempt_count"] == 0
    assert body["last_error"] is None
