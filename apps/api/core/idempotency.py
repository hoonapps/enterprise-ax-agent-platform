from __future__ import annotations

import hashlib
import json
from typing import Annotated

from fastapi import Header, HTTPException, status
from pydantic import BaseModel

from apps.api.application.ports import IdempotencyRepositoryPort
from apps.api.domain.models import IdempotencyRecord

IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def request_payload_hash(payload: BaseModel) -> str:
    serialized = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def replay_idempotent_response[ResponseT: BaseModel](
    *,
    repository: IdempotencyRepositoryPort,
    tenant_id: str,
    key: str | None,
    request_hash: str,
    response_type: type[ResponseT],
) -> ResponseT | None:
    if not key:
        return None

    record = repository.get(tenant_id=tenant_id, key=key)
    if record is None:
        return None
    if record.request_hash != request_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="같은 Idempotency-Key로 다른 요청 payload를 처리할 수 없습니다.",
        )
    return response_type.model_validate(record.response_payload)


def save_idempotent_response(
    *,
    repository: IdempotencyRepositoryPort,
    tenant_id: str,
    key: str | None,
    request_hash: str,
    response: BaseModel,
) -> None:
    if not key:
        return
    repository.save(
        IdempotencyRecord(
            tenant_id=tenant_id,
            key=key,
            request_hash=request_hash,
            response_payload=response.model_dump(mode="json"),
        )
    )
