# Enterprise AX Agent Platform

사내 지식 검색, 업무 자동화, 정책 감사, 실행 추적을 하나의 흐름으로 묶는 기업형 AX Agent 백엔드입니다.

LLM Agent를 단순 챗봇으로 두지 않고, 운영 가능한 업무 시스템으로 만들기 위해 다음 문제를 제품 경계로 다룹니다.

- 어떤 문서를 근거로 답했는가
- 어떤 정책 검사를 통과했는가
- 어떤 tool 실행이 허용되거나 차단되었는가
- 실패와 재시도는 어디에서 제어되는가
- 운영자는 어떤 trace와 audit event로 문제를 추적하는가

## 현재 구현 범위

- FastAPI 기반 REST API
- 문서 적재 API
- 문서 chunking
- 로컬 deterministic 검색 어댑터
- Qdrant Vector DB 어댑터
- Postgres Repository 어댑터
- 질문 유형 분류
- 질문 유형별 RAG 전략 선택
- 근거 기반 답변 생성
- 개인정보 마스킹 정책
- 위험 action 승인 차단 정책
- Tool Runtime 정책 결정
- Tool Gateway 실행 어댑터
- Tool Gateway timeout/retry/fallback wrapper
- 조회 tool 즉시 실행
- 쓰기 tool 승인 대기 전환
- Tool Schema Registry
- required scope 기반 tool 실행 제어
- MCP-compatible JSON-RPC tool boundary
- 승인 요청 조회 API
- 승인 후 tool replay
- 승인 요청 반려 API
- 중복 승인 replay 방지
- Agent 실행 trace
- 감사 이벤트 기록
- Audit event JSONL/CSV export
- Operations summary API
- Evaluation run API
- expected facts 기반 답변 회귀 평가
- JSON evaluation dataset
- CI regression evaluation gate
- Postgres 기준 DB schema
- Docker Compose 기반 로컬 인프라
- ruff, mypy, pytest, GitHub Actions CI

기본 모드는 외부 서비스 없이 실행됩니다.  
설정만 바꾸면 같은 Port 경계 위에서 Postgres/Qdrant 모드로 전환됩니다.

## 제품 아키텍처

```text
FastAPI / n8n / MCP / CLI
        |
        v
Application Use Case
        |
        v
Domain Model / Policy
        |
        v
Port Interface
        |
        v
Adapter: Postgres, Vector DB, LLM, Tool Runtime, Observability
```

핵심 원칙은 업무 규칙과 외부 기술을 분리하는 것입니다.  
LLM, Vector DB, Workflow Tool, MCP 서버는 바뀔 수 있지만 Agent 실행 정책과 데이터 모델은 흔들리지 않아야 합니다.

## 기술 스택

| 영역 | 선택 |
| --- | --- |
| API | Python 3.12+, FastAPI |
| Application | Use Case orchestration |
| RAG | query classification, retrieval strategy, citation |
| Vector Search | local keyword adapter, Qdrant adapter |
| Persistence | in-memory adapter, Postgres adapter |
| Governance | PII redaction, policy guard, approval-required action |
| Tool Reliability | timeout, retry, fallback, gateway execution metadata |
| Observability | trace step, audit event |
| Infra | Docker Compose |
| Quality Gate | ruff, mypy, pytest, regression evaluation, GitHub Actions |

## 문서

- [제품 전략](docs/PRODUCT_STRATEGY.md)
- [아키텍처](docs/ARCHITECTURE.md)
- [디자인 패턴](docs/DESIGN_PATTERNS.md)
- [DB 설계](docs/DATABASE_DESIGN.md)
- [API 설계](docs/API_DESIGN.md)
- [ADR 0001: 헥사고날 아키텍처](docs/adr/0001-use-hexagonal-architecture.md)

## API

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

GET  /v1/operations/summary

POST /v1/evaluations/runs
GET  /v1/evaluations/runs/{evaluation_run_id}

GET  /v1/tools
POST /mcp
GET  /v1/approvals/pending
POST /v1/approvals/{approval_id}/approve
POST /v1/approvals/{approval_id}/reject
```

## 빠른 실행

```bash
make install
make dev
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## 로컬 기본 모드

`.env` 없이 실행하면 다음 모드로 동작합니다.

```text
STORAGE_BACKEND=memory
VECTOR_BACKEND=local
```

이 모드는 외부 DB 없이 API, 정책, 검색, 감사 이벤트 흐름을 검증하기 위한 모드입니다.

## 운영형 로컬 인프라

Postgres와 Qdrant를 함께 띄웁니다.

```bash
cp .env.example .env
docker compose up -d postgres qdrant redis
```

`.env`에서 저장소를 전환합니다.

```env
STORAGE_BACKEND=postgres
VECTOR_BACKEND=qdrant
POSTGRES_DSN=postgresql://ax_agent:ax_agent@localhost:5432/ax_agent
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=ax_agent_chunks
```

그 다음 API 서버를 실행합니다.

```bash
make dev
```

Postgres는 `db/migrations`의 초기 schema로 뜨고, Qdrant collection은 어댑터가 필요 시 생성합니다.

API 컨테이너까지 함께 띄울 때는 환경변수로 backend mode를 지정합니다.

```bash
STORAGE_BACKEND=postgres VECTOR_BACKEND=qdrant docker compose up --build api
```

## 사용 예시

문서 적재:

```bash
curl -X POST http://127.0.0.1:8000/v1/documents/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "title": "AX 거버넌스 플레이북",
    "content": "기업용 LLM Agent는 개인정보 마스킹, 권한 검사, 감사로그를 포함해야 한다. 삭제, 송금, 결제는 승인 후 실행한다.",
    "source_uri": "manual://ax-governance",
    "classification": "internal"
  }'
```

Agent 실행:

```bash
curl -X POST http://127.0.0.1:8000/v1/agents/runs \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "scenario": "operations",
    "message": "AX 전환 리스크와 거버넌스 기준을 정리해줘"
  }'
```

위험 action 차단:

```bash
curl -X POST http://127.0.0.1:8000/v1/agents/runs \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "scenario": "finance-ops",
    "message": "고객 계좌로 100만원 송금 실행해줘"
  }'
```

응답은 `approval_required` 정책 판단과 함께 실행을 차단합니다.

## Tool Runtime

Agent는 외부 시스템을 직접 변경하지 않습니다. 업무 실행 요청은 Tool Runtime을 거치며,
정책 결과에 따라 다음 상태로 남습니다.

Tool Runtime은 registry에 등록된 tool만 실행합니다.

| tool | action | required scope | risk |
| --- | --- | --- | --- |
| `internal-records.lookup` | `read` | `records:read` | low |
| `workflow.request-change` | `write` | `workflow:request` | high |

등록되지 않은 tool, 비활성화된 tool, action type이 맞지 않는 요청, required scope가 없는 요청은
`denied`로 처리됩니다.

| 결정 | 의미 |
| --- | --- |
| `allowed` | 조회성 또는 낮은 위험도의 작업으로 즉시 실행 가능 |
| `approval_required` | 외부 상태 변경이 필요한 작업으로 승인 대기 |
| `denied` | 정책상 실행 불가 |
| `not_required` | tool 실행이 필요 없는 질의 |

예를 들어 “정책 문서를 근거로 보고서 생성 요청을 처리해줘” 같은 요청은
`workflow.request-change` tool 요청으로 정규화되고, 쓰기성 작업이므로 `pending_approval` 상태로 남습니다.

응답에는 `tool_executions`가 포함됩니다.

```json
{
  "tool_name": "workflow.request-change",
  "action_type": "write",
  "decision": "approval_required",
  "status": "pending_approval"
}
```

같은 정보는 `tool.approval_required` 감사 이벤트로도 기록됩니다.

Tool catalog:

```bash
curl http://127.0.0.1:8000/v1/tools
```

## MCP-Compatible Tool Boundary

`/mcp`는 JSON-RPC 기반 tool discovery와 tool call 경계입니다.
등록된 tool은 `tools/list`로 노출되고, `tools/call`은 기존 Tool Runtime 정책을 그대로 통과합니다.

초기화:

```bash
curl -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "init-1",
    "method": "initialize"
  }'
```

Tool 목록:

```bash
curl -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "tools-1",
    "method": "tools/list"
  }'
```

Tool 호출:

```bash
curl -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

MCP 경유 호출도 `AgentRun`, `AuditEvent`로 남습니다. 쓰기성 high-risk tool은
scope가 있어도 즉시 실행하지 않고 `approval_requests`로 승격됩니다.

## Tool Gateway Reliability

외부 tool 호출은 `ResilientToolGateway`를 거칩니다.

```text
ToolRuntime
  -> ResilientToolGateway
  -> LocalToolGateway 또는 외부 Gateway Adapter
```

기본 정책:

- timeout을 초과한 호출은 실패한 attempt로 간주
- 일시적 오류는 설정된 횟수만큼 retry
- 모든 attempt가 실패하면 fallback 결과를 반환
- 실행 결과에는 `_gateway` metadata를 포함

예시:

```json
{
  "result": "fallback_result",
  "source": "internal-records.lookup",
  "_gateway": {
    "attempts": 2,
    "elapsed_ms": 34,
    "fallback_used": true,
    "error_message": "ConnectionError: gateway unavailable"
  }
}
```

이 구조에서는 외부 업무 시스템 장애가 Agent 프로세스 전체 장애로 번지지 않고,
실행 상태와 실패 원인이 tool execution 결과에 남습니다.

## Evaluation Runs

평가 API는 Agent 답변이 기대 사실을 포함하는지 측정합니다.

```bash
curl -X POST http://127.0.0.1:8000/v1/evaluations/runs \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "name": "운영 정책 회귀 평가",
    "scenario": "operations",
    "cases": [
      {
        "input_query": "Agent 운영 정책을 정리해줘",
        "expected_facts": ["개인정보 마스킹", "감사로그"]
      }
    ]
  }'
```

응답에는 케이스별 `score`, `failure_reason`, 전체 `average_score`, `pass_rate`,
`failed_count`가 포함됩니다. 평가 결과는 `evaluation_runs`, `evaluation_cases` 모델로
저장되며 `evaluation.completed` 감사 이벤트가 남습니다.

## Regression Gate

회귀 평가 dataset은 JSON 파일로 관리합니다.

```text
data/evaluation/regression_ko.json
```

로컬 실행:

```bash
make regression
```

`make verify`와 GitHub Actions CI도 같은 regression gate를 실행합니다.
기준 점수보다 `average_score`나 `pass_rate`가 낮으면 non-zero exit로 실패합니다.

## Approval Workflow

승인이 필요한 tool execution은 `approval_requests`로 승격됩니다. 운영자는 pending 목록을 조회하고,
승인 또는 반려 결정을 남길 수 있습니다.

```bash
curl http://127.0.0.1:8000/v1/approvals/pending?tenant_id=default
```

승인 실행:

```bash
curl -X POST http://127.0.0.1:8000/v1/approvals/{approval_id}/approve \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "approved_by": "operator-01"
  }'
```

승인 후 상태는 `executed`가 되고, `replay_result`가 남습니다. 이미 `executed` 상태인 승인 요청을
다시 승인하면 replay를 다시 실행하지 않고 기존 결과를 반환합니다.

반려 실행:

```bash
curl -X POST http://127.0.0.1:8000/v1/approvals/{approval_id}/reject \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "rejected_by": "operator-02",
    "reason": "요청 근거가 부족하여 실행하지 않습니다."
  }'
```

반려 후 상태는 `rejected`가 되고, 이후 approve 요청이 들어와도 replay를 실행하지 않습니다.
반려 결정은 `approval.rejected` 감사 이벤트로 남습니다.

## 품질 검증

```bash
make verify
```

개별 실행:

```bash
make lint
make typecheck
make test
make regression
```

CI도 같은 검증을 수행합니다.

## Audit Export

감사 이벤트는 조회뿐 아니라 JSONL/CSV로 export할 수 있습니다.

```bash
curl "http://127.0.0.1:8000/v1/audit/export?tenant_id=default&event_type=document.ingested&format=jsonl"
```

CSV:

```bash
curl "http://127.0.0.1:8000/v1/audit/export?tenant_id=default&resource_type=agent_run&format=csv"
```

지원 필터:

- `event_type`
- `resource_type`
- `limit`

export 결과에는 `id`, `tenant_id`, `actor_type`, `actor_id`, `event_type`, `resource_type`,
`resource_id`, `payload`, `created_at`이 포함됩니다.

## Operations Summary

운영 요약 API는 대시보드가 필요한 핵심 지표를 한 번에 반환합니다.

```bash
curl "http://127.0.0.1:8000/v1/operations/summary?tenant_id=default"
```

포함 지표:

- 문서 수
- pending approval 수
- Agent 실행 수
- 평균 latency/confidence
- event type별 count
- tool decision별 count
- approval 상태별 count
- gateway fallback count
- 최신 evaluation metrics

## 데이터 모델 핵심

```text
tenants
  ├─ users
  ├─ documents
  │    └─ document_chunks
  ├─ agent_runs
  │    ├─ retrieval_events
  │    ├─ tool_calls
  │    ├─ approval_requests
  │    └─ agent_messages
  ├─ evaluation_runs
  │    └─ evaluation_cases
  └─ audit_events
```

RDB와 Vector DB의 책임을 분리합니다.

| 저장소 | 책임 |
| --- | --- |
| Postgres | 업무 원장, 문서 메타데이터, 실행 이력, 감사 이벤트 |
| Vector DB | 유사도 검색용 임베딩 인덱스 |

## 운영 관점에서 중요한 설계

- raw prompt가 아니라 구조화된 trace를 남긴다.
- 답변에는 citation과 confidence를 포함한다.
- 개인정보는 LLM context 구성 전에 마스킹한다.
- 위험 action은 자동 실행하지 않고 승인 필요 상태로 차단한다.
- tool call은 추론 과정 안에 숨기지 않고 별도 이벤트로 남긴다.
- Vector DB는 재생성 가능한 파생 인덱스로 취급한다.

## 다이어그램

- [시스템 컨텍스트](docs/diagrams/system-context.mmd)
- [Agent 실행 시퀀스](docs/diagrams/agent-run-sequence.mmd)

## 로드맵

### 1단계: Agentic RAG Runtime

- 문서 적재
- chunking
- 질문 유형 분류
- 검색 전략 선택
- 근거 기반 답변
- trace/audit

### 2단계: 운영형 Persistence

- Postgres repository
- Qdrant vector adapter
- Docker Compose schema bootstrap
- backend mode 전환

### 3단계: Tool Runtime

- MCP-compatible JSON-RPC boundary
- tool schema와 권한 scope
- Tool Gateway 실행 어댑터
- timeout/retry/fallback 실행 안정성
- 승인 워크플로우
- 승인 반려와 감사 이벤트
- tool call audit
- 승인 후 replay와 중복 실행 방지

### 4단계: LLMOps

- evaluation dataset
- regression test
- evaluation run API
- cost/latency metrics

### 5단계: Workflow Product

- n8n 연동
- Slack 승인 플로우
- 운영자 dashboard
- 감사 이벤트 export

## 라이선스

MIT License
