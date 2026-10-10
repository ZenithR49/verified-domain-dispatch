import asyncio
from datetime import UTC, datetime

import pytest

from verified_dispatch.shipment_onboarding import (
    LogisticsOnboarding,
    OnboardingRequest,
    OnboardingState,
    ProofOfDelivery,
    ShipmentEvent,
    ShipmentEventKind,
    ShipmentRegistry,
)


class FakeInfrai:
    def __init__(self, verified: bool) -> None:
        self.verified = verified
        self.zone_used: str | None = None

    async def add_domain(self, domain: str, onboarding_id: str) -> dict:
        return {"zone_id": "zone_logistics_42"}

    async def upsert_txt_challenge(
        self, zone_id: str, name: str, content: str, onboarding_id: str
    ) -> dict:
        self.zone_used = zone_id
        return {"record_id": "record_42"}

    async def verify_domain(self, domain: str) -> dict:
        return {"verified": self.verified}

    async def get_user_by_email(self, email: str) -> dict:
        return {"id": "user_ops_42", "email": email}


def request() -> OnboardingRequest:
    return OnboardingRequest(
        onboarding_id="onboarding_42",
        company_domain="parcel.test",
        owner_email="ops@parcel.test",
        txt_name="_infrai-onboarding.parcel.test",
        txt_content="challenge_42",
    )


def test_verified_domain_activates_shipment_intake() -> None:
    gateway = FakeInfrai(verified=True)
    registry = ShipmentRegistry()

    result = asyncio.run(LogisticsOnboarding(gateway, registry).onboard(request()))
    event_number = registry.record(
        "parcel.test",
        ShipmentEvent(
            shipment_id="shipment_42",
            kind=ShipmentEventKind.DELIVERED,
            occurred_at=datetime(2026, 9, 14, tzinfo=UTC),
            proof=ProofOfDelivery(
                object_key="pod/shipment_42.pdf",
                sha256="a" * 64,
                media_type="application/pdf",
            ),
        ),
    )

    assert result.state == OnboardingState.ACTIVE
    assert result.owner_user_id == "user_ops_42"
    assert gateway.zone_used == "zone_logistics_42"
    assert event_number == 1


def test_pending_txt_blocks_shipment_intake() -> None:
    registry = ShipmentRegistry()
    result = asyncio.run(
        LogisticsOnboarding(FakeInfrai(verified=False), registry).onboard(request())
    )

    with pytest.raises(PermissionError, match="company domain is not active"):
        registry.record(
            "parcel.test",
            ShipmentEvent(
                shipment_id="shipment_43",
                kind=ShipmentEventKind.IN_TRANSIT,
                occurred_at=datetime(2026, 9, 14, tzinfo=UTC),
            ),
        )

    assert result.state == OnboardingState.TXT_PENDING
