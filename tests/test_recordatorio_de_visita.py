"""Recordatorio al cliente 24 h antes, por plantilla de Meta (app/visit_reminders.py)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from app.horarios import zona_agente
from app.meta_wa import MetaError, MetaWhatsApp
from app.visit_reminders import VisitReminderWorker, momento_de_envio
from tests.conftest import CRM_URL, IDENTITY, crm_context, make_ctx, make_settings

TZ = zona_agente("America/Mexico_City")
META_URL = "https://graph.facebook.com/v21.0/104210872528753/messages"
# miércoles 7 oct 2026, 10:00 hora de México (UTC-6)
VISITA = datetime(2026, 10, 7, 16, 0, tzinfo=timezone.utc)
HACE_24H = VISITA - timedelta(hours=24)


def _ajustes(**extra):
    return make_settings(
        vertical="plagas",
        meta_wa_token="tok_de_prueba",
        meta_wa_phone_number_id="104210872528753",
        meta_wa_template_recordatorio="nea_recordatorio_visita",
        **extra,
    )


async def _armar(inicio=VISITA, agendada_hace=timedelta(days=3), **extra):
    ctx = make_ctx(_ajustes(**extra))
    ctx.meta = MetaWhatsApp(token="tok_de_prueba", phone_number_id="104210872528753")
    conv = await ctx.store.get_or_create_conversation(IDENTITY)
    conv.caso = {"direccion": {"calle": "Vértiz", "numero_exterior": "2200", "colonia": "Portales"}}
    cita = await ctx.store.save_calendar_booking(conv.id, "e1", "alemana", inicio, inicio + timedelta(minutes=90))
    cita.created_at = inicio - agendada_hace
    return ctx, cita


def _crm(respx_mock):
    respx_mock.get(f"{CRM_URL}/api/bot/context").mock(
        return_value=httpx.Response(200, json=crm_context())
    )


def test_momento_de_envio_respeta_la_ventana_de_10_a_20():
    assert momento_de_envio(VISITA, TZ) == HACE_24H  # 10:00 → 10:00 del día anterior
    temprano = datetime(2026, 10, 7, 15, 0, tzinfo=timezone.utc)  # visita 9:00 local
    assert momento_de_envio(temprano, TZ) == datetime(2026, 10, 6, 16, 0, tzinfo=timezone.utc)  # 10:00 local
    tarde = datetime(2026, 10, 8, 3, 0, tzinfo=timezone.utc)  # visita 21:00 local → 21:00 del día anterior
    assert momento_de_envio(tarde, TZ).astimezone(TZ).hour == 10


@respx.mock
async def test_manda_la_plantilla_con_los_datos_de_la_visita_una_sola_vez():
    ctx, cita = await _armar()
    _crm(respx)
    meta = respx.post(META_URL).mock(return_value=httpx.Response(200, json={"messages": [{"id": "wamid.1"}]}))
    worker = VisitReminderWorker(ctx)

    assert await worker.tick(HACE_24H) == 1
    cuerpo = json.loads(meta.calls.last.request.content)
    assert meta.calls.last.request.headers["authorization"] == "Bearer tok_de_prueba"
    assert cuerpo["to"] == IDENTITY and cuerpo["template"]["name"] == "nea_recordatorio_visita"
    assert cuerpo["template"]["language"]["code"] == "es_MX"
    textos = [p["text"] for p in cuerpo["template"]["components"][0]["parameters"]]
    assert textos[0] == "Lead"  # primer nombre del contacto
    assert textos[1] == "cucaracha alemana"
    assert textos[2] == "mañana miércoles 7 de octubre, 10:00"
    assert "Vértiz 2200" in textos[3] and "Portales" in textos[3]
    assert cita.recordatorio_enviado_at is not None

    assert await worker.tick(HACE_24H + timedelta(minutes=5)) == 0  # no se repite
    assert meta.call_count == 1


@respx.mock
async def test_no_manda_antes_de_tiempo_ni_fuera_de_ventana():
    ctx, _ = await _armar()
    _crm(respx)
    meta = respx.post(META_URL).mock(return_value=httpx.Response(200, json={"messages": [{"id": "x"}]}))
    worker = VisitReminderWorker(ctx)
    assert await worker.tick(HACE_24H - timedelta(minutes=10)) == 0  # faltan más de 24 h
    # visita de 9:00 → toca a las 10:00 locales, no a las 9:00
    ctx2, _ = await _armar(inicio=datetime(2026, 10, 7, 15, 0, tzinfo=timezone.utc))
    assert await VisitReminderWorker(ctx2).tick(datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)) == 0
    assert await VisitReminderWorker(ctx2).tick(datetime(2026, 10, 6, 16, 0, tzinfo=timezone.utc)) == 1
    # de noche (21:00 local) nunca
    ctx3, _ = await _armar()
    assert await VisitReminderWorker(ctx3).tick(datetime(2026, 10, 7, 3, 0, tzinfo=timezone.utc)) == 0
    assert meta.call_count == 1


@respx.mock
async def test_cita_agendada_con_menos_de_24h_no_lleva_recordatorio():
    ctx, cita = await _armar(agendada_hace=timedelta(hours=20))
    _crm(respx)
    meta = respx.post(META_URL).mock(return_value=httpx.Response(200, json={"messages": [{"id": "x"}]}))
    assert await VisitReminderWorker(ctx).tick(HACE_24H + timedelta(hours=1)) == 0
    assert meta.call_count == 0


@respx.mock
async def test_si_meta_falla_no_se_marca_y_se_reintenta():
    ctx, cita = await _armar()
    _crm(respx)
    meta = respx.post(META_URL).mock(
        return_value=httpx.Response(400, json={"error": {"code": 132001, "message": "template not found"}})
    )
    worker = VisitReminderWorker(ctx)
    assert await worker.tick(HACE_24H) == 0 and cita.recordatorio_enviado_at is None
    meta.mock(return_value=httpx.Response(200, json={"messages": [{"id": "ok"}]}))
    assert await worker.tick(HACE_24H + timedelta(minutes=5)) == 1


@respx.mock
async def test_respeta_la_lista_de_permitidos():
    ctx, _ = await _armar(allowed_wa_ids="525500000099")
    _crm(respx)
    meta = respx.post(META_URL).mock(return_value=httpx.Response(200, json={"messages": [{"id": "x"}]}))
    assert await VisitReminderWorker(ctx).tick(HACE_24H) == 0
    assert meta.call_count == 0


async def test_reagendar_renueva_el_recordatorio():
    ctx, cita = await _armar()
    await ctx.store.mark_visit_reminder_sent(cita.id)
    await ctx.store.update_calendar_booking_time(cita.conversation_id, VISITA + timedelta(days=1), VISITA + timedelta(days=1, hours=1))
    assert cita.recordatorio_enviado_at is None


@respx.mock
async def test_meta_error_trae_codigo_sin_token():
    meta = MetaWhatsApp(token="secreto123", phone_number_id="104210872528753")
    respx.post(META_URL).mock(return_value=httpx.Response(401, json={"error": {"code": 190, "message": "token expirado"}}))
    with pytest.raises(MetaError) as exc:
        await meta.enviar_plantilla("525500000001", "x", ["a"])
    assert "190" in str(exc.value) and "secreto123" not in str(exc.value)


def test_se_enciende_solo_con_las_tres_variables():
    assert _ajustes().recordatorios_activos is True
    assert make_settings(vertical="plagas").recordatorios_activos is False
