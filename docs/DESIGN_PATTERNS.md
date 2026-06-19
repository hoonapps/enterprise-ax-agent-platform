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
- Resilient Gateway는 timeout, retry, fallback을 공통으로 처리한다.
- Gateway Adapter는 외부 시스템 호출과 응답 정규화에 집중한다.
- MCP, 사내 API, workflow engine은 Gateway 어댑터만 교체해서 붙일 수 있다.

`ToolGatewayResult`에는 `attempts`, `elapsed_ms`, `fallback_used`, `error_message`가 포함된다.
Runtime은 이 정보를 tool execution의 `_gateway` metadata로 남긴다.
