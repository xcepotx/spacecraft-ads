from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import httpx
from redis import Redis


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://redis:6379/0",
)

APP_URL = os.getenv(
    "AUTOMATION_APP_URL",
    "http://app:8000",
).rstrip("/")

INTERNAL_TOKEN = os.getenv(
    "AUTOMATION_INTERNAL_TOKEN",
    "",
).strip()

DUE_SET = (
    "product_ads:automation:due"
)

RULE_PREFIX = (
    "product_ads:automation:rule:"
)


def decode(value):
    if isinstance(value, bytes):
        return value.decode(
            "utf-8",
            errors="replace",
        )

    return str(value)


def main():
    redis_client = Redis.from_url(
        REDIS_URL
    )

    print(
        "[automation] scheduler started",
        flush=True,
    )

    while True:
        try:
            current_timestamp = (
                datetime.now(
                    timezone.utc
                ).timestamp()
            )

            due_rules = (
                redis_client.zrangebyscore(
                    DUE_SET,
                    0,
                    current_timestamp,
                    start=0,
                    num=10,
                )
            )

            for raw_rule_id in due_rules:
                rule_id = decode(
                    raw_rule_id
                )

                lock_key = (
                    "product_ads:"
                    "automation:lock:"
                    f"{rule_id}"
                )

                locked = redis_client.set(
                    lock_key,
                    "1",
                    nx=True,
                    ex=300,
                )

                if not locked:
                    continue

                try:
                    raw_rule = redis_client.get(
                        f"{RULE_PREFIX}{rule_id}"
                    )

                    if not raw_rule:
                        redis_client.zrem(
                            DUE_SET,
                            rule_id,
                        )
                        continue

                    rule = json.loads(
                        decode(raw_rule)
                    )

                    if not rule.get("enabled"):
                        redis_client.zrem(
                            DUE_SET,
                            rule_id,
                        )
                        continue

                    params = {}

                    if INTERNAL_TOKEN:
                        params[
                            "internal_token"
                        ] = INTERNAL_TOKEN

                    with httpx.Client(
                        timeout=120.0
                    ) as client:
                        response = client.post(
                            (
                                f"{APP_URL}"
                                "/api/automation/"
                                f"rules/{rule_id}/run"
                            ),
                            params=params,
                        )

                        print(
                            "[automation]",
                            rule_id,
                            response.status_code,
                            response.text[:300],
                            flush=True,
                        )

                finally:
                    redis_client.delete(
                        lock_key
                    )

            time.sleep(20)

        except Exception as exc:
            print(
                "[automation] scheduler error:",
                repr(exc),
                flush=True,
            )
            time.sleep(20)


if __name__ == "__main__":
    main()
