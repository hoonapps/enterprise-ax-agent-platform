from __future__ import annotations

import argparse
import json
import time
from typing import Any

from apps.api.core.container import get_container
from apps.api.domain.models import WebhookDelivery


def main() -> None:
    parser = argparse.ArgumentParser(description="Dispatch due webhook outbox deliveries.")
    parser.add_argument("--tenant-id", default="default", help="Tenant id to dispatch.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum deliveries to dispatch.")
    parser.add_argument("--loop", action="store_true", help="Keep dispatching on an interval.")
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=15.0,
        help="Sleep interval used with --loop.",
    )
    args = parser.parse_args()

    container = get_container()
    while True:
        deliveries = container.webhook_dispatcher.dispatch_pending(
            tenant_id=args.tenant_id,
            limit=max(1, args.limit),
        )
        print(json.dumps(_summary(deliveries), ensure_ascii=False, indent=2, sort_keys=True))
        if not args.loop:
            break
        time.sleep(max(1.0, args.interval_seconds))


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
