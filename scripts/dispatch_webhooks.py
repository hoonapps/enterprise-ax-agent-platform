from __future__ import annotations

import argparse
import json
from typing import Any

from apps.api.core.container import get_container
from apps.api.domain.models import WebhookDelivery


def main() -> None:
    parser = argparse.ArgumentParser(description="Dispatch due webhook outbox deliveries.")
    parser.add_argument("--tenant-id", default="default", help="Tenant id to dispatch.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum deliveries to dispatch.")
    args = parser.parse_args()

    container = get_container()
    deliveries = container.webhook_dispatcher.dispatch_pending(
        tenant_id=args.tenant_id,
        limit=max(1, args.limit),
    )

    print(json.dumps(_summary(deliveries), ensure_ascii=False, indent=2, sort_keys=True))


def _summary(deliveries: list[WebhookDelivery]) -> dict[str, Any]:
    return {
        "count": len(deliveries),
        "deliveries": [
            {
                "id": str(delivery.id),
                "event_type": delivery.event_type,
                "status": delivery.status.value,
                "attempt_count": delivery.attempt_count,
                "next_attempt_at": (
                    delivery.next_attempt_at.isoformat() if delivery.next_attempt_at else None
                ),
                "last_error": delivery.last_error,
            }
            for delivery in deliveries
        ],
    }


if __name__ == "__main__":
    main()
