"""Escenarios sintéticos de punta a punta (sin LLM real): por cada plaga que se agenda,
el ciclo completo cliente -> técnico -> calendario, más cancelaciones y reagendos.

Cada escenario recorre los mismos candados que producción: el horario sale del calendario,
el dueño aprueba por WhatsApp («sí N», «no N», «cambiar N …») y el cliente recibe lo que
el servidor escribe. Si un escenario falla, el comportamiento cambió.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
import respx

from app.approvals import atender_respuesta_del_dueno
from app.gcal import SERVICIO_DE_PLAGA
from app.horarios import zona_agente
from app.plagas.caso import Caso
from app.state import OfferedSlot
from tests.conftest import CRM_CONV_ID, CRM_URL
from tests.test_confirmacion_inmediata import INICIO, _rt

DUENO = "525529161746"
PLAGAS = sorted(SERVICIO_DE_PLAGA)


def _dueno(texto: str):
    return [SimpleNamespace(text=texto)]


async def _con_plaga(plaga: str):
    rt, ctx = await _rt(inmediata=False)
    rt.caso.plaga = plaga
    rt._nombre_lead = "Ethel"
    return rt, ctx


def _textos_al_cliente(envio) -> list[str]:
    cuerpos = [json.loads(c.request.content) for c in envio.calls]
    return [c["text"] for c in cuerpos if c.get("conversationId") == CRM_CONV_ID]


def _slot(rt, inicio=INICIO, etiqueta="mañana lunes 5 de octubre, 10:00"):
    return OfferedSlot(conversation_id=rt._conv.id, start_utc=inicio, end_utc=None, label=etiqueta)


def _crm_con_dueno():
    respx.get(f"{CRM_URL}/api/bot/context", params={"waIdentity": DUENO}).mock(
        return_value=httpx.Response(
            200, json={"conversation": {"id": "cv_dueno", "windowOpen": True, "aiEnabled": True}}
        )
    )
    envio = respx.post(f"{CRM_URL}/api/bot/messages").mock(return_value=httpx.Response(200, json={}))
    respx.put(f"{CRM_URL}/api/bot/ficha").mock(return_value=httpx.Response(200, json={}))
    return envio


@pytest.mark.parametrize("plaga", PLAGAS)
@respx.mock
async def test_cada_plaga_se_agenda_y_el_dueno_aprueba(plaga):
    rt, ctx = await _con_plaga(plaga)
    envio = _crm_con_dueno()

    await rt._solicitar_visita(_slot(rt))
    assert ctx.calendar.booking_calls == []  # nada en el calendario antes de aprobar
    assert "ese horario sí lo tenemos disponible" in rt.texto_garantizado
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]
    assert pend.service_key == SERVICIO_DE_PLAGA[plaga]

    assert await atender_respuesta_del_dueno(ctx, DUENO, _dueno(f"sí {pend.id}")) is True

    assert ctx.calendar.booking_calls[0]["service_key"] == SERVICIO_DE_PLAGA[plaga]
    assert "quedó agendada" in _textos_al_cliente(envio)[-1]
    assert (await ctx.store.get_active_calendar_booking(rt._conv.id)) is not None


@pytest.mark.parametrize("plaga", ["cucaracha_alemana", "chinches", "roedores"])
@respx.mock
async def test_si_el_dueno_rechaza_no_hay_evento_y_el_cliente_recibe_alternativas(plaga):
    rt, ctx = await _con_plaga(plaga)
    envio = _crm_con_dueno()
    await rt._solicitar_visita(_slot(rt))
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]

    await atender_respuesta_del_dueno(ctx, DUENO, _dueno(f"no {pend.id}"))

    assert ctx.calendar.booking_calls == []
    assert (await ctx.store.get_active_calendar_booking(rt._conv.id)) is None
    assert "No tengo disponible ese horario" in _textos_al_cliente(envio)[-1]


@pytest.mark.parametrize("plaga", ["cucaracha_alemana", "chinches", "hormiga"])
@respx.mock
async def test_el_dueno_sugiere_otro_horario_y_queda_agendado_ahi(plaga):
    rt, ctx = await _con_plaga(plaga)
    envio = _crm_con_dueno()
    await rt._solicitar_visita(_slot(rt))
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]
    hora = "5 pm" if plaga == "hormiga" else "10 am"  # la hormiga solo se agenda en sus ventanas

    await atender_respuesta_del_dueno(ctx, DUENO, _dueno(f"cambiar {pend.id} pasado mañana {hora}"))

    tz = zona_agente(ctx.settings.agent_timezone)
    inicio = ctx.calendar.booking_calls[0]["start_utc"].astimezone(tz)
    assert inicio.date() == (datetime.now(tz) + timedelta(days=2)).date()
    assert inicio.hour == (17 if plaga == "hormiga" else 10)
    assert "quedó agendada" in _textos_al_cliente(envio)[-1]


async def _confirmada(plaga: str):
    rt, ctx = await _con_plaga(plaga)
    rt.caso.cita = {"label": "lunes 5 de octubre, 10:00", "estado": "confirmada", "folio": 1}
    await ctx.store.save_calendar_booking(
        rt._conv.id, "evt_1", SERVICIO_DE_PLAGA[plaga], INICIO, INICIO + timedelta(minutes=90)
    )
    return rt, ctx


def _miercoles_10():
    hoy = datetime.now(timezone.utc).date()
    dias = (2 - hoy.weekday()) % 7 or 7
    inicio = datetime.combine(hoy + timedelta(days=dias), datetime.min.time(), timezone.utc).replace(hour=16)
    return inicio, {
        "startUtc": inicio.isoformat().replace("+00:00", "Z"),
        "endUtc": (inicio + timedelta(minutes=90)).isoformat().replace("+00:00", "Z"),
        "dayLabel": "el miércoles", "time": "10:00",
    }


@pytest.mark.parametrize("plaga", ["cucaracha_alemana", "cucaracha_americana", "chinches", "arana"])
@respx.mock
async def test_reagendo_hora_libre_el_tecnico_aprueba_y_el_evento_se_mueve(plaga):
    rt, ctx = await _confirmada(plaga)
    rt._mensajes_lead = ["me surgió algo, ¿podemos pasarla al miércoles a las 10 am?"]
    envio = _crm_con_dueno()
    inicio, slot = _miercoles_10()
    ctx.calendar.availability_queue.append([slot])

    await rt.execute("cambiar_visita", {"accion": "reagendar", "motivo": "imprevisto"})
    await ctx.store.update_conversation(rt._conv.id, caso=rt.caso.a_dict())
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]
    assert pend.kind == "reagendar" and ctx.calendar.reschedule_calls == []

    await atender_respuesta_del_dueno(ctx, DUENO, _dueno(f"sí {pend.id}"))

    assert ctx.calendar.reschedule_calls[0]["new_start"] == inicio
    assert "reagendada" in _textos_al_cliente(envio)[-1]
    caso = Caso.desde((await ctx.store.get_conversation(rt._conv.id)).caso)
    assert caso.cambio is None and caso.cita["estado"] == "confirmada"


@respx.mock
async def test_reagendo_el_dueno_propone_otra_hora_y_se_mueve_ahi():
    rt, ctx = await _confirmada("cucaracha_alemana")
    rt._mensajes_lead = ["¿podemos pasarla al miércoles a las 10 am?"]
    envio = _crm_con_dueno()
    _, slot = _miercoles_10()
    ctx.calendar.availability_queue.append([slot])
    await rt.execute("cambiar_visita", {"accion": "reagendar"})
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]

    await atender_respuesta_del_dueno(ctx, DUENO, _dueno(f"cambiar {pend.id} pasado mañana 11 am"))

    tz = zona_agente(ctx.settings.agent_timezone)
    nuevo = ctx.calendar.reschedule_calls[0]["new_start"].astimezone(tz)
    assert nuevo.hour == 11 and "reagendada" in _textos_al_cliente(envio)[-1]


@pytest.mark.parametrize("plaga", ["cucaracha_alemana", "chinches", "pulgas"])
@respx.mock
async def test_cancelacion_pregunta_primero_y_cancela_al_confirmar(plaga):
    rt, ctx = await _confirmada(plaga)
    envio = _crm_con_dueno()

    rt._mensajes_lead = ["quiero cancelar mi visita"]
    await rt.execute("cambiar_visita", {"accion": "cancelar"})
    assert "reagendamos" in rt.texto_garantizado and ctx.calendar.cancel_calls == []

    rt._mensajes_lead = ["ya no la necesito"]
    rt.texto_garantizado = None
    await rt.execute(
        "cambiar_visita", {"accion": "cancelar", "confirmado": True, "motivo": "ya no la necesita"}
    )

    assert ctx.calendar.cancel_calls == ["evt_1"]
    assert (await ctx.store.get_active_calendar_booking(rt._conv.id)) is None
    assert "quedó cancelada" in rt.texto_garantizado
    assert "canceló su visita" in envio.calls.last.request.content.decode()


@respx.mock
async def test_cancelacion_si_dice_que_lo_verifica_no_se_cancela():
    rt, ctx = await _confirmada("cucaracha_alemana")
    _crm_con_dueno()
    rt._mensajes_lead = ["déjame verificar mi agenda"]
    rt.caso.cancelacion_preguntada = True
    res = await rt.execute("cambiar_visita", {"accion": "cancelar"})  # sin confirmado
    assert res["error"] == "falta_confirmacion" and ctx.calendar.cancel_calls == []


def test_cucarachas_sin_pistas_presenta_las_dos_especies():
    from app.plagas import catalogo, diagnostico

    d = diagnostico.evaluar("cucaracha", [], mensajes_lead=["tengo cucarachas"])
    assert d.pregunta == catalogo.INTRO_CUCARACHAS
    assert "alemana" in d.pregunta and "americana" in d.pregunta and "1️⃣" in d.pregunta


def test_cucarachas_con_una_pista_solo_pregunta_el_tamano():
    from app.plagas import catalogo, diagnostico

    d = diagnostico.evaluar("cucaracha", [], mensajes_lead=["tengo cucarachas en mi cocina"])
    assert d.pregunta == catalogo.PREGUNTA_CUCARACHA_TAMANO


def test_alemana_explica_que_se_rompe_el_ciclo_reproductivo():
    from app.plagas.herramientas import bloque_de_tratamiento

    texto = bloque_de_tratamiento("cucaracha_alemana")
    assert "ciclo reproductivo" in texto and "recién nacidos" in texto and "edad reproductiva" in texto
