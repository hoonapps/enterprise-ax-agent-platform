# 디자인 패턴

이 프로젝트의 패턴 사용 기준은 “면접에서 설명 가능한가”와 “실제 기업 Agent 시스템에 필요한가”다.

## 1. Hexagonal Architecture

LLM, Vector DB, MCP, n8n, SaaS API는 빠르게 바뀐다.  
도메인과 유스케이스가 특정 벤더 SDK에 묶이면 유지보수하기 어렵다.

따라서 다음 포트를 둔다.

- `DocumentRepositoryPort`
- `VectorSearchPort`
- `AuditLogPort`
- `AgentRunRepositoryPort`
- 이후 확장: `ToolRegistryPort`, `McpClientPort`, `WorkflowPort`

현재는 로컬 메모리 어댑터로 실행하고, 이후 Postgres/Qdrant/MCP로 교체한다.

## 2. Use Case Pattern

외부에서 의미 있는 행위는 유스케이스로 분리한다.

| 유스케이스 | 역할 |
| --- | --- |
| `IngestDocumentUseCase` | 문서 적재, 청크 분리, 벡터 저장, 감사 이벤트 기록 |
| `RunAgentUseCase` | Agent 실행 전체 흐름 orchestration |
| `SearchKnowledgeUseCase` | 검색 API와 검색 감사 이벤트 처리 |
| `EvaluateAnswerUseCase` | 이후 RAG 품질 평가 확장 |

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

이 구조는 LG CNS의 A-RAG, 삼성SDS의 RAG 전략 자동 선택과 직접 연결된다.

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

면접 포인트는 “처음부터 DB를 붙였는가”보다 “저장소 교체 경계가 있는가”다.

## 6. Domain Event / Audit Event

Agent 시스템은 나중에 왜 그런 답을 했는지 설명할 수 있어야 한다.

그래서 주요 실행 지점을 이벤트로 남긴다.

- `document.ingested`
- `retrieval.executed`
- `agent.answer.generated`
- 이후 확장: `tool.allowed`, `tool.denied`, `policy.redaction.applied`

이벤트는 나중에 Langfuse, OpenTelemetry, SIEM, 관리자 대시보드로 보낼 수 있다.

## 7. Anti-Corruption Layer

ERP, HR, CRM, Slack, n8n, MCP 도구 응답은 시스템마다 형식이 다르다.  
Agent 내부로 외부 응답을 그대로 흘리면 전체 코드가 외부 시스템 형식에 오염된다.

따라서 tool 응답은 내부 표준 형태로 정규화한다.

```text
External API Response -> Tool Adapter -> Normalized Tool Result -> Agent Context
```

이 구조는 무신사식 SaaS/API 자동화와 현대오토에버식 MCP 연동을 동시에 수용한다.

## 8. Fail-Safe Default

기업형 Agent는 실패해도 안전해야 한다.

- LLM 키가 없어도 로컬 모드로 실행
- 근거가 없으면 답변을 보류
- 쓰기 작업은 정책 검사 통과 전 실행하지 않음
- 민감정보는 LLM context에 넣기 전에 제거
- 모든 실행 결과에 trace와 citation을 포함
