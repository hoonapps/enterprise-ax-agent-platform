# DB 설계

이 프로젝트는 로컬 MVP에서는 메모리 저장소로 실행되지만, 기준 데이터 모델은
Postgres + Vector DB 조합을 전제로 설계했다.

핵심 메시지는 다음과 같다.

> Vector DB는 검색 성능을 위한 파생 저장소이고, 업무 메타데이터와 감사 가능성의 source of truth는 RDB다.

## 설계 원칙

- 모든 업무 데이터는 `tenant_id`로 격리한다.
- 원본 문서와 검색 청크를 분리한다.
- Agent 실행은 요청/상태/답변/신뢰도/trace를 가진 업무 레코드로 저장한다.
- Tool call은 프롬프트 로그 안에 숨기지 않고 별도 테이블로 남긴다.
- 감사 이벤트는 append-only로 관리한다.
- 평가 결과는 Agent 실행과 분리해 회귀 테스트에 사용할 수 있게 한다.

## ERD 개요

```text
tenants
  |
  +-- users
  |
  +-- documents
  |     |
  |     +-- document_chunks
  |
  +-- agent_runs
  |     |
  |     +-- retrieval_events
  |     +-- tool_calls
  |     +-- agent_messages
  |
  +-- evaluation_runs
  |     |
  |     +-- evaluation_cases
  |
  +-- audit_events
```

## 핵심 테이블

### `tenants`

기업 고객 또는 로컬 워크스페이스를 나타낸다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `id` | uuid | PK |
| `slug` | text | 고유 식별자 |
| `name` | text | 표시 이름 |
| `created_at` | timestamptz | 생성 시각 |

### `documents`

업무 문서의 원본 메타데이터다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id` | uuid | FK |
| `source_type` | text | `manual`, `policy`, `ticket`, `report`, `api` |
| `source_uri` | text | 파일 경로, URL, 외부 시스템 ID |
| `title` | text | 문서 제목 |
| `content_hash` | text | 중복 적재 방지 |
| `classification` | text | `public`, `internal`, `confidential`, `restricted` |
| `metadata` | jsonb | 회사/도메인별 확장 메타데이터 |
| `created_at` | timestamptz | 생성 시각 |

주요 인덱스:

- `(tenant_id, source_type)`
- `(tenant_id, content_hash)` unique
- `metadata` GIN

### `document_chunks`

RAG 검색 단위다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id` | uuid | FK |
| `document_id` | uuid | 원본 문서 FK |
| `chunk_index` | int | 문서 내 순서 |
| `content` | text | 검색 대상 텍스트 |
| `token_count` | int | 추정 토큰 수 |
| `metadata` | jsonb | 섹션, 페이지, 업무 태그 |
| `embedding_ref` | text | Vector DB point id |
| `created_at` | timestamptz | 생성 시각 |

`embedding_ref`만 저장하고 실제 벡터는 Vector DB에 둔다.  
임베딩 모델을 바꾸면 RDB 청크를 기준으로 벡터 인덱스를 재생성할 수 있다.

### `agent_runs`

Agent 요청 1건을 나타낸다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id` | uuid | FK |
| `user_id` | uuid | 요청자 |
| `scenario` | text | `lg-cns`, `hyundai-autoever` 등 |
| `query` | text | 원본 요청 |
| `redacted_query` | text | 마스킹된 요청 |
| `query_type` | text | factual, summary, compare, action, risk |
| `status` | text | running, succeeded, failed, blocked |
| `confidence` | numeric | 0~1 신뢰도 |
| `latency_ms` | int | 전체 지연시간 |
| `created_at` | timestamptz | 시작 시각 |
| `completed_at` | timestamptz | 종료 시각 |

주요 인덱스:

- `(tenant_id, created_at desc)`
- `(tenant_id, scenario, created_at desc)`
- `(tenant_id, status)`

### `retrieval_events`

검색 전략과 검색 결과를 추적한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id` | uuid | FK |
| `agent_run_id` | uuid | Agent 실행 FK |
| `strategy` | text | 선택된 검색 전략 |
| `query` | text | 검색 질의 |
| `top_k` | int | 검색 개수 |
| `selected_chunk_ids` | uuid[] | 선택된 청크 |
| `scores` | jsonb | 청크별 점수 |
| `created_at` | timestamptz | 생성 시각 |

이 테이블이 있으면 “왜 이 문서를 근거로 답했는가”를 추적할 수 있다.

### `tool_calls`

Agent가 외부 시스템을 호출한 이력이다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id` | uuid | FK |
| `agent_run_id` | uuid | Agent 실행 FK |
| `tool_name` | text | 표준화된 tool 이름 |
| `action_type` | text | read, write, approval |
| `input_payload` | jsonb | 마스킹된 입력 |
| `output_payload` | jsonb | 마스킹된 출력 |
| `policy_decision` | text | allowed, denied, approval_required |
| `status` | text | succeeded, failed, skipped |
| `latency_ms` | int | tool 지연시간 |
| `created_at` | timestamptz | 생성 시각 |

Tool call을 별도 테이블로 둔 이유:

- prompt injection 사고 분석
- 권한 오남용 추적
- 승인 필요한 업무 분리
- 외부 시스템 장애 원인 추적

### `audit_events`

감사 이벤트 append-only 로그다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id` | uuid | FK |
| `actor_type` | text | user, system, agent |
| `actor_id` | text | 행위자 식별자 |
| `event_type` | text | 이벤트 이름 |
| `resource_type` | text | document, agent_run, tool_call |
| `resource_id` | uuid | 대상 리소스 |
| `payload` | jsonb | 마스킹된 상세 내용 |
| `created_at` | timestamptz | 발생 시각 |

감사 로그는 운영자와 보안 담당자가 Agent 실행을 재구성하기 위한 핵심 데이터다.

## Vector DB Payload

Vector DB에는 실제 임베딩과 검색용 payload만 둔다.

```json
{
  "tenant_id": "default",
  "document_id": "...",
  "chunk_id": "...",
  "title": "AX 거버넌스 플레이북",
  "classification": "internal",
  "domain": "si-ict",
  "source_type": "manual"
}
```

RDB와 Vector DB의 책임을 분리한다.

| 저장소 | 책임 |
| --- | --- |
| Postgres | 업무 원장, 메타데이터, 실행 이력, 감사 이벤트 |
| Vector DB | 유사도 검색용 임베딩 인덱스 |

## 보관 정책

| 데이터 | 권장 보관 |
| --- | --- |
| 원본 문서 | 업무 정책 기준 |
| 청크 | 원본 문서와 동일 |
| Agent 실행 | 180~365일 |
| Tool call | 365일 또는 컴플라이언스 기준 |
| 감사 이벤트 | 1~3년 |
| 평가 결과 | 회귀 분석을 위해 장기 보관 |

## 확장 전략

1. MVP: 메모리 저장소 + SQL schema 문서화
2. 2단계: Postgres repository 구현
3. 3단계: `tenant_id` 기반 Row Level Security
4. 4단계: `agent_runs`, `tool_calls`, `audit_events` 월별 파티셔닝
5. 5단계: 임베딩 모델 변경 시 청크 기준 Vector DB 재색인
