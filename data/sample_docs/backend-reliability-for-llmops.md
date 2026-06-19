# LLMOps 백엔드 안정성

LLM Agent 백엔드는 일반 CRUD API와 다른 실패 모드를 가진다.

주요 실패 유형은 다음과 같다.

- 검색 결과가 부족한데 답변을 확정하는 문제
- prompt injection으로 원치 않는 tool call이 실행되는 문제
- 외부 LLM API 지연 또는 실패
- 같은 요청이 재시도되어 중복 실행되는 문제
- 문서 인덱스와 원본 데이터가 불일치하는 문제

운영 가능한 구조를 만들려면 retry, timeout, fallback, idempotency, trace, audit event가 필요하다.

운영 조직에서는 기능 구현뿐 아니라 장애 대응 가능성, 관측성, 배포 자동화, 성능 측정 기준을 함께 관리해야 한다.
