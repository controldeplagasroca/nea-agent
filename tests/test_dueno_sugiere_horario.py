"""El dueño puede sugerir OTRO horario por mensaje («cambiar 7 pasado mañana 10 am»):
se agenda ahí y el cliente recibe la confirmación de visita agendada."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.approvals import parece_propuesta_de_horario, proponer_horario
from app.horarios import zona_agente
from tests.test_approvals import (
    CRM_CONV_ID, CRM_URL, END, IDENTITY, OWNER_ID, START, _pending, make_ctx, make_settings,
)


def test_reconoce_la_propuesta_con_folio():
    pend, resto = parece_propuesta_de_horario("cambiar 7 martes 10 am", [_pending(7), _pending(8)])
    assert pend is not None and pend.id == 7 and "martes" in resto and "10 am" in resto


def test_sin_folio_solo_vale_con_una_pendiente():
    assert parece_propuesta_de_horario("mejor el martes a las 10", [_pending(7)])[0] is not None
    assert parece_propuesta_de_horario("mejor el martes a las 10", [_pending(7), _pending(8)])[0] is None


def test_un_si_o_comentario_normal_no_es_propuesta():
    assert parece_propuesta_de_horario("sí 7", [_pending(7)])[0] is None
    assert parece_propuesta_de_horario("gracias, ahorita lo veo", [_pending(7)])[0] is None


@pytest.fixture
async def ctx_con_dueno():
    ctx = make_ctx(settings=make_settings(owner_wa_id=OWNER_ID))
    conv = await ctx.store.get_or_create_conversation(IDENTITY)
    yield ctx, conv
    await ctx.crm.aclose()


async def _pendiente(ctx, conv):
    return await ctx.store.create_pending_booking(
        conv.id, CRM_CONV_ID, "alemana", START, END, "lunes 20 de julio, 10:00",
        "Calle Amores 123", "lunes a las 10", START,
    )


def _mocks(respx_mock):
    respx_mock.put(f"{CRM_URL}/api/bot/ficha").mock(return_value=httpx.Response(200, json={"ficha": {}}))
    return respx_mock.post(f"{CRM_URL}/api/bot/messages").mock(
        return_value=httpx.Response(200, json={"messageId": "m"})
    )


async def test_el_dueno_sugiere_horario_y_se_le_pregunta_al_cliente_antes_de_agendar(ctx_con_dueno, respx_mock):
    ctx, conv = ctx_con_dueno
    pend = await _pendiente(ctx, conv)
    envio = _mocks(respx_mock)

    respuesta = await proponer_horario(ctx, pend, "cambiar 1 pasado manana 10 am")

    assert "le propuse al cliente" in respuesta
    assert ctx.calendar.booking_calls == []  # nada se agenda hasta que el cliente acepte
    tz = zona_agente(ctx.settings.agent_timezone)
    nueva = (await ctx.store.get_pending_booking(pend.id))
    esperado = (datetime.now(tz) + timedelta(days=2)).date()
    assert nueva.start_utc.astimezone(tz).date() == esperado and nueva.start_utc.astimezone(tz).hour == 10
    assert (nueva.end_utc - nueva.start_utc) == (END - START)
    assert nueva.estado == "esperando_cliente"
    texto = json.loads(envio.calls[-1].request.content)["text"]
    assert "ya no tenemos disponible ese horario" in texto and "se van programando" in texto
    assert "¿Te queda bien el" in texto and "10:00" in texto and "quedó agendada" not in texto
    caso = (await ctx.store.get_conversation(conv.id)).caso
    assert caso["contrapropuesta"]["folio"] == pend.id


async def test_hora_sin_am_pm_de_la_tarde(ctx_con_dueno, respx_mock):
    ctx, conv = ctx_con_dueno
    pend = await _pendiente(ctx, conv)
    _mocks(respx_mock)
    await proponer_horario(ctx, pend, "pasado manana a las 4")
    tz = zona_agente(ctx.settings.agent_timezone)
    assert (await ctx.store.get_pending_booking(pend.id)).start_utc.astimezone(tz).hour == 16


async def test_horario_lleno_no_agenda_y_sigue_pendiente(ctx_con_dueno, respx_mock):
    ctx, conv = ctx_con_dueno
    pend = await _pendiente(ctx, conv)
    envio = _mocks(respx_mock)
    ctx.calendar.cupo = False
    respuesta = await proponer_horario(ctx, pend, "pasado manana 10 am")
    assert "lleno" in respuesta and "PENDIENTE" in respuesta
    assert ctx.calendar.booking_calls == [] and envio.calls.call_count == 0
    assert (await ctx.store.get_pending_booking(pend.id)).estado == "pendiente"


async def test_sin_dia_u_hora_pide_aclarar(ctx_con_dueno, respx_mock):
    ctx, conv = ctx_con_dueno
    pend = await _pendiente(ctx, conv)
    _mocks(respx_mock)
    assert "No entendí" in await proponer_horario(ctx, pend, "cambiar mejor")
    assert ctx.calendar.booking_calls == []
