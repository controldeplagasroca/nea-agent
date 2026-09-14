"""POST /internal/service-events: aviso de ROCA Ops/Hermes sobre cambios de
servicio (cancelar/reagendar) para citas que Nea agendo."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.main import create_app
from tests.conftest import make_ctx, make_settings

SECRET = "sync-secreto"


@pytest.fixture
def ctx_with_secret():
    return make_ctx(settings=make_settings(service_sync_secret=SECRET))


@pytest.fixture
async def client(ctx_with_secret):
    app = create_app(ctx=ctx_with_secret)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://bot.test") as c:
        yield c
    await ctx_with_secret.crm.aclose()
    await ctx_with_secret.calendar.aclose()


async def _seed_booking(ctx, event_id: str = "evt_ext_1") -> int:
    conv_id = 42
    start = datetime.now(timezone.utc) + timedelta(days=1)
    await ctx.store.save_calendar_booking(
        conv_id, event_id, "fumigacion", start, start + timedelta(hours=1)
    )
    return conv_id


async def test_sin_secreto_configurado_rechaza(client):
    # ctx_with_secret ya trae secreto, este caso prueba el default vacio.
    ctx = make_ctx()  # service_sync_secret="" por default
    app = create_app(ctx=ctx)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://bot.test") as c:
        resp = await c.post(
            "/internal/service-events",
            json={"calendarEventId": "evt_1", "eventType": "cancelado"},
        )
    assert resp.status_code == 401


async def test_secreto_invalido_rechaza(client):
    resp = await client.post(
        "/internal/service-events",
        headers={"X-Service-Sync-Secret": "incorrecto"},
        json={"calendarEventId": "evt_1", "eventType": "cancelado"},
    )
    assert resp.status_code == 401


async def test_evento_sin_booking_activo_no_falla(client):
    resp = await client.post(
        "/internal/service-events",
        headers={"X-Service-Sync-Secret": SECRET},
        json={"calendarEventId": "evt-que-no-existe", "eventType": "cancelado"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "matched": False}


async def test_cancelar_marca_booking_cancelado(client, ctx_with_secret):
    conv_id = await _seed_booking(ctx_with_secret, "evt_cancel_1")
    assert await ctx_with_secret.store.get_active_calendar_booking(conv_id) is not None

    resp = await client.post(
        "/internal/service-events",
        headers={"X-Service-Sync-Secret": SECRET},
        json={"calendarEventId": "evt_cancel_1", "eventType": "cancelado"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "matched": True, "conversation_id": conv_id}
    assert await ctx_with_secret.store.get_active_calendar_booking(conv_id) is None


async def test_reagendar_mueve_el_booking(client, ctx_with_secret):
    conv_id = await _seed_booking(ctx_with_secret, "evt_resched_1")

    resp = await client.post(
        "/internal/service-events",
        headers={"X-Service-Sync-Secret": SECRET},
        json={
            "calendarEventId": "evt_resched_1",
            "eventType": "reagendado",
            "nuevaFecha": "2027-01-15",
            "nuevaHora": "10:00",
        },
    )

    assert resp.status_code == 200
    booking = await ctx_with_secret.store.get_active_calendar_booking(conv_id)
    assert booking is not None
    # 10:00 America/Mexico_City == 16:00 UTC (UTC-6, sin horario de verano).
    assert booking.start_utc.hour == 16
    assert booking.start_utc.day == 15


async def test_asignado_no_cambia_el_booking(client, ctx_with_secret):
    conv_id = await _seed_booking(ctx_with_secret, "evt_asignado_1")
    before = await ctx_with_secret.store.get_active_calendar_booking(conv_id)

    resp = await client.post(
        "/internal/service-events",
        headers={"X-Service-Sync-Secret": SECRET},
        json={"calendarEventId": "evt_asignado_1", "eventType": "asignado"},
    )

    assert resp.status_code == 200
    after = await ctx_with_secret.store.get_active_calendar_booking(conv_id)
    assert after is not None
    assert after.start_utc == before.start_utc
