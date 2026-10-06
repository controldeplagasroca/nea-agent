"""Reagendar y cancelar una visita ya registrada (caso de Ethel, 4 oct): el cliente pidió
mover su cita y la conversación se quedó sin respuesta y sin aviso al técnico."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import respx

from app.approvals import resolver_aprobacion
from app.plagas.aviso import avisar_al_dueno
from app.plagas.caso import Caso, paso_actual
from app.state import utcnow
from tests.conftest import CRM_URL, IDENTITY
from tests.test_confirmacion_inmediata import INICIO, _crm_falso, _rt


def _dia_libre(hora_utc: int = 16):
    """El próximo miércoles a las 10:00 CDMX (16:00 UTC) y su payload de calendario."""
    hoy = datetime.now(timezone.utc).date()
    dias = (2 - hoy.weekday()) % 7 or 7
    inicio = datetime.combine(hoy + timedelta(days=dias), datetime.min.time(), timezone.utc).replace(hour=hora_utc)
    return inicio, {
        "startUtc": inicio.isoformat().replace("+00:00", "Z"),
        "endUtc": (inicio + timedelta(minutes=90)).isoformat().replace("+00:00", "Z"),
        "dayLabel": "el miércoles", "time": f"{(hora_utc - 6):02d}:00",
    }


async def _con_visita_confirmada(texto: str):
    rt, ctx = await _rt(inmediata=False)
    rt._mensajes_lead = [texto]
    rt._nombre_lead = "Ethel"
    rt.caso.cita = {"label": "martes 6 de octubre, 09:00", "estado": "confirmada", "folio": 1}
    await ctx.store.save_calendar_booking(rt._conv.id, "evt_1", "alemana", INICIO, INICIO + timedelta(minutes=90))
    return rt, ctx


@respx.mock
async def test_reagendar_con_horario_libre_pide_confirmacion_al_tecnico_y_no_apaga_la_ia():
    rt, ctx = await _con_visita_confirmada("podria reagendar? el miercoles a las 10 am")
    envio = _crm_falso()
    inicio, slot = _dia_libre()
    ctx.calendar.availability_queue.append([slot])

    res = await rt.execute("cambiar_visita", {"accion": "reagendar", "motivo": "cita médica"})

    assert res["estado"] == "cambio_registrado" and rt.handoff_reason is None
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]
    assert pend.kind == "reagendar" and pend.google_event_id == "evt_1" and pend.start_utc == inicio
    assert "cita médica" in pend.nota
    pedido = envio.calls.last.request.content.decode()
    assert "Reagendo" in pedido and f"sí {pend.id}" in pedido
    texto = rt.texto_garantizado
    assert "ese horario sí lo tenemos disponible" in texto and "falta confirmarlo" not in texto.replace("Solo falta", "")
    assert "sigue en pie" in texto and "martes 6 de octubre" in texto
    assert rt.caso.cambio["folio"] == pend.id and rt.caso.cita["estado"] == "confirmada"
    assert paso_actual(rt.caso).nombre == "cambio_solicitado"
    assert ctx.calendar.reschedule_calls == []  # el calendario no se toca hasta que apruebe


@respx.mock
async def test_hora_ocupada_no_registra_nada_y_pide_ofrecer_las_libres():
    rt, ctx = await _con_visita_confirmada("el miercoles a las 10 am")
    _crm_falso()
    _, slot = _dia_libre(hora_utc=17)  # solo hay 11:00
    ctx.calendar.availability_queue.append([slot])
    res = await rt.execute("cambiar_visita", {"accion": "reagendar", "motivo": "imprevisto"})
    assert res["ok"] is True and "NO está libre" in res["instrucciones"] and "11:00" in res["instrucciones"]
    assert await ctx.store.list_pending_bookings_pendientes() == []
    assert rt.texto_garantizado is None and rt.caso.cambio is None


async def test_sin_dia_u_hora_pregunta():
    rt, ctx = await _con_visita_confirmada("quiero cambiarla")
    res = await rt.execute("cambiar_visita", {"accion": "reagendar", "motivo": "imprevisto"})
    assert res["error"] == "falta_dia_u_hora"


@respx.mock
async def test_al_aprobar_el_cambio_se_mueve_el_evento_y_el_cliente_recibe_reagendada():
    rt, ctx = await _con_visita_confirmada("el miercoles a las 10 am")
    envio = _crm_falso()
    inicio, slot = _dia_libre()
    ctx.calendar.availability_queue.append([slot])
    await rt.execute("cambiar_visita", {"accion": "reagendar", "motivo": "imprevisto"})
    await ctx.store.update_conversation(rt._conv.id, caso=rt.caso.a_dict())
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]

    await resolver_aprobacion(ctx, pend, True)

    assert ctx.calendar.reschedule_calls[0]["event_id"] == "evt_1"
    assert ctx.calendar.reschedule_calls[0]["new_start"] == inicio
    assert "reagendada" in json.loads(envio.calls.last.request.content)["text"]
    caso = Caso.desde((await ctx.store.get_conversation(rt._conv.id)).caso)
    assert caso.cambio is None and caso.cita["estado"] == "confirmada"
    assert caso.cita["start_utc"] == inicio.isoformat() and "6 de octubre" not in caso.cita["label"]


@respx.mock
async def test_si_el_tecnico_rechaza_el_cambio_la_visita_de_antes_sigue_en_pie():
    rt, ctx = await _con_visita_confirmada("el miercoles a las 10 am")
    envio = _crm_falso()
    _, slot = _dia_libre()
    ctx.calendar.availability_queue.append([slot])
    await rt.execute("cambiar_visita", {"accion": "reagendar", "motivo": "imprevisto"})
    await ctx.store.update_conversation(rt._conv.id, caso=rt.caso.a_dict())
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]

    await resolver_aprobacion(ctx, pend, False)

    assert "sigue en pie" in json.loads(envio.calls.last.request.content)["text"]
    caso = Caso.desde((await ctx.store.get_conversation(rt._conv.id)).caso)
    assert caso.cambio is None and caso.cita is not None and caso.cita["estado"] == "confirmada"
    assert (await ctx.store.get_active_calendar_booking(rt._conv.id)) is not None


@respx.mock
async def test_cancelar_primero_pregunta_el_motivo_y_ofrece_reagendar_sin_cancelar():
    rt, ctx = await _con_visita_confirmada("quiero cancelar mi cita")
    _crm_falso()
    res = await rt.execute("cambiar_visita", {"accion": "cancelar"})
    assert res["estado"] == "motivo_preguntado"
    assert "inconveniente" in rt.texto_garantizado and "reagendamos" in rt.texto_garantizado
    assert ctx.calendar.cancel_calls == [] and rt.caso.cita is not None


@respx.mock
async def test_cancelar_confirmado_borra_el_evento_y_avisa_al_tecnico():
    rt, ctx = await _con_visita_confirmada("si, mejor cancela, ya contrate a otra empresa")
    envio = _crm_falso()
    rt.caso.cancelacion_preguntada = True

    sin = await rt.execute("cambiar_visita", {"accion": "cancelar"})
    assert sin["error"] == "falta_confirmacion" and ctx.calendar.cancel_calls == []

    res = await rt.execute("cambiar_visita", {"accion": "cancelar", "confirmado": True, "motivo": "contrató a otra empresa"})
    assert res["estado"] == "cancelada" and ctx.calendar.cancel_calls == ["evt_1"]
    assert await ctx.store.get_active_calendar_booking(rt._conv.id) is None
    assert rt.caso.cita is None and "quedó cancelada" in rt.texto_garantizado
    aviso = envio.calls.last.request.content.decode()
    assert "canceló su visita" in aviso and "contrató a otra empresa" in aviso


@respx.mock
async def test_un_pase_con_visita_confirmada_si_avisa_al_dueno():
    """Antes se callaba porque la cita tenía folio: la solicitud ya estaba resuelta."""
    rt, ctx = await _con_visita_confirmada("hablar con alguien")
    envio = _crm_falso()
    ctx.settings.aviso_dueno_wa = "525529161746"
    enviado = await avisar_al_dueno(
        ctx, identidad_lead=IDENTITY, context=None, caso=rt.caso, motivo="cliente"
    )
    assert enviado is True and envio.call_count == 1


async def test_reagendar_una_visita_confirmada_sin_motivo_primero_lo_pregunta():
    rt, ctx = await _con_visita_confirmada("quiero cambiarla al miercoles a las 10 am")
    res = await rt.execute("cambiar_visita", {"accion": "reagendar"})
    assert res["error"] == "falta_motivo" and "motivo" in res["instrucciones"]
    assert await ctx.store.list_pending_bookings_pendientes() == []
