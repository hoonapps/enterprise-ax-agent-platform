import json

from fastapi.testclient import TestClient

from apps.api.main import create_app


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


def test_operator_dashboard_serves_backend_console():
    client = TestClient(create_app())

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Enterprise AX Agent Operations" in response.text
    assert "/v1/operations/summary" in response.text
    assert "/v1/approvals/pending" in response.text
    assert "/v1/audit/events" in response.text
    assert "/v1/tools" in response.text
