# API 설계

API는 LLM 구현 세부사항이 아니라 업무 기능을 노출한다.

## 버전 정책

모든 API는 `/v1` 하위에 둔다.

```text
GET  /health
GET  /v1/readiness

POST /v1/documents/ingest
GET  /v1/documents

POST /v1/knowledge/search

POST /v1/agents/runs
GET  /v1/agents/runs/{run_id}

GET  /v1/audit/events

GET  /v1/approvals/pending
POST /v1/approvals/{approval_id}/approve
```

## Agent 실행 요청

```json
{
  "tenant_id": "default",
  "user_id": "operator-01",
  "scenario": "operations",
  "message": "고객사의 AX 전환 리스크와 실행 순서를 정리해줘.",
  "context": {
    "department": "digital-transformation",
    "risk_level": "medium"
  }
}
```

## Agent 실행 응답

```json
{
  "run_id": "018f...",
  "status": "succeeded",
  "query_type": "risk",
  "answer": "...",
  "confidence": 0.82,
  "citations": [
    {
      "document_id": "018f...",
      "chunk_id": "018f...",
      "title": "AX 거버넌스 플레이북",
      "score": 0.77,
      "source_uri": "data/sample_docs/ax-governance.md"
    }
  ],
  "trace": [
    {
      "step": "classify_query",
      "status": "succeeded",
      "detail": {
        "query_type": "risk"
      }
    }
  ],
  "policy": {
    "allowed": true,
    "decision": "allowed",
    "reason": "요청이 현재 정책 기준을 통과했습니다.",
    "redactions": 0
  },
  "tool_executions": [
    {
      "tool_name": "workflow.request-change",
      "action_type": "write",
      "decision": "approval_required",
      "status": "pending_approval"
    }
  ]
}
```

## 오류 응답

```json
{
  "error": {
    "code": "POLICY_DENIED",
    "message": "요청한 쓰기 작업은 승인 절차가 필요합니다.",
    "trace_id": "..."
  }
}
```

## 승인 요청 응답

```json
{
  "id": "018f...",
  "tenant_id": "default",
  "agent_run_id": "018f...",
  "tool_execution_id": "018f...",
  "tool_name": "workflow.request-change",
  "action_type": "write",
  "status": "pending",
  "reason": "외부 상태를 변경하는 작업은 승인 대기 상태로 전환합니다.",
  "requested_by": "operator-01",
  "approved_by": null,
  "replay_result": {}
}
```

승인 후에는 같은 리소스가 `executed` 상태로 바뀌고 replay 결과가 저장된다.

```json
{
  "status": "executed",
  "approved_by": "operator-02",
  "replay_result": {
    "tool_name": "workflow.request-change",
    "decision": "allowed",
    "status": "succeeded"
  }
}
```

## 헤더

| 헤더 | 목적 |
| --- | --- |
| `X-Request-Id` | 호출자 trace id |
| `Idempotency-Key` | 쓰기 API 재시도 안전성 |
| `X-Tenant-Id` | 요청 body가 없을 때 tenant 지정 |

## 설계 의도

- raw prompt를 그대로 노출하지 않고 구조화된 trace만 반환한다.
- citation을 응답에 포함해 RAG 답변을 검증 가능하게 만든다.
- policy decision을 응답에 포함해 차단/승인 상태를 제품 상태로 다룬다.
- tool execution을 응답에 포함해 외부 시스템 실행 경계를 확인할 수 있게 한다.
- 승인 요청은 별도 리소스로 다뤄 pending, executed 상태 전이를 추적한다.
- 평가 API를 별도 축으로 두어 Agent 품질을 회귀 테스트할 수 있게 한다.
