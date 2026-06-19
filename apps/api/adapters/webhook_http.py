from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from apps.api.domain.models import WebhookHttpResult


class UrllibWebhookHttpClient:
    def post_json(
        self,
        *,
        url: str,
        payload: dict[str, object],
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> WebhookHttpResult:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        request = Request(
            url=url,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return WebhookHttpResult(
                    status_code=response.status,
                    response_body=response.read().decode("utf-8", errors="replace"),
                )
        except HTTPError as exc:
            return WebhookHttpResult(
                status_code=exc.code,
                response_body=exc.read().decode("utf-8", errors="replace"),
            )
        except (TimeoutError, URLError, OSError) as exc:
            return WebhookHttpResult(status_code=0, error_message=str(exc))
