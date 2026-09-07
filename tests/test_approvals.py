"""Parseo de la respuesta del dueño (sí/no + folio) y ejecución de la
aprobación/rechazo — ver app/approvals.py."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from app.approvals import (
    enviar_solicitud_aprobacion,
    formatear_solicitud,
    listar_pendientes_para_dueno,
    parece_aprobacion,
    resolver_aprobacion,
)
from app.gcal import CalendarSlotTaken
from app.state import PendingBooking
from tests.conftest import CRM_CONV_ID, CRM_URL, IDENTITY, crm_context, make_ctx, make_settings

OWNER_ID = "525500000000"
START = datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc)
END = datetime(2026, 7, 20, 17, 30, tzinfo=timezone.utc)


def _pending(id: int = 7, service_key: str = "alemana") -> PendingBooking:
    return PendingBooking(
        id=id,
        conversation_id=1,
        crm_conversation_id=CRM_CONV_ID,
        service_key=service_key,
        start_utc=START,
        end_utc=END,
        label="lunes 20 de julio, 10:00 am",
        direccion="Calle Amores 123, depto 4B",
        dia_confirmado="lunes a las 10",
    )


# --------------------------------------------------------------- parseo ---


def test_formatear_solicitud_incluye_folio_plaga_y_direccion():
    texto = formatear_solicitud(_pending())
    assert "#7" in texto
    assert "cucaracha alemana" in texto
    assert "Calle Amores 123, depto 4B" in texto


def test_parece_aprobacion_una_pendiente_si_sin_folio():
    kind, pending, aprueba = parece_aprobacion("si", [_pending(7)])
    assert kind == "resuelto"
    assert pending.id == 7
    assert aprueba is True


def test_parece_aprobacion_una_pendiente_no_sin_folio():
    kind, pending, aprueba = parece_aprobacion("no", [_pending(7)])
    assert kind == "resuelto"
    assert pending.id == 7
    assert aprueba is False


def test_parece_aprobacion_varias_pendientes_con_folio():
    pendientes = [_pending(7), _pending(12)]
    kind, pending, aprueba = parece_aprobacion("sí 12", pendientes)
    assert kind == "resuelto"
    assert pending.id == 12
    assert aprueba is True


def test_parece_aprobacion_varias_pendientes_sin_folio_es_ambiguo():
    pendientes = [_pending(7), _pending(12)]
    kind, pending, aprueba = parece_aprobacion("si", pendientes)
    assert kind == "ambiguo"
    assert pending is None


def test_parece_aprobacion_folio_inexistente_es_ambiguo():
    kind, pending, aprueba = parece_aprobacion("si 99", [_pending(7)])
    assert kind == "ambiguo"
    assert pending is None


def test_parece_aprobacion_sinonimos_aprobar_rechazar():
    kind, _, aprueba = parece_aprobacion("aprobar 7", [_pending(7)])
    assert (kind, aprueba) == ("resuelto", True)
    kind, _, aprueba = parece_aprobacion("rechazar 7", [_pending(7)])
    assert (kind, aprueba) == ("resuelto", False)


def test_parece_aprobacion_texto_no_relacionado_no_reconocido():
    kind, pending, aprueba = parece_aprobacion(
        "hola tengo un problema de cucarachas", [_pending(7)]
    )
    assert kind == "no_reconocido"


def test_parece_aprobacion_sin_pendientes_no_reconocido():
    kind, pending, aprueba = parece_aprobacion("si", [])
    assert kind == "no_reconocido"


def test_listar_pendientes_para_dueno_incluye_todos_los_folios():
    texto = listar_pendientes_para_dueno([_pending(7), _pending(12)])
    assert "#7" in texto
    assert "#12" in texto


# ------------------------------------------------------------ ejecución ---


@pytest.fixture
async def ctx_con_dueno():
    ctx = make_ctx(settings=make_settings(owner_wa_id=OWNER_ID))
    conv = await ctx.store.get_or_create_conversation(IDENTITY)
    yield ctx, conv
    await ctx.crm.aclose()


async def test_enviar_solicitud_aprobacion_manda_al_dueno(ctx_con_dueno, respx_mock):
    ctx, conv = ctx_con_dueno
    respx_mock.get(f"{CRM_URL}/api/bot/context", params={"waIdentity": OWNER_ID}).mock(
        return_value=httpx.Response(200, json=crm_context(conv_id="cv_owner"))
    )
    msg_route = respx_mock.post(f"{CRM_URL}/api/bot/messages").mock(
        return_value=httpx.Response(200, json={"messageId": "msg_1"})
    )
    ok = await enviar_solicitud_aprobacion(ctx, _pending(7))
    assert ok is True
    body = json.loads(msg_route.calls[0].request.content)
    assert body["conversationId"] == "cv_owner"
    assert "#7" in body["text"]


async def test_resolver_aprobacion_aprobado_reserva_y_avisa_al_lead(
    ctx_con_dueno, respx_mock
):
    ctx, conv = ctx_con_dueno
    pending = await ctx.store.create_pending_booking(
        conv.id, CRM_CONV_ID, "alemana", START, END,
        "lunes 20 de julio, 10:00 am", "Calle Amores 123, depto 4B",
        "lunes a las 10", START,
    )
    ficha_route = respx_mock.put(f"{CRM_URL}/api/bot/ficha").mock(
        return_value=httpx.Response(200, json={"ficha": {}, "stageMoved": False})
    )
    lead_msg_route = respx_mock.post(f"{CRM_URL}/api/bot/messages").mock(
        return_value=httpx.Response(200, json={"messageId": "msg_1"})
    )
    respuesta_dueno = await resolver_aprobacion(ctx, pending, True)
    assert "confirmada" in respuesta_dueno.lower() or "listo" in respuesta_dueno.lower()

    assert ctx.calendar.booking_calls[0]["service_key"] == "alemana"
    active = await ctx.store.get_active_calendar_booking(conv.id)
    assert active is not None
    assert active.google_event_id == "evt_1"

    resolved = await ctx.store.get_pending_booking(pending.id)
    assert resolved.estado == "aprobado"

    lead_body = json.loads(lead_msg_route.calls[-1].request.content)
    assert lead_body["conversationId"] == CRM_CONV_ID
    assert "confirmada" in lead_body["text"].lower()

    ficha_body = json.loads(ficha_route.calls[0].request.content)
    assert ficha_body["ficha"]["geo"] == "Calle Amores 123, depto 4B"
    assert ficha_body["ficha"]["resultado"] == "agendo"


async def test_resolver_aprobacion_rechazado_no_reserva_avisa_al_lead(
    ctx_con_dueno, respx_mock
):
    ctx, conv = ctx_con_dueno
    pending = await ctx.store.create_pending_booking(
        conv.id, CRM_CONV_ID, "alemana", START, END,
        "lunes 20 de julio, 10:00 am", "Calle Amores 123, depto 4B",
        "lunes a las 10", START,
    )
    lead_msg_route = respx_mock.post(f"{CRM_URL}/api/bot/messages").mock(
        return_value=httpx.Response(200, json={"messageId": "msg_1"})
    )
    respuesta_dueno = await resolver_aprobacion(ctx, pending, False)
    assert "rechazada" in respuesta_dueno.lower()
    assert ctx.calendar.booking_calls == []

    resolved = await ctx.store.get_pending_booking(pending.id)
    assert resolved.estado == "rechazado"

    lead_body = json.loads(lead_msg_route.calls[-1].request.content)
    assert lead_body["conversationId"] == CRM_CONV_ID


async def test_resolver_aprobacion_slot_ocupado_al_aprobar_rechaza_y_avisa(
    ctx_con_dueno, respx_mock
):
    """Alguien más tomó el horario mientras se esperaba la aprobación."""
    ctx, conv = ctx_con_dueno
    ctx.calendar.create_result = CalendarSlotTaken([])
    pending = await ctx.store.create_pending_booking(
        conv.id, CRM_CONV_ID, "alemana", START, END,
        "lunes 20 de julio, 10:00 am", "Calle Amores 123, depto 4B",
        "lunes a las 10", START,
    )
    respx_mock.post(f"{CRM_URL}/api/bot/messages").mock(
        return_value=httpx.Response(200, json={"messageId": "msg_1"})
    )
    respuesta_dueno = await resolver_aprobacion(ctx, pending, True)
    assert "ocup" in respuesta_dueno.lower()

    resolved = await ctx.store.get_pending_booking(pending.id)
    assert resolved.estado == "rechazado"
    active = await ctx.store.get_active_calendar_booking(conv.id)
    assert active is None
