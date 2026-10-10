from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .infrai_client import InfraiClient, InfraiError
from .shipment_onboarding import (
    LogisticsOnboarding,
    OnboardingRequest,
    OnboardingResult,
    ShipmentEvent,
    ShipmentRegistry,
)

client: InfraiClient | None = None
registry = ShipmentRegistry()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global client
    client = InfraiClient()
    yield
    await client.close()
    client = None


app = FastAPI(title="Verified Domain Dispatch", lifespan=lifespan)


@app.post("/onboard", response_model=OnboardingResult)
async def onboard(request: OnboardingRequest) -> OnboardingResult:
    if client is None:
        raise HTTPException(status_code=503, detail="service is starting")
    try:
        return await LogisticsOnboarding(client, registry).onboard(request)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@app.post("/companies/{domain}/shipments/events", status_code=202)
async def record_shipment_event(domain: str, event: ShipmentEvent) -> dict[str, int | str]:
    try:
        event_number = registry.record(domain, event)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "shipment_id": event.shipment_id,
        "event_number": event_number,
        "status": "accepted",
    }
