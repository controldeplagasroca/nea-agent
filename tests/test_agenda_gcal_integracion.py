"""Google Calendar + aprobación del dueño dentro del vertical de plagas.

Lo que se prueba es el pegamento: que el vertical ofrezca los horarios del
calendario propio con la regla de SU plaga, que la solicitud de visita quede con
folio y se le pida al dueño, y que su «sí N» / «no N» no llegue al modelo.
Los módulos de fondo (app/gcal.py, app/approvals.py) tienen sus propias pruebas.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest
import respx
from zoneinfo import ZoneInfo

from app.approvals import atender_respuesta_del_dueno
from app.plagas.aviso import avisar_al_dueno
from app.plagas.caso import Caso
from app.plagas.herramientas import RuntimeDePlagas
from app.state import InboundMessage, OfferedSlot
from tests.conftest import CRM_CONV_ID, CRM_URL, IDENTITY, FakeCalendar, make_ctx, make_settings
from tests.test_gcal import API_BASE, CAL_ID, NOW, calendar, mock_freebusy, sa_info  # noqa: F401

OWNER = "525529161746"
INICIO = datetime(2026, 8, 5, 16, 0, tzinfo=timezone.utc)  # miércoles 10:00 CDMX


def _ctx(**ajustes: Any):
    settings = make_settings(vertical="plagas", owner_wa_id=OWNER, **ajustes)
    return make_ctx(settings, calendar=FakeCalendar())


async def _runtime(ctx, plaga: str | None = "cucaracha_alemana") -> RuntimeDePlagas:
    conv = await ctx.store.get_or_create_conversation(IDENTITY)
    caso = Caso(plaga=plaga)
    caso.cotizacion = {"precio": 1200.0, "linea": "$1,200 MXN por visita", "bloque": "", "turno": 0}
    caso.direccion = {"calle": "Amores 123", "colonia": "Del Valle"}
    return RuntimeDePlagas(ctx, conv, CRM_CONV_ID, caso=caso, mensajes_lead=[])


# ------------------------------------------------------- consulta por día ---


async def test_get_day_domingo_esta_cerrado(calendar, respx_mock):  # noqa: F811
    mock_freebusy(respx_mock)
    slots, estado = await calendar.get_day("alemana", (NOW + timedelta(days=6)).date())
    assert (slots, estado) == ([], "closed")


async def test_get_day_dia_pasado(calendar):  # noqa: F811
    slots, estado = await calendar.get_day("alemana", (NOW - timedelta(days=1)).date())
    assert (slots, estado) == ([], "past")


async def test_get_day_devuelve_todas_las_horas_libres_menos_las_ocupadas(calendar, respx_mock):  # noqa: F811
    dia = (NOW + timedelta(days=2)).date()  # miércoles 5: pasa el aviso de 24 h
    ocupado = datetime(dia.year, dia.month, dia.day, 10, 0, tzinfo=ZoneInfo("America/Mexico_City"))
    mock_freebusy(respx_mock, [{
        "start": ocupado.astimezone(timezone.utc).isoformat(),
        "end": (ocupado + timedelta(minutes=60)).astimezone(timezone.utc).isoformat(),
    }])
    slots, estado = await calendar.get_day("alemana", dia)
    horas = [s["time"] for s in slots]
    assert estado == "available"
    # La alemana bloquea 90 min: ni las 09:00 ni las 09:30 ni las 10:00 caben
    # antes de la hora ocupada (10:00-11:00); la primera libre es a las 11:00.
    assert horas[0] == "11:00"
    assert not {"09:00", "09:30", "10:00", "10:30"} & set(horas)


# ------------------------------------------------- horarios del calendario ---


async def test_propone_horarios_del_calendario_con_la_regla_de_la_plaga():
    ctx = _ctx()
    rt = await _runtime(ctx, "cucaracha_americana")
    ctx.calendar.availability_queue.append([
        {"startUtc": "2026-08-05T16:00:00Z", "endUtc": "2026-08-05T18:00:00Z",
         "dayLabel": "el miércoles 5 de agosto", "time": "10:00", "label": "mié 5 ago, 10:00"},
    ])
    consulta = await rt._consultar_calendario(None)
    assert ctx.calendar.availability_calls[0]["service_key"] == "americana"
    assert consulta["slots"][0]["time"] == "10:00"


async def test_plaga_sin_regla_de_agenda_no_ofrece_horarios():
    from app.crm import AgendaUnavailable

    ctx = _ctx()
    rt = await _runtime(ctx, "termita_subterranea")
    with pytest.raises(AgendaUnavailable):
        await rt._consultar_calendario(None)
    assert ctx.calendar.availability_calls == []


async def test_con_calendario_la_agenda_no_depende_de_la_bandera_del_crm():
    from app.agenda import agenda_vigente

    ctx = _ctx()
    ctx.agenda_enabled = False
    assert await agenda_vigente(ctx) is True
    ctx.calendar = None
    assert await agenda_vigente(ctx) is False


# ----------------------------------------------------- solicitud con folio ---


@respx.mock
async def test_la_solicitud_de_visita_queda_con_folio_y_se_le_pide_al_dueno():
    ctx = _ctx()
    rt = await _runtime(ctx)
    respx.get(f"{CRM_URL}/api/bot/context").mock(return_value=httpx.Response(
        200, json={"conversation": {"id": "conv-dueno", "windowOpen": True}}
    ))
    envio = respx.post(f"{CRM_URL}/api/bot/messages").mock(return_value=httpx.Response(200, json={}))
    respx.put(f"{CRM_URL}/api/bot/ficha").mock(return_value=httpx.Response(200, json={}))
    slot = OfferedSlot(conversation_id=rt._conv.id, start_utc=INICIO, end_utc=None,
                       label="el miércoles 5 de agosto, 10:00")
    rt.caso.cita = {"label": "miércoles 5 de agosto, 10:00", "estado": "pendiente_de_aprobacion"}

    await rt._registrar_pendiente(slot)

    pendientes = await ctx.store.list_pending_bookings_pendientes()
    assert len(pendientes) == 1
    p = pendientes[0]
    assert p.service_key == "alemana"
    assert p.end_utc - p.start_utc == timedelta(minutes=90)  # regla de la alemana
    assert p.costo_cotizado == 1200.0 and p.telefono_cliente == IDENTITY
    assert rt.caso.cita["folio"] == p.id
    cuerpo = envio.calls.last.request.content.decode()
    assert f"sí {p.id}" in cuerpo and "conv-dueno" in cuerpo


async def test_sin_dueno_configurado_no_se_crea_pendiente():
    ctx = make_ctx(make_settings(vertical="plagas"), calendar=FakeCalendar())
    rt = await _runtime(ctx)
    slot = OfferedSlot(conversation_id=rt._conv.id, start_utc=INICIO, end_utc=None, label="x")
    await rt._registrar_pendiente(slot)
    assert await ctx.store.list_pending_bookings_pendientes() == []


async def test_con_folio_no_se_duplica_el_aviso_del_resumen():
    ctx = _ctx(aviso_dueno_wa=OWNER)
    caso = Caso(plaga="cucaracha_alemana")
    caso.cita = {"label": "x", "folio": 3}
    assert await avisar_al_dueno(
        ctx, identidad_lead=IDENTITY, context=None, caso=caso, motivo="cliente"
    ) is False


# -------------------------------------------------- respuesta del dueño ---


@respx.mock
async def test_el_si_con_folio_del_dueno_aprueba_y_no_llega_al_modelo():
    ctx = _ctx()
    rt = await _runtime(ctx)
    pend = await ctx.store.create_pending_booking(
        conversation_id=rt._conv.id, crm_conversation_id=CRM_CONV_ID, service_key="alemana",
        start_utc=INICIO, end_utc=INICIO + timedelta(minutes=90), label="miércoles 5, 10:00",
        direccion="Amores 123", dia_confirmado="miércoles",
        next_reminder_at=INICIO,
    )
    respx.get(f"{CRM_URL}/api/bot/context").mock(return_value=httpx.Response(
        200, json={"conversation": {"id": "conv-dueno"}}
    ))
    respx.post(f"{CRM_URL}/api/bot/messages").mock(return_value=httpx.Response(200, json={}))
    respx.put(f"{CRM_URL}/api/bot/ficha").mock(return_value=httpx.Response(200, json={}))

    atendido = await atender_respuesta_del_dueno(
        ctx, OWNER, [InboundMessage(wa_message_id="w1", identity=OWNER, type="text", text=f"sí {pend.id}")]
    )

    assert atendido is True
    assert ctx.calendar.booking_calls[0]["service_key"] == "alemana"
    assert (await ctx.store.get_pending_booking(pend.id)).estado == "aprobado"


async def test_un_mensaje_cualquiera_del_dueno_no_se_toma_por_respuesta():
    ctx = _ctx()
    atendido = await atender_respuesta_del_dueno(
        ctx, OWNER, [InboundMessage(wa_message_id="w2", identity=OWNER, type="text", text="hola")]
    )
    assert atendido is False


@respx.mock
async def test_si_no_se_pudo_avisar_al_cliente_el_dueno_se_entera():
    ctx = _ctx()
    rt = await _runtime(ctx)
    pend = await ctx.store.create_pending_booking(
        conversation_id=rt._conv.id, crm_conversation_id=CRM_CONV_ID, service_key="alemana",
        start_utc=INICIO, end_utc=INICIO + timedelta(minutes=90), label="miércoles 5, 10:00",
        direccion="Amores 123", dia_confirmado="miércoles", next_reminder_at=INICIO,
    )
    respx.post(f"{CRM_URL}/api/bot/messages").mock(
        return_value=httpx.Response(409, json={"error": "ai_paused"})
    )
    respx.put(f"{CRM_URL}/api/bot/ficha").mock(return_value=httpx.Response(200, json={}))
    from app.approvals import resolver_aprobacion

    texto = await resolver_aprobacion(ctx, pend, True)

    assert "No pude avisarle al cliente" in texto
    assert (await ctx.store.get_pending_booking(pend.id)).estado == "aprobado"
