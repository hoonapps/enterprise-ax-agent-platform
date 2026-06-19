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
GET  /v1/audit/export

POST /v1/evaluations/runs
GET  /v1/evaluations/runs/{evaluation_run_id}

GET  /v1/tools
POST /mcp
GET  /v1/approvals/pending
POST /v1/approvals/{approval_id}/approve
POST /v1/approvals/{approval_id}/reject
```

## Agent 실행 요청

```json
{
  "tenant_id": "default",
  "user_id": "operator-01",
  "scenario": "operations",
  "message": "고객사의 AX 전환 리스크와 실행 순서를 정리해줘.",
  "actor_scopes": ["records:read", "workflow:request"],
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

## Tool Catalog 응답

```json
[
  {
    "name": "workflow.request-change",
    "action_type": "write",
    "required_scope": "workflow:request",
    "risk_level": "high",
    "description": "외부 상태 변경이 필요한 workflow 요청을 생성한다.",
    "enabled": true
  }
]
```

## MCP-Compatible JSON-RPC

`/mcp`는 tool discovery와 tool call을 위한 JSON-RPC boundary다.

초기화:

```json
{
  "jsonrpc": "2.0",
  "id": "init-1",
  "method": "initialize"
}
```

Tool 목록:

```json
{
  "jsonrpc": "2.0",
  "id": "tools-1",
  "method": "tools/list"
}
```

Tool 호출:

```json
{
  "jsonrpc": "2.0",
  "id": "call-1",
  "method": "tools/call",
  "params": {
    "tenant_id": "default",
    "actor_id": "operator-01",
    "actor_scopes": ["records:read"],
    "name": "internal-records.lookup",
    "arguments": {
      "query": "최근 승인 대기 업무 조회"
    }
  }
}
```

Tool 호출 응답은 `content`, `structuredContent`, `isError`를 포함한다.
`structuredContent`에는 내부 `tool_execution_id`, `decision`, `status`, `output_payload`가 들어간다.

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

반려 후에는 같은 리소스가 `rejected` 상태로 바뀌고 replay를 실행하지 않는다.

```json
{
  "status": "rejected",
  "approved_by": "operator-02",
  "replay_result": {
    "decision": "rejected",
    "rejected_by": "operator-02",
    "reason": "요청 근거가 부족하여 실행하지 않습니다."
  }
}
```

## Evaluation Run

요청:

```json
{
  "tenant_id": "default",
  "name": "운영 정책 회귀 평가",
  "scenario": "operations",
  "cases": [
    {
      "input_query": "Agent 운영 정책을 정리해줘",
      "expected_facts": ["개인정보 마스킹", "감사로그"]
    }
  ]
}
```

## Audit Export

JSONL export:

```text
GET /v1/audit/export?tenant_id=default&event_type=document.ingested&format=jsonl
```

CSV export:

```text
GET /v1/audit/export?tenant_id=default&resource_type=agent_run&format=csv
```

지원 query parameter:

| 파라미터 | 의미 |
| --- | --- |
| `tenant_id` | export 대상 tenant |
| `event_type` | 특정 이벤트 타입 필터 |
| `resource_type` | 특정 리소스 타입 필터 |
| `limit` | 최대 export 개수 |
| `format` | `jsonl` 또는 `csv` |

## Regression Dataset

CI regression gate는 API request와 유사한 JSON dataset을 사용한다.

```json
{
  "tenant_id": "default",
  "name": "core-agent-regression-ko",
  "scenario": "operations",
  "minimum_average_score": 0.8,
  "minimum_pass_rate": 1.0,
  "cases": [
    {
      "input_query": "AX Agent 거버넌스 기준을 설명해줘",
      "expected_facts": ["개인정보", "감사 이벤트", "쓰기 작업"]
    }
  ]
}
```

`scripts/run_regression_eval.py`는 sample documents를 적재한 뒤 같은 evaluation use case를 실행한다.
점수가 기준보다 낮으면 프로세스를 실패시킨다.

응답:

```json
{
  "id": "018f...",
  "status": "completed",
  "metrics": {
    "case_count": 1,
    "average_score": 1.0,
    "pass_rate": 1.0,
    "failed_count": 0
  },
  "cases": [
    {
      "input_query": "Agent 운영 정책을 정리해줘",
      "expected_facts": ["개인정보 마스킹", "감사로그"],
      "score": 1.0,
      "failure_reason": null
    }
  ]
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
- tool catalog를 API로 노출해 required scope와 risk level을 확인할 수 있게 한다.
- MCP 경유 tool call도 동일한 audit/approval 흐름으로 처리한다.
- 승인 요청은 별도 리소스로 다뤄 pending, executed, rejected 상태 전이를 추적한다.
- 평가 API를 별도 축으로 두어 Agent 품질을 회귀 테스트할 수 있게 한다.
