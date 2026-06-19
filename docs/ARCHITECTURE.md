# 아키텍처

## 목표

`Enterprise AX Agent Platform`은 LLM Agent를 기업 업무 시스템에 붙일 때 필요한
백엔드 실행 계층을 검증하는 제품이다.

단순 챗봇이 아니라 다음 운영 요건을 만족하는 것을 목표로 한다.

- 업무 유스케이스 중심의 서비스 경계 설계
- RAG, Tool Calling, 정책 검사, 감사로그의 실행 흐름 분리
- LLM/Vector DB/MCP/n8n 같은 외부 기술을 교체 가능한 어댑터로 격리
- 개인정보 마스킹, 권한, 승인, 추적성을 고려한 Agent 실행 구조
- 장애 분석과 품질 개선이 가능한 실행 이력/평가 데이터 모델

## 설계 스타일

전체 구조는 실용적인 헥사고날 아키텍처를 따른다.

```text
FastAPI / Dashboard / n8n / MCP / CLI
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

핵심 원칙은 간단하다.

> 업무 규칙과 정책 판단은 프레임워크와 LLM SDK 바깥에 둔다.

FastAPI는 입출력 계층이고, LangGraph/OpenAI/Qdrant/Postgres는 어댑터다.  
Agent가 똑똑해 보이는 것보다, Agent가 **어떤 정책과 데이터 경계 안에서 실행되는지**가 더 중요하다.

## 런타임 구조

```text
사용자 / 업무 워크플로우 / 운영 콘솔
    |
    | REST API
    v
FastAPI
    |
    +--> RequestContextMiddleware
    |       |
    |       +--> X-Request-ID echo/generate
    |       +--> X-Process-Time-Ms response header
    |       +--> request scoped log context
    |       +--> AuditEvent payload request_id
    |       +--> WebhookDelivery payload request_id
    |
    +--> ExceptionHandlers
    |       |
    |       +--> detail 호환 오류 응답
    |       +--> response body request_id
    |
    +--> API Key Auth / HTTP Scope Guard
    |
    +--> Agent 실행 유스케이스
    |       |
    |       +--> 질문 유형 분류
    |       +--> RAG 검색 전략 선택
    |       +--> 정책 사전 검사
    |       +--> 문서 검색
    |       +--> 근거 기반 답변 생성
    |       +--> Tool Runtime 정책 결정
    |       +--> Tool Schema / Scope 검사
    |       +--> 승인 요청 생성
    |       +--> 감사 이벤트 기록
    |
    +--> 문서 적재 유스케이스
    |       |
    |       +--> 문서 정규화
    |       +--> 청크 분리
    |       +--> 임베딩/벡터 저장
    |       +--> Ontology graph 추출/저장
    |       +--> 문서 메타데이터 저장
    |
    +--> 검색/평가/감사/운영 조회 API
    |       |
    |       +--> EvaluationRun 생성
    |       +--> Agent 실행 재사용
    |       +--> expected facts 기반 scoring
    |       +--> evaluation.completed 감사 이벤트 기록
    |       +--> AuditEvent JSONL/CSV export
    |       +--> OperationsSummary 집계
    |       +--> Webhook delivery outbox 조회
    +--> 승인 요청 조회/승인/반려 API
    +--> Operator Dashboard
    |       |
    |       +--> OperationsSummary API
    |       +--> Approval pending API
    |       +--> Approval approve/reject API
    |       +--> Audit events API
    |       +--> Tool catalog API
    |       +--> Tool gateway status API
    +--> MCP-compatible tool boundary
            |
            +--> tools/list
            +--> tools/call
            +--> ToolCallUseCase
            +--> AgentRun / AuditEvent / ApprovalRequest 기록
```

## 모듈 책임

| 모듈 | 책임 | 백엔드 관점의 의미 |
| --- | --- | --- |
| `domain` | 엔티티, 값 객체, 정책 | 업무 규칙을 프레임워크와 분리 |
| `application` | 유스케이스 orchestration | API 없이도 테스트 가능한 서비스 흐름 |
| `adapters/http` | REST API 입출력 | FastAPI 의존성 격리 |
| `adapters/persistence` | 저장소 구현 | Postgres 전환 가능한 Repository 경계 |
| `adapters/vector` | 임베딩/검색 | Qdrant, pgvector, Pinecone 교체 가능 |
| `adapters/agent` | LLM/LangGraph 실행 | Agent 프레임워크 교체 가능 |
| `security` | 마스킹, 정책, 권한 | 기업형 AX의 거버넌스 경계 |
| `observability` | trace, audit, metric | 장애 분석과 품질 개선 기반 |

## Agent 실행 흐름

```text
POST /v1/agents/runs
  -> X-API-Key 인증
  -> agents:run HTTP scope 확인
  -> 요청 검증
  -> Idempotency-Key replay 가능 여부 확인
  -> 개인정보 마스킹
  -> 질문 유형 분류
  -> 검색 전략 선택
  -> 정책 사전 검사
  -> 벡터 검색
  -> 근거 기반 답변 생성
  -> tool 실행 필요 시 Tool Runtime 호출
  -> registry에서 tool schema와 required scope 확인
  -> 허용된 조회성 tool은 Resilient Tool Gateway 호출
  -> timeout/retry/fallback/circuit breaker 결과를 tool execution에 기록
  -> approval_required tool은 승인 요청으로 승격
  -> 실행 이력 저장
  -> 감사 이벤트 기록
  -> Idempotency-Key 응답 저장
  -> 답변 + 출처 + trace 반환
```

이 흐름은 Agentic RAG, RAG 전략 자동 선택, 운영 가능한 Agent runtime을 동시에 수용하도록 설계했다.

```text
POST /v1/agents/runs/preview
  -> X-API-Key 인증
  -> agents:run HTTP scope 확인
  -> 개인정보 마스킹
  -> 질문 유형 분류
  -> 월간 quota 확인
  -> 검색 전략 선택
  -> 정책 사전 검사
  -> 예상 tool route 계산
  -> 실행 이력과 감사 이벤트 저장 없이 preview 반환
```

preview는 실제 실행 전 dry-run 경계다. 실행 저장소, 검색 실행, tool runtime을 호출하지 않고 같은
정책/분류/검색 계획 컴포넌트로 요청의 실행 경로만 계산한다.

## Agent 실행 이력 조회

```text
GET /v1/agents/runs
  -> agents:read HTTP scope 확인
  -> tenant 접근 권한 확인
  -> scenario/status/query_type 필터 적용
  -> 최신 실행순 summary 반환

GET /v1/agents/runs/{run_id}/timeline
  -> AgentRun 단건 조회
  -> trace step을 timeline item으로 변환
  -> tool execution을 timeline item으로 변환
  -> 관련 audit event를 timeline item으로 변환
  -> sequence 기준으로 정렬해 반환

GET /v1/agents/runs/{run_id}/diagnostics
  -> AgentRun 단건 조회
  -> 관련 audit event와 feedback event 수집
  -> confidence, citation, trace, gateway, approval, feedback signal 계산
  -> quality_score, severity, recommended_actions 반환

GET /v1/agents/runs/{run_id}/evidence
  -> AgentRun 단건 조회
  -> 관련 audit event와 feedback event 수집
  -> timeline read model 생성
  -> 핵심 payload를 canonical JSON으로 직렬화
  -> SHA-256 evidence_hash와 함께 반환

POST /v1/agents/runs/{run_id}/feedback
  -> AgentRun 단건 조회
  -> rating/outcome/comment/tags 검증
  -> agent.feedback.submitted audit event 기록
  -> feedback response 반환
```

실행 이력 목록은 상세 답변 API와 분리한다.
운영 화면에서는 원문 query와 전체 답변 대신 `redacted_query_preview`, 상태, query type, confidence,
trace/tool/citation 개수를 조회한다.
Timeline은 단일 실행의 내부 진행과 외부 감사 이벤트를 한 응답에서 확인하는 drill-down read model이다.
Diagnostics는 같은 원장을 읽지만 운영 판단을 위해 위험 신호와 권장 조치를 계산하는 read model이다.
Evidence bundle은 run 상세, timeline, audit event, feedback event를 한 응답으로 묶어 장애 분석이나
감사 대응 시 실행 단위의 증거를 재조회할 수 있게 한다.

HTTP scope와 Agent tool scope는 다르다.

- HTTP scope는 API endpoint 접근을 제어한다.
- Agent tool scope는 Agent가 외부 tool을 실행할 수 있는지 제어한다.

따라서 `agents:run`이 있어도 `workflow:request`가 없으면 쓰기성 tool 실행은 거부된다.

## 문서 적재 흐름

```text
POST /v1/documents/ingest
  -> 문서 출처/등급 검증
  -> content hash 생성
  -> 청크 분리
  -> chunk metadata 구성
  -> 벡터 저장소 upsert
  -> OntologyExtractor로 concept/metadata/relation 추출
  -> OntologyRepositoryPort upsert
  -> 문서/청크 메타데이터 저장
  -> 감사 이벤트 기록
```

문서 원본과 검색 청크를 분리한 이유는 명확하다.

- 원본 문서는 업무/컴플라이언스 단위다.
- 청크는 검색/임베딩 단위다.
- ontology graph는 운영자가 업무 개념과 문서 관계를 탐색하기 위한 read model이다.
- 벡터 DB는 파생 데이터이며, 원본 메타데이터의 source of truth는 RDB다.

## Ontology Graph 흐름

```text
Document
  -> OntologyExtractor
     -> document node
     -> classification node
     -> metadata node
     -> concept node
     -> mentions / classified_as / has_metadata / co_occurs_with edge
  -> OntologyRepositoryPort
  -> GET /v1/ontology/graph
```

현재 extractor는 외부 LLM 없이 동작하는 결정론적 규칙 기반 구현이다.
이 경계 덕분에 나중에 LLM 기반 entity extraction이나 Neo4j adapter로 교체해도 API 계약은 유지된다.

## Evaluation 실행 흐름

```text
POST /v1/evaluations/runs
  -> 평가 케이스 검증
  -> 각 케이스별 Agent 실행
  -> 답변과 expected facts 비교
  -> case score와 failure reason 계산
  -> aggregate metrics 계산
  -> evaluation_runs / evaluation_cases 저장
  -> evaluation.completed 감사 이벤트 기록
```

로컬 답변 생성기는 검색된 근거 문장을 포함하도록 결정론적으로 동작한다.
따라서 외부 LLM 키 없이도 evaluation run을 회귀 테스트로 사용할 수 있다.

## Regression Gate 흐름

```text
make regression
  -> data/evaluation/regression_ko.json 로드
  -> data/sample_docs 문서 적재
  -> EvaluateAgentUseCase 실행
  -> average_score / pass_rate 기준 확인
  -> 기준 미달 시 non-zero exit
```

GitHub Actions는 lint, typecheck, pytest 이후 regression gate를 실행한다.
이 흐름은 retrieval, answer synthesis, scoring 변경이 제품 품질을 낮추는지 확인한다.

## Audit Export 흐름

```text
GET /v1/audit/export
  -> tenant/event/resource filter 적용
  -> AuditLogPort에서 이벤트 조회
  -> JSONL 또는 CSV로 직렬화
  -> 운영 분석/감사 시스템으로 전달
```

export는 조회 API와 같은 AuditLogPort를 사용한다.
따라서 메모리 모드와 Postgres 모드가 같은 필터 규칙을 따른다.

## Webhook Outbox 흐름

```text
Use Case
  -> AuditLogPort.append(event)
  -> OutboxAuditLog
     -> inner AuditLogPort.append(event)
     -> matching WebhookSubscription 조회
     -> WebhookDelivery pending 생성
  -> WebhookDispatcher가 delivery 전송
     -> X-AX-* 헤더와 HMAC signature 구성
     -> timeout 적용
     -> 2xx면 delivered
     -> 실패면 failed + next_attempt_at 기록
  -> delivered / failed 상태 기록
```

감사 이벤트 저장과 외부 workflow 전송을 분리한다.
따라서 n8n, Slack, 내부 workflow endpoint가 느리거나 실패해도 Agent 실행은 delivery outbox 생성까지만 수행한다.

## Operations Summary 흐름

```text
GET /v1/operations/summary
  -> DocumentRepositoryPort 문서 수 조회
  -> ApprovalRepositoryPort pending 수 조회
  -> AuditLogPort 최근 이벤트 조회
  -> latency/confidence/tool/approval/evaluation 지표 계산
  -> dashboard-ready summary 반환
```

운영 요약은 별도 집계 테이블 없이 현재 이벤트 스트림에서 계산한다.
이 방식은 MVP 단계에서 데이터 모델을 단순하게 유지하면서 dashboard API 계약을 먼저 고정한다.

## Operator Dashboard 흐름

```text
GET /dashboard
  -> FastAPI HTML response
  -> browser fetch
     -> /v1/operations/summary
     -> /v1/operations/usage
     -> /v1/operations/slo
     -> /v1/operations/incidents/snapshot
     -> /v1/operations/feedback/summary
     -> /v1/operations/alerts
     -> /v1/operations/migrations/status
     -> /v1/agents/runs/preview
     -> /v1/agents/runs
     -> /v1/agents/runs/{run_id}/timeline
     -> /v1/agents/runs/{run_id}/diagnostics
     -> /v1/approvals/pending
     -> /v1/approvals/{approval_id}/approve
     -> /v1/approvals/{approval_id}/reject
     -> /v1/audit/events?request_id=...
     -> /v1/tools
     -> /v1/tools/gateway/status
  -> 운영 지표, run preview, feedback summary, 월간 사용률, SLO 상태, incident snapshot, alert, schema migration status, 최근 실행 이력, 실행 diagnostics, 실행 timeline, 승인 queue, 승인/반려 처리, tool catalog, gateway circuit 상태, 감사 이벤트 표시
```

대시보드는 별도 상태 저장소를 갖지 않는다.
운영 화면은 API read model의 소비자로 두고, 승인 실행/반려 같은 변경은 명시적인 API 경계를 호출한다.
request id 필터도 화면 내부 상태로 별도 저장하지 않고 audit event 조회 API의 query parameter로 전달한다.

Operations alert는 별도 쓰기 모델이 아니라 summary read model 위에서 계산한다.
임계치 기준은 API query parameter로 넘기며, 대시보드는 반환된 alert만 표시한다.
월간 사용률은 Agent 실행 저장소의 기간 집계를 읽으며, Agent 실행 전 `quota_guard`와 같은 기준을 사용한다.
SLO read model은 Agent 실행 감사 이벤트에서 success rate, blocked rate, p95 latency, error budget을
계산한다.
Incident snapshot은 summary, usage, SLO, alert read model을 조합해 severity, 원인 후보, 권장 조치를
반환한다.
Feedback summary는 `agent.feedback.submitted` 감사 이벤트를 집계해 average rating과 outcome count를
반환한다.
실행 timeline은 목록에서 선택된 run id로 조회하며, 화면 자체에 별도 timeline 상태를 저장하지 않는다.

## Retention Prune 흐름

```text
POST /v1/operations/retention/prune
  -> dry_run이면 삭제 대상 count만 반환
  -> dry_run=false이면 terminal webhook delivery 삭제
  -> 오래된 audit event 삭제
  -> retention.pruned audit event 기록
```

보관 정책은 운영 API에서 시작하지만 실제 삭제 규칙은 persistence adapter가 책임진다.
Postgres adapter는 재시도 가능한 webhook delivery가 연결된 audit event를 삭제하지 않는다.

## Health와 Readiness

```text
GET /health
  -> process liveness 확인

GET /v1/readiness
  -> storage backend 확인
  -> vector backend 확인
  -> llm/auth mode 보고
  -> dependency 하나라도 unavailable이면 503 반환
```

readiness는 배포 제어와 운영 장애 판단을 위한 계약이다.
local memory/vector 모드는 process 내부 adapter를 ready로 보고, Postgres/Qdrant 모드는 실제 연결을
검사한다.

## Migration Status 흐름

```text
GET /v1/operations/migrations/status
  -> db/migrations/*.sql 파일을 version 순으로 읽음
  -> SHA-256 checksum 계산
  -> Postgres schema_migrations ledger 조회
  -> applied/pending/checksum_mismatch 상태 계산
```

API는 migration을 직접 적용하지 않는다. DDL 실행은 `scripts/manage_migrations.py`가 담당하고,
운영 API는 현재 DB와 repository migration 파일의 일치 여부만 읽는다. 이 분리는 운영 화면이나
readiness 호출이 스키마를 변경하지 않는다는 경계를 보장한다.

## 엔터프라이즈 고려사항

### 멀티테넌시

모든 핵심 데이터는 `tenant_id`를 가진다. API 요청의 tenant slug는 Postgres 내부 tenant UUID로
변환되고, Postgres adapter는 connection마다 `app.tenant_id` session setting을 지정한다.
tenant-owned table은 Row Level Security policy로 이 값과 row의 `tenant_id`가 일치할 때만 접근된다.
schema owner인 `ax_agent`와 runtime role인 `ax_agent_app`을 분리해 runtime query가 RLS를 우회하지
않도록 한다.

API key credential은 선택적으로 tenant 목록을 가질 수 있다.

```text
key:actor_id:scope|scope@tenant-a|tenant-b
```

요청의 `tenant_id`가 principal의 허용 tenant 목록에 없으면 `403 Forbidden`을 반환한다.
tenant 목록을 생략한 key는 모든 tenant에 접근할 수 있어 로컬 호환성을 유지하지만,
운영형 설정에서는 tenant를 명시하는 것을 권장한다.

### 멱등성

재시도 가능한 쓰기 API는 `Idempotency-Key`를 지원한다.

```text
POST write API
  -> request payload canonical hash
  -> IdempotencyRepositoryPort 조회
  -> 같은 key + 같은 hash면 저장된 response replay
  -> 같은 key + 다른 hash면 409 Conflict
  -> 신규 요청이면 use case 실행 후 response 저장
```

현재 적용 대상:

- `POST /v1/documents/ingest`
- `POST /v1/agents/runs`
- `POST /v1/evaluations/runs`

메모리 모드와 Postgres 모드는 같은 `IdempotencyRepositoryPort`를 구현한다.
Postgres 모드에서는 `idempotency_keys` 테이블에 request hash와 response payload를 저장한다.

승인 replay는 이미 `executed` 상태인 요청을 다시 실행하지 않고 기존 replay 결과를 반환한다.
반려된 요청은 `rejected` 상태로 닫히며 이후 승인 요청이 들어와도 replay하지 않는다.

### 감사 가능성

Agent는 사용자를 대신해 행동할 수 있다. 따라서 다음 정보가 남아야 한다.

- 누가 요청했는가
- 어떤 문서를 근거로 답했는가
- 어떤 정책 검사를 통과했는가
- 어떤 tool call이 허용/거부되었는가
- 어떤 tool call이 승인 대기 상태로 전환되었는가
- 어떤 승인 요청이 실행 또는 반려되었는가
- 외부 tool 호출이 몇 번 시도되었고 fallback 또는 circuit breaker를 사용했는가
- 평가 케이스별 점수와 누락된 기대 사실은 무엇인가
- 감사 이벤트를 어떤 형식으로 외부 분석 시스템에 전달했는가
- 운영자가 한 화면에서 볼 핵심 지표는 무엇인가
- 실행 결과와 신뢰도는 무엇인가

### 보수적 기본값

로컬 실행에서도 기본값은 안전하게 둔다.

- 외부 LLM 키 없이도 로컬 deterministic 모드로 실행
- 쓰기성 tool call은 승인 대기 상태를 기본값으로 둠
- 개인정보 마스킹 기본 적용
- 근거 문서가 없으면 답변 보류
- 모든 실행은 감사 이벤트로 기록

## 제품 확장 포인트

| 확장 영역 | 추가 구현 | 현재 아키텍처 연결점 |
| --- | --- | --- |
| Tool Runtime | MCP boundary, Agent 간 협업, tool schema | Tool Runtime, Resilient Tool Gateway, Agent Orchestrator |
| Agentic RAG | 검색 전략 평가, reranking, freshness check | Query Classifier, Retrieval Planner, Evaluation |
| Governance | RAG 라우팅, 승인, 감사 정책 | Policy Guard, Audit Log, Workflow API |
| Workflow | n8n/iPaaS 업무 자동화 | REST API, Tool Executor, Scenario Module |
| LLMOps | retry/fallback, timeout, 관측성 | Trace, Adapter Boundary, Audit Event |
| Domain Intelligence | 멀티모달 RAG, Ontology, 지식그래프 | Document Metadata, Vector Adapter, Graph Extension |
| Regulated Workflow | 마스킹, 승인, 규제 대응 | Redaction, RBAC-ready Schema, Audit Trail |

## MVP에서 일부러 하지 않는 것

- Foundation model 직접 학습
- 논문 재현형 모델링
- 프롬프트만 많은 챗봇
- 출처 없는 답변 생성
- 외부 API 키가 있어야만 동작하는 구조
