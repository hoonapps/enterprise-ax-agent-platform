# Enterprise AX Agent Platform

한국 대기업 AX Engineer / AI Agent Engineer / LLM Application Backend Engineer 포지션을 목표로 만든
기업형 LLM Agent 백엔드 포트폴리오입니다.

이 프로젝트는 “LLM 챗봇을 만들었다”가 아니라,

> 기업 업무 시스템에 LLM Agent를 안전하게 연결하고, RAG·권한·감사로그·평가·운영 안정성을 갖춘 백엔드 플랫폼으로 설계했다

를 보여주기 위한 프로젝트입니다.

## 핵심 포지셔닝

```text
모델을 직접 학습하는 AI Research Engineer가 아니라,
LLM/Agent 도구를 활용해 기업 업무를 자동화하고 운영 가능한 시스템으로 만드는 백엔드 엔지니어
```

## 현재 구현 범위

- FastAPI 기반 REST API
- 문서 적재 API
- 문서 chunking
- 로컬 deterministic 검색 어댑터
- 질문 유형 분류
- 질문 유형별 RAG 전략 선택
- 근거 기반 답변 생성
- 개인정보 마스킹 정책
- 위험 action 승인 차단 정책
- Agent 실행 trace
- 감사 이벤트 기록
- Postgres 기준 DB 설계 SQL
- 헥사고날 아키텍처 기반 코드 구조
- 로컬 테스트

외부 LLM API key가 없어도 로컬에서 동작합니다.  
실제 OpenAI/Claude/Qdrant/Postgres/MCP/n8n 연동은 같은 포트/어댑터 구조 위에 단계적으로 추가합니다.

## 기술 스택

| 영역 | 선택 |
| --- | --- |
| API | Python 3.12, FastAPI |
| Agent Orchestration | Use Case orchestration, LangGraph 확장 예정 |
| RAG | Chunking, retrieval strategy router, citation |
| Vector Search | Local deterministic adapter, Qdrant 확장 예정 |
| DB 설계 | Postgres, Audit Event, Agent Run, Tool Call schema |
| Governance | PII redaction, policy guard, approval-required action |
| 운영 | trace, audit log, deterministic fallback |
| 배포 | Docker Compose |
| 테스트 | pytest, FastAPI TestClient |

## 아키텍처

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

자세한 설계 문서:

- [아키텍처](docs/ARCHITECTURE.md)
- [디자인 패턴](docs/DESIGN_PATTERNS.md)
- [DB 설계](docs/DATABASE_DESIGN.md)
- [API 설계](docs/API_DESIGN.md)
- [채용 공고 매핑](docs/COMPANY_FIT.md)
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
```

## 빠른 실행

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger 문서:

```text
http://127.0.0.1:8000/docs
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
    "scenario": "lg-cns",
    "message": "AX 전환 리스크와 거버넌스 기준을 정리해줘"
  }'
```

위험 action 차단:

```bash
curl -X POST http://127.0.0.1:8000/v1/agents/runs \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "scenario": "finance",
    "message": "고객 계좌로 100만원 송금 실행해줘"
  }'
```

응답은 `approval_required` 정책 판단과 함께 실행을 차단합니다.

## 테스트

```bash
make verify
```

개별 실행:

```bash
make lint
make typecheck
make test
```

## 회사별 어필 포인트

| 회사 | 어필 기능 |
| --- | --- |
| 현대오토에버 | MCP/A2A/지식그래프 확장 가능한 Tool Runtime 경계 |
| LG CNS | Agentic RAG, 질문 유형 분류, 검색 전략 라우팅 |
| 삼성SDS | RAG 전략 자동 선택, Policy Guard, Audit Log |
| 무신사 | n8n/iPaaS 업무 자동화 API로 확장 가능한 구조 |
| SK AX | LLMOps, 관측성, fallback, 운영 가능한 Agent 구조 |
| 한화시스템 | Ontology/Vertical AI 확장 가능한 문서 메타데이터 |
| 금융권 | 개인정보 마스킹, 승인, 감사 이벤트 |

## 백엔드 개발자로서 보여주는 강점

- LLM 기능을 프롬프트에만 의존하지 않고 백엔드 유스케이스로 모델링
- RDB와 Vector DB의 책임 분리
- Agent 실행을 상태와 감사 이벤트로 관리
- 정책 검사를 런타임 컴포넌트로 구현
- 외부 벤더 SDK를 어댑터 경계로 격리
- 테스트 가능한 구조로 API와 도메인 로직 분리
- CI에서 lint, typecheck, test를 모두 검증

## 다이어그램

- [시스템 컨텍스트](docs/diagrams/system-context.mmd)
- [Agent 실행 시퀀스](docs/diagrams/agent-run-sequence.mmd)

## 단계별 로드맵

### 1단계: Agentic RAG MVP

- 문서 적재
- chunking
- 검색
- 질문 유형 분류
- 근거 기반 답변
- trace/audit

### 2단계: 운영형 RAG

- Qdrant 연동
- Postgres repository 구현
- 평가 데이터셋과 regression test
- Langfuse/OpenTelemetry trace

### 3단계: Enterprise Tool Runtime

- MCP Streamable HTTP 서버
- Tool schema와 권한 scope
- 승인 워크플로우
- n8n 연동

### 4단계: 회사별 시나리오

- 현대오토에버: 차량/제조 MCP + 지식그래프
- LG CNS: 고객사 AX 컨설팅 A-RAG
- 삼성SDS: 업무앱형 Agent + 거버넌스
- 무신사: Slack/n8n 사내 자동화
- SK AX: LLMOps와 관측성 강화

## 라이선스

MIT License
