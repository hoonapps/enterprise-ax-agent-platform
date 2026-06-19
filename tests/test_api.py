from fastapi.testclient import TestClient

from apps.api.main import create_app


def test_health_and_agent_flow():
    client = TestClient(create_app())

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ingest = client.post(
        "/v1/documents/ingest",
        json={
            "tenant_id": "default",
            "title": "Agentic RAG 운영 모델",
            "content": (
                "Agentic RAG는 질문 유형을 분류하고 검색 전략을 선택한다. "
                "리스크 질문은 보안과 감사로그를 함께 봐야 한다."
            ),
            "source_uri": "test://agentic-rag",
        },
    )
    assert ingest.status_code == 200
    assert ingest.json()["chunk_count"] == 1

    run = client.post(
        "/v1/agents/runs",
        json={
            "tenant_id": "default",
            "scenario": "lg-cns",
            "message": "Agentic RAG 리스크를 정리해줘",
        },
    )
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "succeeded"
    assert body["citations"]
    assert body["trace"]
