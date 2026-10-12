"""API de Nea para Vocero: listar y resolver citas por aprobar (panel y chat de Vocero)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from app.main import create_app
from tests.conftest import CRM_CONV_ID, CRM_URL, IDENTITY, FakeCalendar, make_ctx, make_settings

INICIO = datetime(2026, 10, 8, 16, 0, tzinfo=timezone.utc)
SECRETO = {"x-vocero-secret": "s3creto-de-prueba"}


async def _entorno(secreto: str = "s3creto-de-prueba"):
    ctx = make_ctx(
        make_settings(vertical="plagas", owner_wa_id="525529161746", vocero_api_secret=secreto),
        calendar=FakeCalendar(),
    )
    conv = await ctx.store.get_or_create_conversation(IDENTITY)
    pend = await ctx.store.create_pending_booking(
        conv.id, CRM_CONV_ID, "chinches", INICIO, INICIO + timedelta(minutes=150),
        "el jueves 8 de octubre, 10:00", "Av. Cuauhtémoc 302, Narvarte", "jueves", INICIO,
    )
    app = create_app(ctx=ctx)
    cliente = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://nea.test")
    return ctx, pend, cliente


def _crm():
    respx.put(f"{CRM_URL}/api/bot/ficha").mock(return_value=httpx.Response(200, json={}))
    return respx.post(f"{CRM_URL}/api/bot/messages").mock(return_value=httpx.Response(200, json={}))


async def test_sin_secreto_configurado_responde_503():
    ctx, pend, c = await _entorno(secreto="")
    async with c:
        r = await c.get("/vocero/citas-pendientes", headers=SECRETO)
    assert r.status_code == 503


async def test_secreto_equivocado_responde_401():
    ctx, pend, c = await _entorno()
    async with c:
        r = await c.get("/vocero/citas-pendientes", headers={"x-vocero-secret": "otro"})
        r2 = await c.post(f"/vocero/citas/{pend.id}/resolver", json={"accion": "aprobar"})
    assert r.status_code == 401 and r2.status_code == 401
    assert ctx.calendar.booking_calls == []


async def test_lista_las_citas_abiertas_de_una_conversacion():
    ctx, pend, c = await _entorno()
    async with c:
        r = await c.get("/vocero/citas-pendientes", params={"conversationId": CRM_CONV_ID}, headers=SECRETO)
        otra = await c.get("/vocero/citas-pendientes", params={"conversationId": "otra"}, headers=SECRETO)
    cita = r.json()["citas"][0]
    assert cita["id"] == pend.id and cita["plaga"] == "chinches de cama" and cita["tipo"] == "nueva"
    assert cita["direccion"].startswith("Av. Cuauhtémoc") and cita["estado"] == "pendiente"
    assert otra.json() == {"citas": []}


@respx.mock
async def test_aprobar_crea_el_evento_y_nea_le_escribe_al_cliente():
    ctx, pend, c = await _entorno()
    envio = _crm()
    async with c:
        r = await c.post(f"/vocero/citas/{pend.id}/resolver", json={"accion": "aprobar"}, headers=SECRETO)
    assert r.status_code == 200 and r.json()["estado"] == "aprobado"
    assert ctx.calendar.booking_calls[0]["service_key"] == "chinches"
    texto = json.loads(envio.calls.last.request.content)["text"]
    assert "quedó agendada" in texto and "Por este medio te confirmamos la fecha y el horario" in texto
    for prohibido in ("Leopoldo", "dueño", "Ing."):
        assert prohibido not in texto


@respx.mock
async def test_una_cita_ya_resuelta_por_otra_via_responde_409_y_no_se_duplica():
    ctx, pend, c = await _entorno()
    _crm()
    async with c:
        await c.post(f"/vocero/citas/{pend.id}/resolver", json={"accion": "aprobar"}, headers=SECRETO)
        r = await c.post(f"/vocero/citas/{pend.id}/resolver", json={"accion": "aprobar"}, headers=SECRETO)
        lista = await c.get("/vocero/citas-pendientes", headers=SECRETO)
    assert r.status_code == 409 and r.json()["error"] == "ya_resuelta"
    assert len(ctx.calendar.booking_calls) == 1
    assert lista.json() == {"citas": []}


@respx.mock
async def test_rechazar_no_crea_evento():
    ctx, pend, c = await _entorno()
    envio = _crm()
    async with c:
        r = await c.post(f"/vocero/citas/{pend.id}/resolver", json={"accion": "rechazar"}, headers=SECRETO)
    assert r.json()["estado"] == "rechazado" and ctx.calendar.booking_calls == []
    assert "No tengo disponible ese horario" in json.loads(envio.calls.last.request.content)["text"]


@respx.mock
async def test_proponer_otra_hora_le_pregunta_al_cliente_y_queda_esperando():
    ctx, pend, c = await _entorno()
    envio = _crm()
    async with c:
        r = await c.post(f"/vocero/citas/{pend.id}/resolver",
                         json={"accion": "proponer", "texto": "pasado mañana 11 am"}, headers=SECRETO)
        lista = await c.get("/vocero/citas-pendientes", headers=SECRETO)
    assert r.json()["estado"] == "esperando_cliente" and ctx.calendar.booking_calls == []
    assert "¿Te queda bien" in json.loads(envio.calls.last.request.content)["text"]
    assert lista.json()["citas"][0]["estado"] == "esperando_cliente"  # sigue abierta para aprobarla directo


async def test_accion_invalida_y_cita_inexistente():
    ctx, pend, c = await _entorno()
    async with c:
        mala = await c.post(f"/vocero/citas/{pend.id}/resolver", json={"accion": "borrar"}, headers=SECRETO)
        falta = await c.post("/vocero/citas/9999/resolver", json={"accion": "aprobar"}, headers=SECRETO)
    assert mala.status_code == 400 and falta.status_code == 404
