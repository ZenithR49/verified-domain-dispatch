import asyncio
import json

from verified_dispatch.infrai_client import InfraiClient
from verified_dispatch.shipment_onboarding import (
    LogisticsOnboarding,
    OnboardingRequest,
    ShipmentRegistry,
)


async def main() -> None:
    client = InfraiClient()
    try:
        result = await LogisticsOnboarding(client, ShipmentRegistry()).onboard(
            OnboardingRequest(
                onboarding_id="acme-logistics-001",
                company_domain="logistics.example.com",
                owner_email="ops@logistics.example.com",
                txt_name="_infrai-onboarding.logistics.example.com",
                txt_content="replace-with-issued-challenge",
            )
        )
        print(json.dumps(result.model_dump(), indent=2))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
