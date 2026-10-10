from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field, model_validator


class OnboardingState(str, Enum):
    TXT_PENDING = "txt_pending"
    ACTIVE = "active"


class ShipmentEventKind(str, Enum):
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    EXCEPTION = "exception"


class ProofOfDelivery(BaseModel):
    object_key: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: str = Field(pattern=r"^(application/pdf|image/jpeg|image/png)$")


class DeliveryException(BaseModel):
    code: str = Field(min_length=1)
    note: str = Field(min_length=1)
    retryable: bool


class ShipmentEvent(BaseModel):
    shipment_id: str = Field(min_length=1)
    kind: ShipmentEventKind
    occurred_at: datetime
    proof: ProofOfDelivery | None = None
    exception: DeliveryException | None = None

    @model_validator(mode="after")
    def check_event_payload(self) -> "ShipmentEvent":
        if self.kind == ShipmentEventKind.DELIVERED and self.proof is None:
            raise ValueError("delivered events require proof")
        if self.kind == ShipmentEventKind.EXCEPTION and self.exception is None:
            raise ValueError("exception events require exception details")
        if self.kind != ShipmentEventKind.DELIVERED and self.proof is not None:
            raise ValueError("proof belongs only on delivered events")
        if self.kind != ShipmentEventKind.EXCEPTION and self.exception is not None:
            raise ValueError("exception details belong only on exception events")
        return self


class OnboardingRequest(BaseModel):
    onboarding_id: str = Field(min_length=1)
    company_domain: str = Field(pattern=r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
    owner_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    txt_name: str = Field(min_length=1)
    txt_content: str = Field(min_length=1)

    @model_validator(mode="after")
    def owner_matches_domain(self) -> "OnboardingRequest":
        if self.owner_email.rsplit("@", 1)[1].lower() != self.company_domain.lower():
            raise ValueError("owner email must use the company domain")
        return self


class OnboardingResult(BaseModel):
    onboarding_id: str
    domain: str
    zone_id: str
    owner_user_id: str
    state: OnboardingState


class InfraiGateway(Protocol):
    async def add_domain(self, domain: str, onboarding_id: str) -> dict:
        raise AssertionError("protocol method")

    async def upsert_txt_challenge(
        self, zone_id: str, name: str, content: str, onboarding_id: str
    ) -> dict:
        raise AssertionError("protocol method")

    async def verify_domain(self, domain: str) -> dict:
        raise AssertionError("protocol method")

    async def get_user_by_email(self, email: str) -> dict:
        raise AssertionError("protocol method")


class ShipmentRegistry:
    def __init__(self) -> None:
        self._active_domains: set[str] = set()
        self._events: dict[str, list[ShipmentEvent]] = {}

    def activate(self, domain: str) -> None:
        self._active_domains.add(domain.lower())

    def record(self, domain: str, event: ShipmentEvent) -> int:
        if domain.lower() not in self._active_domains:
            raise PermissionError("company domain is not active")
        events = self._events.setdefault(event.shipment_id, [])
        events.append(event)
        return len(events)


class LogisticsOnboarding:
    def __init__(self, infrai: InfraiGateway, registry: ShipmentRegistry) -> None:
        self._infrai = infrai
        self._registry = registry

    async def onboard(self, request: OnboardingRequest) -> OnboardingResult:
        domain_data = await self._infrai.add_domain(
            request.company_domain, request.onboarding_id
        )
        zone_id = str(domain_data["zone_id"])
        await self._infrai.upsert_txt_challenge(
            zone_id,
            request.txt_name,
            request.txt_content,
            request.onboarding_id,
        )
        verification = await self._infrai.verify_domain(request.company_domain)
        verified = verification.get("verified") is True
        state = OnboardingState.ACTIVE if verified else OnboardingState.TXT_PENDING

        user_data = await self._infrai.get_user_by_email(request.owner_email)
        if state == OnboardingState.ACTIVE:
            self._registry.activate(request.company_domain)

        return OnboardingResult(
            onboarding_id=request.onboarding_id,
            domain=request.company_domain,
            zone_id=zone_id,
            owner_user_id=str(user_data["id"]),
            state=state,
        )
