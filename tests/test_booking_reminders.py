"""ApprovalReminderWorker: reenvío indefinido al dueño mientras una cita
siga sin aprobar — ver app/booking_reminders.py."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.booking_reminders import ApprovalReminderWorker
from app.state import utcnow
from tests.conftest import CRM_CONV_ID, CRM_URL, IDENTITY, crm_context, make_ctx, make_settings

OWNER_ID = "525500000000"
START = datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc)
END = datetime(2026, 7, 20, 17, 30, tzinfo=timezone.utc)


@pytest.fixture
async def ctx_con_dueno():
    ctx = make_ctx(settings=make_settings(owner_wa_id=OWNER_ID, booking_reminder_minutes=10.0))
    conv = await ctx.store.get_or_create_conversation(IDENTITY)
    yield ctx, conv
    await ctx.crm.aclose()


async def test_reenvia_pendiente_vencida_y_reprograma(ctx_con_dueno, respx_mock):
    ctx, conv = ctx_con_dueno
    now = utcnow()
    vencida = await ctx.store.create_pending_booking(
        conv.id, CRM_CONV_ID, "alemana", START, END,
        "lunes 20 de julio, 10:00 am", "Calle Amores 123, depto 4B",
        "lunes a las 10", now - timedelta(minutes=1),
    )
    respx_mock.get(f"{CRM_URL}/api/bot/context", params={"waIdentity": OWNER_ID}).mock(
        return_value=httpx.Response(200, json=crm_context(conv_id="cv_owner"))
    )
    msg_route = respx_mock.post(f"{CRM_URL}/api/bot/messages").mock(
        return_value=httpx.Response(200, json={"messageId": "msg_1"})
    )

    worker = ApprovalReminderWorker(ctx)
    await worker.tick(now)

    assert msg_route.call_count == 1
    body = json.loads(msg_route.calls[0].request.content)
    assert body["conversationId"] == "cv_owner"
    assert f"#{vencida.id}" in body["text"]

    actualizada = await ctx.store.get_pending_booking(vencida.id)
    assert actualizada.reminders_sent == 1
    assert actualizada.next_reminder_at > now + timedelta(minutes=9)


async def test_no_reenvia_pendiente_que_todavia_no_vence(ctx_con_dueno, respx_mock):
    ctx, conv = ctx_con_dueno
    now = utcnow()
    await ctx.store.create_pending_booking(
        conv.id, CRM_CONV_ID, "alemana", START, END,
        "lunes 20 de julio, 10:00 am", "Calle Amores 123, depto 4B",
        "lunes a las 10", now + timedelta(minutes=5),
    )
    msg_route = respx_mock.post(f"{CRM_URL}/api/bot/messages").mock(
        return_value=httpx.Response(200, json={"messageId": "msg_1"})
    )

    worker = ApprovalReminderWorker(ctx)
    await worker.tick(now)

    assert msg_route.call_count == 0


async def test_no_reenvia_pendiente_ya_resuelta(ctx_con_dueno, respx_mock):
    ctx, conv = ctx_con_dueno
    now = utcnow()
    resuelta = await ctx.store.create_pending_booking(
        conv.id, CRM_CONV_ID, "alemana", START, END,
        "lunes 20 de julio, 10:00 am", "Calle Amores 123, depto 4B",
        "lunes a las 10", now - timedelta(minutes=1),
    )
    await ctx.store.resolve_pending_booking(resuelta.id, "aprobado")
    msg_route = respx_mock.post(f"{CRM_URL}/api/bot/messages").mock(
        return_value=httpx.Response(200, json={"messageId": "msg_1"})
    )

    worker = ApprovalReminderWorker(ctx)
    await worker.tick(now)

    assert msg_route.call_count == 0
