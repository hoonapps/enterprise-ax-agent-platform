# 채용 공고 매핑

이 프로젝트는 AI 모델 연구자가 아니라 **AX Engineer / AI Agent Engineer / LLM Application Backend Engineer**를
목표로 만든다.

## 포지셔닝

```text
기업 업무 시스템에 LLM Agent를 안전하게 붙이고 운영 가능한 백엔드로 만드는 개발자
```

## 회사별 매핑

| 회사 | 공고에서 원하는 방향 | 프로젝트에서 보여주는 기능 |
| --- | --- | --- |
| 현대오토에버 | MCP, A2A, 지식그래프, Agent 오케스트레이션 | Tool Runtime 경계, MCP 확장 포인트, graph-ready 문서 메타데이터 |
| LG CNS | Agentic AI, A-RAG, IR, Prompt Engineering, 고객 맞춤 AX | 질문 분류, 검색 전략 라우팅, 평가 서비스 확장 구조 |
| 삼성SDS | 기업용 생성형 AI 플랫폼, RAG 전략 자동 선택, 거버넌스 | Policy Guard, Audit Log, 업무앱형 Agent API |
| 무신사 | n8n/Zapier/Make, LangChain, SaaS/API 업무 자동화 | REST 기반 workflow API, Tool Executor 계약 |
| SK AX | LLM/RAG/Vector DB/Agent, LLMOps, 안정성 | 어댑터 경계, deterministic fallback, observability 모델 |
| 한화시스템 | LLM, Vision AI, Ontology, Vector DB, Vertical AI | ontology-ready schema, 문서 메타데이터, 멀티모달 확장 포인트 |
| 금융권 | 규제 산업 생성형 AI, 마스킹, 승인, 감사 | PII redaction, RBAC-ready schema, audit trail |

## 이력서 문장

```text
Enterprise AX Agent Platform 개발
- FastAPI 기반 Agent API 서버를 설계하고, Hexagonal Architecture로 도메인/유스케이스/어댑터 경계를 분리
- 문서 적재, 청크 분리, Vector Search, 질문 유형별 RAG 전략 라우팅, 근거 기반 답변 생성 흐름 구현
- 개인정보 마스킹, 위험 action 승인 차단, Agent 실행 trace, 감사 이벤트 모델을 적용해 기업형 거버넌스 설계
- Postgres 기준 문서/청크/Agent 실행/Tool call/Audit event 스키마를 설계하고 Vector DB를 파생 인덱스로 분리
```

## 면접에서 설명할 핵심

- 챗봇이 아니라 Agent 실행 플랫폼으로 설계했다.
- LLM 호출보다 중요한 것은 권한, 감사, 근거, 실패 처리라고 판단했다.
- RDB와 Vector DB의 책임을 분리했다.
- Agent workflow를 유스케이스 단위로 테스트 가능하게 만들었다.
- 각 회사 공고에 맞춰 MCP, n8n, 지식그래프, 평가, 거버넌스를 확장할 수 있다.
