"""4 oct (Ethel): el técnico propuso otro horario y el bot le dijo «quedó agendada» sin
preguntarle. Ahora el cliente decide: acepta (se agenda) o propone otro (se vuelve a empezar)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
import respx

from app.approvals import atender_respuesta_del_dueno
from app.gcal import SERVICIO_DE_PLAGA
from app.horarios import zona_agente
from app.plagas.caso import Caso, paso_actual
from app.plagas.turno import herramienta_obligada
from tests.conftest import CRM_CONV_ID, CRM_URL
from tests.test_escenarios_sinteticos import (
    DUENO, _con_plaga, _confirmada, _crm_con_dueno, _dueno, _miercoles_10, _slot, _textos_al_cliente,
)


async def _runtime_con_lo_guardado(rt, ctx):
    """Un turno nuevo del cliente: el expediente se lee de lo que quedó guardado."""
    rt.caso = Caso.desde((await ctx.store.get_conversation(rt._conv.id)).caso)
    rt.texto_garantizado = None
    return rt


async def _dueno_sugiere(plaga="chinches"):
    rt, ctx = await _con_plaga(plaga)
    envio = _crm_con_dueno()
    await rt._solicitar_visita(_slot(rt))
    await ctx.store.update_conversation(rt._conv.id, caso=rt.caso.a_dict())
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]
    await atender_respuesta_del_dueno(ctx, DUENO, _dueno(f"cambiar {pend.id} pasado mañana 10 am"))
    return rt, ctx, envio, pend


@pytest.mark.parametrize("plaga", ["cucaracha_alemana", "chinches", "arana"])
@respx.mock
async def test_el_cliente_acepta_el_horario_sugerido_y_se_agenda(plaga):
    rt, ctx, envio, pend = await _dueno_sugiere(plaga)
    assert "ya no tenemos disponible ese horario" in _textos_al_cliente(envio)[-1]
    assert ctx.calendar.booking_calls == []
    rt = await _runtime_con_lo_guardado(rt, ctx)
    assert paso_actual(rt.caso).nombre == "contrapropuesta"

    res = await rt.execute("responder_horario_sugerido", {"acepta": True})

    assert res["estado"] == "aceptada"
    assert ctx.calendar.booking_calls[0]["service_key"] == SERVICIO_DE_PLAGA[plaga]
    tz = zona_agente(ctx.settings.agent_timezone)
    assert ctx.calendar.booking_calls[0]["start_utc"].astimezone(tz).hour == 10
    assert "Tu visita quedó agendada" in rt.texto_garantizado
    # el texto sale UNA vez, como respuesta del turno; no se manda aparte
    assert not any("quedó agendada" in t for t in _textos_al_cliente(envio))
    assert rt.caso.contrapropuesta is None and rt.caso.cita["estado"] == "confirmada"
    assert "aceptó" in envio.calls.last.request.content.decode()  # el dueño se entera


@respx.mock
async def test_el_cliente_propone_otro_horario_se_libera_y_se_sigue_con_los_horarios_reales():
    rt, ctx, envio, pend = await _dueno_sugiere("chinches")
    rt = await _runtime_con_lo_guardado(rt, ctx)

    res = await rt.execute("responder_horario_sugerido", {"acepta": False})

    assert res["estado"] == "rechazada" and "propose_slots" in res["instrucciones"]
    assert (await ctx.store.get_pending_booking(pend.id)).estado == "rechazado"
    assert rt.caso.cita is None and rt.caso.contrapropuesta is None
    assert ctx.calendar.booking_calls == []
    assert "no puede" in envio.calls.last.request.content.decode()
    # y el flujo normal sigue: otro horario -> nueva solicitud al dueño
    rt.caso.aceptada = True
    await rt._solicitar_visita(_slot(rt, etiqueta="jueves 8 de octubre, 11:00"))
    assert len(await ctx.store.list_pending_bookings_pendientes()) == 1


@respx.mock
async def test_reagendo_con_sugerencia_del_dueno_acepta_y_el_evento_se_mueve():
    rt, ctx = await _confirmada("cucaracha_alemana")
    rt._mensajes_lead = ["¿podemos pasarla al miércoles a las 10 am?"]
    envio = _crm_con_dueno()
    _, slot = _miercoles_10()
    ctx.calendar.availability_queue.append([slot])
    await rt.execute("cambiar_visita", {"accion": "reagendar", "motivo": "imprevisto"})
    await ctx.store.update_conversation(rt._conv.id, caso=rt.caso.a_dict())
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]
    await atender_respuesta_del_dueno(ctx, DUENO, _dueno(f"cambiar {pend.id} pasado mañana 11 am"))
    assert ctx.calendar.reschedule_calls == [] and "ya no tenemos" in _textos_al_cliente(envio)[-1]

    rt = await _runtime_con_lo_guardado(rt, ctx)
    res = await rt.execute("responder_horario_sugerido", {"acepta": True})

    assert res["estado"] == "aceptada"
    tz = zona_agente(ctx.settings.agent_timezone)
    assert ctx.calendar.reschedule_calls[0]["new_start"].astimezone(tz).hour == 11
    assert "reagendada" in rt.texto_garantizado and rt.caso.cambio is None


@respx.mock
async def test_reagendo_con_sugerencia_rechazada_deja_la_visita_de_antes():
    rt, ctx = await _confirmada("chinches")
    rt._mensajes_lead = ["¿podemos pasarla al miércoles a las 10 am?"]
    _crm_con_dueno()
    _, slot = _miercoles_10()
    ctx.calendar.availability_queue.append([slot])
    await rt.execute("cambiar_visita", {"accion": "reagendar", "motivo": "imprevisto"})
    await ctx.store.update_conversation(rt._conv.id, caso=rt.caso.a_dict())
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]
    await atender_respuesta_del_dueno(ctx, DUENO, _dueno(f"cambiar {pend.id} pasado mañana 11 am"))

    rt = await _runtime_con_lo_guardado(rt, ctx)
    res = await rt.execute("responder_horario_sugerido", {"acepta": False})

    assert "cambiar_visita" in res["instrucciones"]
    assert rt.caso.cita["estado"] == "confirmada" and rt.caso.cambio is None
    assert (await ctx.store.get_active_calendar_booking(rt._conv.id)) is not None


@respx.mock
async def test_un_si_corto_fuerza_la_herramienta_y_una_respuesta_larga_no():
    rt, ctx, envio, pend = await _dueno_sugiere("chinches")
    rt = await _runtime_con_lo_guardado(rt, ctx)
    assert herramienta_obligada(rt.caso, "sí, me queda bien", agenda=True) == "responder_horario_sugerido"
    assert herramienta_obligada(rt.caso, "sí pero mejor el jueves a las 11 de la mañana por favor", agenda=True) is None


@respx.mock
async def test_si_el_calendario_falla_al_aceptar_no_se_dice_que_quedo_agendada():
    from app.gcal import CalendarError

    rt, ctx, envio, pend = await _dueno_sugiere("chinches")
    rt = await _runtime_con_lo_guardado(rt, ctx)
    ctx.calendar.create_result = CalendarError("boom")

    res = await rt.execute("responder_horario_sugerido", {"acepta": True})

    assert res["estado"] == "por_confirmar"
    assert "agendada" not in rt.texto_garantizado
    assert rt.caso.cita.get("estado") != "confirmada"
