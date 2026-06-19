# 디자인 패턴

이 프로젝트의 패턴 사용 기준은 “운영 가능한 Agent 시스템에 실제로 필요한가”다.

## 1. Hexagonal Architecture

LLM, Vector DB, MCP, n8n, SaaS API는 빠르게 바뀐다.  
도메인과 유스케이스가 특정 벤더 SDK에 묶이면 유지보수하기 어렵다.

따라서 다음 포트를 둔다.

- `DocumentRepositoryPort`
- `VectorSearchPort`
- `AuditLogPort`
- `AgentRunRepositoryPort`
- `ToolRegistryPort`
- `ToolGatewayPort`
- 이후 확장: `McpClientPort`, `WorkflowPort`

현재는 로컬 메모리/로컬 gateway 어댑터로 실행하고, 이후 Postgres/Qdrant/외부 tool gateway로 교체한다.
Gateway는 `ResilientToolGateway`로 감싸 timeout, retry, fallback 정책을 공통 적용한다.

## 2. Use Case Pattern

외부에서 의미 있는 행위는 유스케이스로 분리한다.

| 유스케이스 | 역할 |
| --- | --- |
| `IngestDocumentUseCase` | 문서 적재, 청크 분리, 벡터 저장, 감사 이벤트 기록 |
| `RunAgentUseCase` | Agent 실행 전체 흐름 orchestration |
| `SearchKnowledgeUseCase` | 검색 API와 검색 감사 이벤트 처리 |
| `ToolCallUseCase` | MCP 경유 tool call의 정책, 감사, 승인 흐름 처리 |
| `EvaluateAgentUseCase` | Agent 답변 회귀 평가, 케이스별 scoring, 평가 감사 이벤트 처리 |
| `AgentScenarioUseCase` | 운영 시나리오 단위로 여러 Agent 실행을 묶고 step별 통과 기준 평가 |

FastAPI 라우터는 얇게 유지한다.  
이렇게 하면 HTTP 서버 없이도 핵심 로직을 단위 테스트할 수 있다.

## 3. Strategy Pattern

RAG는 하나의 검색 방식으로 끝나지 않는다. 질문 유형에 따라 전략이 달라져야 한다.

| 질문 유형 | 검색 전략 |
| --- | --- |
| `factual` | 정확 질의 중심 top-k 검색 |
| `summary` | 넓은 문맥 검색 후 요약 |
| `compare` | 복수 문서 비교 검색 |
| `action` | 업무 실행 전 근거 검색 + tool 가능 여부 확인 |
| `risk` | 보안/정책/장애 관점 검색 |

이 구조는 Agentic RAG와 RAG 전략 자동 선택을 구현하기 위한 기반이다.

## 4. Policy Guard

Agent 실행 전후에 정책 검사를 넣는다.

```text
입력 -> 개인정보 마스킹 -> 질문 분류 -> 정책 검사 -> 검색/실행 -> 감사로그
```

중요한 점은 정책이 README에만 있는 것이 아니라 런타임 코드로 존재한다는 것이다.

현재 MVP 정책:

- 이메일, 전화번호, 주민등록번호 패턴 마스킹
- 삭제/송금/결제/퇴사처리 같은 위험 action은 승인 필요 상태로 차단
- 차단된 요청도 감사 이벤트로 기록

## 5. Repository Pattern

도메인 로직은 저장 방식에 의존하지 않는다.

현재:

```text
InMemoryDocumentRepository
InMemoryAgentRunRepository
InMemoryAuditLog
LocalKeywordVectorSearch
```

확장:

```text
PostgresDocumentRepository
PostgresAgentRunRepository
PostgresAuditLog
QdrantVectorSearch
```

중요한 점은 “처음부터 특정 DB에 고정했는가”가 아니라 “저장소 교체 경계가 있는가”다.
Postgres adapter는 runtime role로 접속하고 connection마다 `app.tenant_id`를 설정해 Row Level
Security policy와 application-level tenant guard를 함께 적용한다.

## 6. Domain Event / Audit Event

Agent 시스템은 나중에 왜 그런 답을 했는지 설명할 수 있어야 한다.

그래서 주요 실행 지점을 이벤트로 남긴다.

- `document.ingested`
- `retrieval.executed`
- `agent.answer.generated`
- `evaluation.completed`
- `approval.rejected`
- 이후 확장: `tool.allowed`, `tool.denied`, `policy.redaction.applied`

이벤트는 나중에 Langfuse, OpenTelemetry, SIEM, 관리자 대시보드로 보낼 수 있다.

Audit export는 같은 이벤트 모델을 JSONL/CSV로 직렬화한다.
조회 API와 export API가 같은 `AuditLogPort` 필터를 사용하므로 저장소가 바뀌어도 동작 의미가 유지된다.
Agent run export도 같은 원칙을 따른다. 목록 조회와 같은 필터를 사용하고, 기본 export에서는 원문 query와
답변 본문을 제외해 운영 분석과 데이터 최소화 원칙을 함께 만족한다.

## 7. Anti-Corruption Layer

ERP, HR, CRM, Slack, n8n, MCP 도구 응답은 시스템마다 형식이 다르다.  
Agent 내부로 외부 응답을 그대로 흘리면 전체 코드가 외부 시스템 형식에 오염된다.

따라서 tool 응답은 내부 표준 형태로 정규화한다.

```text
External API Response -> Tool Adapter -> Normalized Tool Result -> Agent Context
```

이 구조는 SaaS/API 자동화와 MCP 기반 내부 도구 연동을 동시에 수용한다.

## 8. Tool Registry

Tool 실행은 문자열 이름만으로 처리하지 않는다. Registry에 등록된 tool만 실행 대상이 된다.

Registry는 다음 정보를 가진다.

- tool name
- action type
- required scope
- risk level
- input schema
- output schema
- enabled flag

이 정보가 있어야 운영자가 어떤 tool이 어떤 권한으로 실행될 수 있는지 확인할 수 있다.

## 9. Fail-Safe Default

기업형 Agent는 실패해도 안전해야 한다.

- LLM 키가 없어도 로컬 모드로 실행
- 근거가 없으면 답변을 보류
- 쓰기 작업은 정책 검사 통과 전 실행하지 않음
- 민감정보는 LLM context에 넣기 전에 제거
- 모든 실행 결과에 trace와 citation을 포함

## 10. Tool Gateway

Tool Runtime은 정책과 승인 결정을 담당하고, 실제 외부 시스템 호출은 Gateway가 담당한다.

```text
ToolCallUseCase
  -> ToolRuntime
  -> ResilientToolGateway
  -> ToolGatewayPort
  -> LocalToolGateway
```

이 분리는 중요하다.

- Runtime은 등록/권한/위험도/승인 판단에 집중한다.
- Resilient Gateway는 timeout, retry, fallback, circuit breaker를 공통으로 처리한다.
- Gateway Adapter는 외부 시스템 호출과 응답 정규화에 집중한다.
- MCP, 사내 API, workflow engine은 Gateway 어댑터만 교체해서 붙일 수 있다.

`ToolGatewayResult`에는 `attempts`, `elapsed_ms`, `fallback_used`, `error_message`,
`circuit_state`, `circuit_open_remaining_ms`가 포함된다.
Runtime은 이 정보를 tool execution의 `_gateway` metadata로 남긴다.
현재 tool별 circuit 상태는 `/v1/tools/gateway/status` read model로 노출한다. 실행 결과 메타데이터는
단건 trace 분석에 쓰고, gateway status API는 운영자가 현재 차단 중인 tool을 식별하는 데 사용한다.

## 11. Regression Gate

Evaluation API와 CI gate는 같은 유스케이스를 사용한다.

```text
JSON Dataset -> EvaluateAgentUseCase -> EvaluationRepository -> Metrics Gate
```

API와 CI가 다른 평가 로직을 갖지 않도록 분리했다.

- API는 운영자가 ad-hoc 평가를 실행하는 경계다.
- `scripts/run_regression_eval.py`는 CI에서 같은 use case를 실행하는 경계다.
- dataset은 `minimum_average_score`, `minimum_pass_rate`를 가진다.
- 기준 미달 시 CI를 실패시킨다.

## 12. Read Model

운영 요약 API는 쓰기 모델을 새로 만들지 않고 기존 이벤트와 원장에서 읽기 모델을 계산한다.

```text
DocumentRepositoryPort
ApprovalRepositoryPort
AuditLogPort
  -> OperationsSummaryUseCase
  -> /v1/operations/summary
```

이 방식은 dashboard가 필요한 데이터 계약을 빠르게 고정하면서도,
나중에 Postgres materialized view나 metrics table로 교체할 여지를 남긴다.
`OperationsSloUseCase`도 같은 원칙을 따른다. Agent 실행 이벤트를 읽어 success rate, p95 latency,
error budget을 계산하되, 별도 쓰기 모델을 만들지 않는다.
`OperationsIncidentSnapshotUseCase`는 여러 read model을 조합하는 facade 역할을 하며, 저장된 incident
테이블 없이도 운영자가 볼 원인 후보와 권장 조치를 계산한다.
`AgentFeedbackUseCase`는 feedback 제출을 `agent.feedback.submitted` 감사 이벤트로 남기고, 별도
summary read model에서 rating과 outcome을 집계한다.

## 13. Scenario Catalog

운영자는 단일 Agent run보다 반복 가능한 업무 흐름을 검증해야 하는 경우가 많다. 예를 들어 release
readiness는 지식 질의, 거버넌스 질의, 승인 필요 workflow 실행을 함께 확인해야 한다.

```text
Scenario Definition
  -> Step 1 Agent Run
  -> Step 2 Agent Run
  -> Step 3 Agent Run
  -> Step Check
  -> agent.scenario.executed AuditEvent
```

Scenario는 별도 workflow engine을 만들지 않고 기존 `RunAgentUseCase`를 조합한다.
각 step은 기대 query type, citation 필요 여부, 최소 confidence, approval 필요 여부를 가진다.
이 결과는 release 전 smoke test, 운영 점검, incident triage 같은 반복 실행 단위로 사용할 수 있다.

## 14. Quota Guard

Agent 실행량 제한은 Router가 아니라 UseCase 초입에서 처리한다.

```text
RunAgentUseCase
  -> AgentRunRepositoryPort.count_runs_between()
  -> quota_guard trace step
  -> blocked AgentRun
  -> agent.quota.exceeded audit event
```

이 구조는 API, MCP, evaluation 등 여러 진입점이 같은 실행 정책을 공유하게 만든다.
운영 화면은 `/v1/operations/usage` read model을 읽어 guard와 동일한 기준의 월간 사용률을 표시한다.

`POST /v1/agents/runs/preview`는 같은 guard와 policy를 호출하지만, run 저장이나 audit append를 하지
않는다. 실행 전 검토 API와 실제 실행 API가 정책 컴포넌트를 공유하도록 만든다.

## 15. Backend-Served Operator Console

운영 콘솔은 제품의 핵심 쓰기 흐름과 분리된 얇은 UI 경계다.

```text
GET /dashboard
  -> HTML shell
  -> browser fetch
  -> /v1/operations/summary, /v1/approvals/pending, /v1/audit/events, /v1/tools
  -> /v1/agents/runs/{run_id}/diagnostics
  -> /v1/agents/runs/{run_id}/replay
  -> /v1/tools/gateway/status
  -> /v1/scenarios, /v1/scenarios/runs, /v1/scenarios/{scenario_id}/run
  -> 승인/반려 action은 approval API 호출
```

대시보드는 다음 원칙을 따른다.

- 화면 전용 상태 저장소를 두지 않는다.
- 운영 지표는 `OperationsSummaryUseCase`가 만든 read model을 사용한다.
- 승인 실행/반려 같은 변경은 기존 API로 처리한다.
- 반복 검증은 scenario catalog API를 호출하고 결과 run은 기존 timeline/diagnostics로 추적한다.
- 화면은 Agent runtime의 내부 구현이 아니라 공개 API 계약에 의존한다.

이 구조는 React 같은 별도 프론트엔드가 붙어도 유지된다. 기존 dashboard는 API 계약 검증용
운영 콘솔로 남고, 더 복잡한 화면은 같은 read model 위에서 확장할 수 있다.

## 16. API Key Scope Guard

HTTP API 접근 권한은 Agent tool 실행 권한과 분리한다.

```text
X-API-Key
  -> AuthPrincipal(actor_id, scopes, tenant_ids)
  -> require_scopes("operations:read")
  -> require_tenant_access("default")
  -> Router
  -> Use Case
```

이 패턴의 목적은 두 가지다.

- endpoint를 호출할 수 있는 주체를 제한한다.
- key가 접근할 수 있는 tenant를 제한한다.
- Agent가 tool을 실행할 수 있는지는 tool runtime에서 별도로 판단한다.

예를 들어 `agents:run` scope가 있는 API key는 Agent 실행 endpoint를 호출할 수 있다.
하지만 request의 `actor_scopes`에 `workflow:request`가 없으면 쓰기성 workflow tool은 실행되지 않는다.

기본 로컬 모드는 `AUTH_ENABLED=false`로 둔다. 외부 DB 없이 빠르게 실행해도 되지만,
운영형 로컬 환경에서는 `AUTH_ENABLED=true`와 `API_KEY_CREDENTIALS`로 같은 API를 보호할 수 있다.
credential의 `@tenant-a|tenant-b` suffix로 허용 tenant를 지정할 수 있다.

## 17. Idempotency Repository

재시도 가능한 쓰기 API는 `Idempotency-Key`를 처리한다.

```text
HTTP Request
  -> canonical request hash
  -> IdempotencyRepositoryPort.get(tenant_id, key)
  -> replay / conflict / execute
  -> IdempotencyRepositoryPort.save(response)
```

이 패턴의 핵심은 “중복 요청을 알아보는 책임”을 라우터에 두되,
저장 방식은 port로 분리하는 것이다.

- `InMemoryIdempotencyRepository`: 로컬 실행과 테스트용
- `PostgresIdempotencyRepository`: `idempotency_keys` 테이블 사용

같은 key로 같은 payload가 들어오면 저장된 응답을 replay한다.
같은 key로 다른 payload가 들어오면 `409 Conflict`를 반환한다.

승인 replay 멱등성과는 책임이 다르다. `Idempotency-Key`는 HTTP write API 재시도 중복을 막고,
approval replay는 승인 이후 외부 tool 실행 중복을 막는다.

## 18. Ontology Read Model

문서 적재 use case는 검색 청크와 별도로 ontology graph read model을 업데이트한다.

```text
Document
  -> TextChunker -> VectorSearchPort
  -> OntologyExtractor -> OntologyRepositoryPort
  -> GET /v1/ontology/graph
```

이 패턴의 목적은 RAG 검색 인덱스와 업무 개념 탐색 모델을 분리하는 것이다.

- Vector DB는 유사도 검색을 담당한다.
- Ontology graph는 문서, 분류, metadata, concept 관계를 조회 가능하게 만든다.
- Extractor는 현재 결정론적 규칙 기반이지만, 나중에 LLM entity extraction으로 교체할 수 있다.
- Repository는 메모리/Postgres 구현을 제공하고, 이후 Neo4j 같은 graph backend로 확장할 수 있다.

## 19. Webhook Outbox

감사 이벤트와 외부 workflow 전송은 분리한다.

```text
AuditEvent
  -> OutboxAuditLog
  -> AuditLogPort.append
  -> WebhookSubscription match
  -> WebhookDelivery(status=pending)
  -> WebhookDispatcher
     -> signed HTTP POST
     -> delivered / failed
```

이 패턴은 외부 시스템 장애가 Agent 실행 경로에 전파되는 것을 막는다.

- audit event는 source of truth로 먼저 저장한다.
- subscription은 어떤 event type을 외부 workflow로 보낼지 정의한다.
- delivery는 pending/delivered/failed 상태를 가진 재처리 가능한 작업 단위다.
- dispatcher는 HMAC signature, timeout, retry backoff 상태를 처리한다.
- 단건 API와 배치 worker는 같은 dispatcher를 재사용해 상태 전이 규칙을 한 곳에 둔다.
- 배치 worker는 먼저 `dispatching` 상태로 delivery를 claim하고, lease 시간 동안 소유권을 갖는다.
- Postgres adapter는 `FOR UPDATE SKIP LOCKED`로 여러 worker의 중복 claim을 막는다.
- lease가 만료된 `dispatching` delivery는 다시 claim 대상이 되어 worker 중단 후에도 복구된다.
- 최대 재시도 횟수를 넘은 delivery는 `dead_letter`로 분리해 자동 재시도 폭주를 막는다.
- 수동 retry는 상태와 attempt count를 초기화해 운영자가 원인 조치 후 다시 큐에 넣는 동작이다.

## 20. Request Context Audit Enrichment

HTTP request context와 audit event를 연결한다.

```text
RequestContextMiddleware
  -> current_request_id()
  -> RequestContextAuditLog
  -> AuditEvent.payload.request_id
  -> WebhookDelivery.payload.payload.request_id
```

이 패턴은 use case가 HTTP 헤더를 알지 않게 하면서도, 운영 추적에 필요한 correlation id를
감사 이벤트와 외부 workflow payload에 포함한다.

- middleware는 `X-Request-ID`를 읽거나 생성한다.
- `ContextVar`는 같은 요청 처리 흐름 안에서 request id를 보관한다.
- `RequestContextAuditLog`는 AuditLogPort decorator로 동작한다.
- 이미 payload에 `request_id`가 있으면 덮어쓰지 않는다.
- HTTP 요청 밖에서 생성된 이벤트는 request id 없이 기록될 수 있다.
- audit event 조회와 export는 `request_id` 필터를 지원한다.
- Postgres adapter는 `payload ->> 'request_id'` expression index로 필터 비용을 낮춘다.

## 21. Compatible Error Envelope

오류 응답은 기존 FastAPI `detail` 계약을 유지하면서 request id만 추가한다.

```json
{
  "detail": "Agent 실행 이력을 찾을 수 없습니다.",
  "request_id": "error-trace-001"
}
```

이 패턴은 클라이언트 호환성과 운영 추적성을 동시에 지키기 위한 것이다.

- `HTTPException.detail`은 그대로 둔다.
- validation error의 `detail` list도 그대로 둔다.
- response body에는 `request_id`를 추가한다.
- response header의 `X-Request-ID`와 body의 `request_id`는 같은 값이다.
- 500 오류는 내부 예외를 노출하지 않고 `"Internal Server Error"`만 반환한다.
