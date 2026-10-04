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


def test_las_dos_cucarachas_bloquean_90_minutos():
    """60 min de aplicación + 30 de traslado promedio. Es tiempo interno de
    agenda: no se le dice al cliente."""
    from app.gcal import SERVICE_RULES

    assert SERVICE_RULES["alemana"].duration_minutes == 90
    assert SERVICE_RULES["americana"].duration_minutes == 90


async def test_9_30_pm_no_aparta_el_horario_de_las_9_30_am():
    """El caso real: se ofreció la mañana, el lead dijo «9:30 pm» y el modelo
    apartó las 09:30 am. El servidor lo detiene y manda a preguntar."""
    ctx = _ctx()
    rt = await _runtime(ctx)
    am = datetime(2026, 8, 5, 15, 30, tzinfo=timezone.utc)  # 09:30 CDMX
    await ctx.store.replace_offered_slots(
        rt._conv.id,
        [OfferedSlot(conversation_id=rt._conv.id, start_utc=am, end_utc=None,
                     label="el miércoles 5 de agosto, 09:30")],
    )
    await ctx.store.add_message(rt._conv.id, "user", "sí, mañana a las 9:30 pm")

    elegido, error = await rt._resolve_offered({"start_utc": "2026-08-05T15:30:00Z"}, "book_session")

    assert elegido is None
    assert error["error"] == "ambiguo_am_pm"
    assert "de la mañana o de la noche" in error["mensaje_al_cliente"]


async def test_hora_que_si_coincide_se_agenda():
    ctx = _ctx()
    rt = await _runtime(ctx)
    am = datetime(2026, 8, 5, 15, 30, tzinfo=timezone.utc)
    await ctx.store.replace_offered_slots(
        rt._conv.id,
        [OfferedSlot(conversation_id=rt._conv.id, start_utc=am, end_utc=None, label="09:30")],
    )
    await ctx.store.add_message(rt._conv.id, "user", "mañana a las 9:30 am")

    elegido, error = await rt._resolve_offered({"start_utc": "2026-08-05T15:30:00Z"}, "book_session")

    assert error is None and elegido is not None


# ------------------------------------------- cierre del ciclo de la cita ---


async def _con_solicitud(ctx):
    """Una solicitud con folio ya registrada, con su expediente en la conversación."""
    rt = await _runtime(ctx)
    rt.caso.cita = {"label": "mañana lunes 5 de octubre, 11:00", "estado": "pendiente_de_aprobacion"}
    rt.caso.direccion = {"calle": "Matías Romero 1014", "colonia": "Valle Centro"}
    slot = OfferedSlot(conversation_id=rt._conv.id, start_utc=INICIO, end_utc=None,
                       label="mañana lunes 5 de octubre, 11:00")
    with respx.mock:
        respx.get(f"{CRM_URL}/api/bot/context").mock(return_value=httpx.Response(
            200, json={"conversation": {"id": "dueno", "windowOpen": True}}))
        respx.post(f"{CRM_URL}/api/bot/messages").mock(return_value=httpx.Response(200, json={}))
        respx.put(f"{CRM_URL}/api/bot/ficha").mock(return_value=httpx.Response(200, json={}))
        await rt._solicitar_visita(slot)
    await ctx.store.update_conversation(rt._conv.id, caso=rt.caso.a_dict())
    return rt


async def test_con_folio_la_ia_sigue_encendida_para_poder_confirmarle_al_cliente():
    ctx = _ctx()
    rt = await _con_solicitud(ctx)
    assert rt.handoff_reason is None  # no se pasa la conversación: el CRM apagaría la IA
    assert rt.booked is True


async def test_el_texto_al_cliente_no_se_contradice():
    ctx = _ctx()
    rt = await _con_solicitud(ctx)
    texto = rt.texto_garantizado
    assert "recibí tu solicitud" in texto and "Todavía no está confirmada" in texto
    assert "Listo" not in texto and "✅" not in texto


@respx.mock
async def test_al_aprobar_el_cliente_recibe_la_confirmacion_y_el_expediente_cambia():
    from app.approvals import resolver_aprobacion

    ctx = _ctx()
    rt = await _con_solicitud(ctx)
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]
    envio = respx.post(f"{CRM_URL}/api/bot/messages").mock(return_value=httpx.Response(200, json={}))
    respx.put(f"{CRM_URL}/api/bot/ficha").mock(return_value=httpx.Response(200, json={}))

    texto = await resolver_aprobacion(ctx, pend, True)

    cuerpo = envio.calls.last.request.content.decode()
    assert "Confirmado" in cuerpo and "mañana" not in cuerpo  # sin «mañana»: se aprueba días después
    assert "lunes 5 de octubre, 11:00" in cuerpo
    assert "avisado al cliente" in texto and "No pude" not in texto
    conv = await ctx.store.get_conversation(rt._conv.id)
    assert conv.caso["cita"]["estado"] == "confirmada"
    from app.plagas.caso import Caso, paso_actual
    assert paso_actual(Caso.desde(conv.caso)).nombre == "visita_confirmada"


@respx.mock
async def test_al_rechazar_el_expediente_queda_libre_para_ofrecer_otro_horario():
    from app.approvals import resolver_aprobacion

    ctx = _ctx()
    rt = await _con_solicitud(ctx)
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]
    respx.post(f"{CRM_URL}/api/bot/messages").mock(return_value=httpx.Response(200, json={}))

    await resolver_aprobacion(ctx, pend, False)

    conv = await ctx.store.get_conversation(rt._conv.id)
    assert conv.caso["cita"] is None and conv.caso["escalado"] == ""


@respx.mock
async def test_si_no_se_pudo_avisar_el_texto_al_dueno_no_dice_que_ya_se_aviso():
    from app.approvals import resolver_aprobacion

    ctx = _ctx()
    await _con_solicitud(ctx)
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]
    respx.post(f"{CRM_URL}/api/bot/messages").mock(
        return_value=httpx.Response(409, json={"error": "ai_paused"})
    )
    respx.put(f"{CRM_URL}/api/bot/ficha").mock(return_value=httpx.Response(200, json={}))

    texto = await resolver_aprobacion(ctx, pend, True)

    assert "avisado al cliente" not in texto
    assert "No pude avisarle al cliente" in texto
