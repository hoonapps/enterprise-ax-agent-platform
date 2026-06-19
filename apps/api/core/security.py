from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from apps.api.core.config import get_settings


@dataclass(frozen=True)
class AuthPrincipal:
    actor_id: str
    scopes: frozenset[str]
    tenant_ids: frozenset[str]
    auth_mode: str


def get_auth_principal(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> AuthPrincipal:
    settings = get_settings()
    if not settings.auth_enabled:
        return AuthPrincipal(
            actor_id="local-operator",
            scopes=frozenset({"*"}),
            tenant_ids=frozenset({"*"}),
            auth_mode=settings.auth_mode,
        )

    credentials = parse_api_key_credentials(settings.api_key_credentials)
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key가 필요합니다.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    principal = credentials.get(x_api_key)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 API key입니다.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return principal


def require_scopes(*required_scopes: str) -> Callable[..., AuthPrincipal]:
    def dependency(
        principal: Annotated[AuthPrincipal, Depends(get_auth_principal)],
    ) -> AuthPrincipal:
        if "*" in principal.scopes:
            return principal
        missing_scopes = [
            required_scope
            for required_scope in required_scopes
            if required_scope not in principal.scopes
        ]
        if missing_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "필요한 scope가 없습니다.",
                    "missing_scopes": missing_scopes,
                },
            )
        return principal

    return dependency


def require_tenant_access(principal: AuthPrincipal, tenant_id: str) -> None:
    if "*" in principal.tenant_ids or tenant_id in principal.tenant_ids:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "message": "허용되지 않은 tenant입니다.",
            "tenant_id": tenant_id,
        },
    )


@lru_cache(maxsize=8)
def parse_api_key_credentials(raw_credentials: str) -> dict[str, AuthPrincipal]:
    credentials: dict[str, AuthPrincipal] = {}
    for raw_entry in raw_credentials.split(";"):
        entry = raw_entry.strip()
        if not entry:
            continue
        api_key, actor_id, raw_scopes, raw_tenants = _split_credential(entry)
        scopes = frozenset(scope.strip() for scope in raw_scopes.split("|") if scope.strip())
        tenant_ids = frozenset(
            tenant_id.strip() for tenant_id in raw_tenants.split("|") if tenant_id.strip()
        )
        credentials[api_key] = AuthPrincipal(
            actor_id=actor_id,
            scopes=scopes,
            tenant_ids=tenant_ids or frozenset({"*"}),
            auth_mode="api-key",
        )
    return credentials


def _split_credential(entry: str) -> tuple[str, str, str, str]:
    parts = entry.split(":", 2)
    if len(parts) != 3 or not parts[0].strip() or not parts[1].strip():
        raise ValueError(
            "API_KEY_CREDENTIALS는 'key:actor_id:scope|scope[@tenant|tenant];...' "
            "형식이어야 합니다."
        )
    raw_scopes, separator, raw_tenants = parts[2].partition("@")
    return (
        parts[0].strip(),
        parts[1].strip(),
        raw_scopes.strip(),
        raw_tenants.strip() if separator else "*",
    )
