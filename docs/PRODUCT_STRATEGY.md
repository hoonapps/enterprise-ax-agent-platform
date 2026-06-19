# 제품 전략

`Enterprise AX Agent Platform`은 사내 지식 검색과 업무 자동화를 하나의 Agent 실행 플랫폼으로 묶는 제품이다.

목표는 단순 질의응답이 아니다.

- 업무 문서를 안전하게 검색한다.
- 질문 유형에 따라 RAG 전략을 바꾼다.
- 외부 시스템 실행 전 정책을 검사한다.
- API 호출 권한과 Agent tool 실행 권한을 분리한다.
- 조회성 tool과 쓰기성 tool의 실행 경계를 분리한다.
- tool별 required scope와 risk level을 registry에서 관리한다.
- 외부 tool 호출은 MCP-compatible boundary와 Tool Gateway를 통해 분리한다.
- 외부 tool 장애는 timeout/retry/fallback 정책으로 격리한다.
- 승인 대기 요청을 운영자가 재검토하고 실행 또는 반려할 수 있게 한다.
- expected facts 기반 evaluation run으로 답변 품질을 회귀 평가한다.
- CI regression gate로 품질 기준 미달 변경을 차단한다.
- Agent 실행 과정을 감사 가능한 이벤트로 남긴다.
- 감사 이벤트를 JSONL/CSV로 export해 외부 분석과 컴플라이언스 흐름에 연결한다.
- 운영 요약 API로 dashboard-ready 지표를 제공한다.
- 운영 콘솔에서 Agent 실행, 승인 대기, 승인/반려, tool catalog, 감사 이벤트를 추적한다.
- 운영자가 장애와 품질을 추적할 수 있게 만든다.

## 제품 문제

기업 내부에서 LLM Agent를 도입할 때 자주 막히는 지점은 모델 성능이 아니라 운영 경계다.

- 어떤 문서를 근거로 답했는지 알기 어렵다.
- Agent가 어떤 권한으로 tool을 실행했는지 추적하기 어렵다.
- 개인정보나 민감정보가 LLM context에 섞일 수 있다.
- 외부 API 실패, 재시도, 중복 실행을 제어하기 어렵다.
- 검색 품질이 나빠졌는지 회귀 테스트하기 어렵다.

이 제품은 그 문제를 백엔드 플랫폼으로 풀어간다.

## 핵심 사용자

| 사용자 | 필요한 기능 |
| --- | --- |
| 업무 담당자 | 사내 문서 기반 답변, 실행 요청, 승인 상태 확인 |
| 운영자 | 실행 이력, 감사 이벤트, 실패 원인, 지연시간 추적 |
| 보안 담당자 | 개인정보 마스킹, 권한 정책, tool call 감사 |
| 플랫폼 개발자 | MCP/n8n/ERP/CRM 같은 외부 시스템 연결 |

## 제품 원칙

1. 근거 없는 답변보다 답변 보류가 낫다.
2. Tool 실행은 Agent의 추론과 분리한다.
3. 모든 쓰기성 작업은 정책과 승인 경계를 지난다.
4. 조회성 tool은 실행 가능하지만, 쓰기성 tool은 승인 대기 상태를 기본값으로 둔다.
5. 등록되지 않은 tool이나 required scope가 없는 tool 요청은 실행하지 않는다.
6. HTTP API 접근은 API key와 endpoint scope로 제어할 수 있어야 한다.
7. 승인 후 replay는 멱등적으로 처리해 중복 실행을 막는다.
8. 반려된 승인 요청은 닫힌 상태로 유지하고 이후 replay하지 않는다.
9. Vector DB는 검색 인덱스이고, 업무 원장은 RDB가 담당한다.
10. 외부 tool 장애는 구조화된 execution metadata로 남긴다.
11. 답변 품질은 evaluation dataset으로 반복 측정한다.
12. 기준 점수보다 낮은 변경은 CI에서 실패시킨다.
13. 감사 이벤트는 운영 분석 시스템으로 export할 수 있어야 한다.
14. 운영 요약은 audit event와 업무 원장에서 계산한다.
15. 운영자는 raw prompt가 아니라 구조화된 trace와 audit event를 본다.
16. 운영 화면은 API read model의 소비자로 두고 상태 변경 책임을 갖지 않는다.

## 확장 축

| 확장 축 | 구현 방향 |
| --- | --- |
| Knowledge | Qdrant/pgvector, reranking, freshness check |
| Workflow | n8n, Slack, approval queue |
| Tool Runtime | tool schema registry, scope check, MCP-compatible JSON-RPC, Tool Gateway |
| Governance | API key auth, RBAC, PII redaction, audit export |
| LLMOps | evaluation dataset, regression test, cost/latency metrics |
| Domain Intelligence | ontology, knowledge graph, multimodal document ingestion |

## 제품 성공 기준

- 운영자가 Agent 실행 1건을 처음부터 끝까지 추적할 수 있다.
- 답변마다 citation과 confidence가 남는다.
- 위험 action은 자동 실행되지 않고 승인 상태로 전환된다.
- 승인된 action은 replay 결과와 함께 executed 상태로 남는다.
- 반려된 action은 reason과 함께 rejected 상태로 남는다.
- 외부 tool 실패는 attempts, elapsed time, fallback 여부와 함께 남는다.
- 평가 결과는 average score, pass rate, failed count로 추적된다.
- regression dataset은 CI에서 자동 실행된다.
- audit event는 JSONL/CSV로 export된다.
- 운영 요약 API는 pending approvals, agent runs, tool decisions, evaluation metrics를 제공한다.
- 운영 콘솔은 핵심 지표, 승인 대기, 승인/반려, tool catalog, 감사 이벤트를 같은 화면에서 처리한다.
- 문서와 벡터 인덱스의 책임이 분리된다.
- 외부 LLM이나 Vector DB 장애 시에도 실패 경계가 명확하다.
