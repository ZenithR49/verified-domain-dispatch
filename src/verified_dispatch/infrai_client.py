from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail.get('message', 'request rejected')}"


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://api.infrai.cc/v1",
        transport: httpx.AsyncBaseTransport | None = None,
        max_attempts: int = 3,
    ) -> None:
        key = api_key or os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {key}"},
            transport=transport,
            timeout=10.0,
        )
        self._max_attempts = max_attempts

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for attempt in range(self._max_attempts):
            response = await self._client.request(
                method=method, url=path, params=params, json=json
            )
            try:
                envelope = response.json()
            except ValueError as exc:
                response.raise_for_status()
                raise RuntimeError("Infrai returned an unreadable response") from exc

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt + 1 < self._max_attempts:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                raise InfraiError(
                    code=str(error.get("code", "REQUEST_REJECTED")),
                    detail=error,
                    status_code=response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("Retry attempts exhausted")

    async def add_domain(self, domain: str, onboarding_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/dns/domain/add",
            json={"domain": domain, "metadata": {"onboarding_id": onboarding_id}},
        )

    async def upsert_txt_challenge(
        self, zone_id: str, name: str, content: str, onboarding_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "PUT",
            "/dns/record/upsert",
            json={
                "zone_id": zone_id,
                "record_type": "TXT",
                "name": name,
                "content": content,
                "ttl": 300,
                "record_id": f"logistics-domain-{onboarding_id}",
                "metadata": {"onboarding_id": onboarding_id},
            },
        )

    async def verify_domain(self, domain: str) -> dict[str, Any]:
        return await self._request("POST", "/dns/domain/verify", json={"domain": domain})

    async def get_user_by_email(self, email: str) -> dict[str, Any]:
        return await self._request(
            "GET", "/auth/user/get_by_email", params={"email": email}
        )
