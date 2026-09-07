"""Turno completo: handoff después de la despedida; LLM agotado → silencio + handoff error."""
from __future__ import annotations

import asyncio
import json

from app.llm import LlmExhausted, LlmReply, ToolCall
from app.state import utcnow
from app.turn import VERIFICAR_COBERTURA_CHOICE
from tests.conftest import IDENTITY, FakeLLM, mock_crm_basics, wa_body


async def test_handoff_despedida_primero_pausa_despues(ctx, client, respx_mock):
    routes = mock_crm_basics(respx_mock)
    ctx.llm.replies = [
        LlmReply(
            content=None,
            tool_calls=[ToolCall(id="tc1", name="handoff", arguments={"reason": "pidió humano"})],
        ),
        LlmReply(content="Va — te paso con el equipo ahora mismo, sin que repitas nada."),
    ]
    await client.post("/webhook", content=wa_body(text="quiero hablar con una persona"))
    await asyncio.sleep(0.25)

    assert routes["messages"].call_count == 1
    assert routes["handoff"].call_count == 1
    # ORDEN CRÍTICO: primero la despedida, luego el handoff (si no, 409 ai_paused)
    llamadas = [
        str(c.request.url.path) for c in respx_mock.calls if "/api/bot/" in str(c.request.url)
    ]
    assert llamadas.index("/api/bot/messages") < llamadas.index("/api/bot/handoff")
    body = json.loads(routes["handoff"].calls[0].request.content)
    # El texto libre del LLM se normaliza al catálogo del CRM (002): un
    # reason fuera de catálogo era 422 y el handoff se perdía en producción.
    assert body["reason"] == "cliente"


async def test_llm_agotado_silencio_mas_handoff_error(ctx, client, respx_mock):
    routes = mock_crm_basics(respx_mock)
    ctx.llm.raise_exc = LlmExhausted("proveedor caído")

    resp = await client.post("/webhook", content=wa_body(text="hola"))
    assert resp.status_code == 200  # el webhook JAMÁS falla por el LLM
    await asyncio.sleep(0.25)

    assert routes["messages"].call_count == 0  # nada roto al lead
    assert routes["handoff"].call_count == 1
    body = json.loads(routes["handoff"].calls[0].request.content)
    assert body["reason"] == "error"
    # el relay a la bandeja quedó intacto
    assert len(ctx.store.relays) == 1


async def test_turno_programa_seguimiento(ctx, client, respx_mock):
    mock_crm_basics(respx_mock)
    await client.post("/webhook", content=wa_body(text="hola"))
    await asyncio.sleep(0.2)
    conv = next(iter(ctx.store.conversations.values()))
    assert conv.greeted is True
    assert conv.followup_due_at is not None  # empujón agendado a FOLLOWUP_HOURS


async def test_turno_con_route_out_cierra_sin_seguimiento(ctx, client, respx_mock):
    routes = mock_crm_basics(respx_mock)
    ctx.llm.replies = [
        LlmReply(content=None, tool_calls=[ToolCall(id="t1", name="route_out", arguments={})]),
        LlmReply(content="Por ahora no somos el mejor fit — te dejo unos recursos para arrancar por tu cuenta."),
    ]
    await client.post("/webhook", content=wa_body(text="soy estudiante"))
    await asyncio.sleep(0.25)
    assert routes["messages"].call_count == 1
    ficha = json.loads(routes["ficha"].calls[0].request.content)
    assert ficha["ficha"]["resultado"] == "dio_diy"
    conv = next(iter(ctx.store.conversations.values()))
    assert conv.phase == "cerrada"
    assert conv.followup_due_at is None


async def test_cancel_session_cierra_sin_handoff_ni_seguimiento(ctx, client, respx_mock):
    """Cancelar deja la conversación cerrada (como book/route_out) pero SIN
    pasar por handoff.reason — antes esto pausaba la IA innecesariamente."""
    routes = mock_crm_basics(respx_mock)
    conv = await ctx.store.get_or_create_conversation(IDENTITY)
    await ctx.store.save_calendar_booking(
        conv.id, "evt_1", "alemana", utcnow(), utcnow()
    )
    ctx.llm.replies = [
        LlmReply(
            content=None,
            tool_calls=[ToolCall(id="tc1", name="cancel_session", arguments={})],
        ),
        LlmReply(content="Listo, tu cita quedó cancelada. Cualquier cosa aquí estoy."),
    ]
    await client.post(
        "/webhook", content=wa_body(text="quiero cancelar mi cita, no estaré")
    )
    await asyncio.sleep(0.25)

    assert routes["messages"].call_count == 1
    assert routes["handoff"].call_count == 0  # NO es handoff
    assert ctx.calendar.cancel_calls == ["evt_1"]
    conv_after = next(iter(ctx.store.conversations.values()))
    assert conv_after.phase == "cerrada"
    assert conv_after.followup_due_at is None


async def test_los_turnos_de_una_conversacion_no_se_encinan(ctx, client, respx_mock):
    """Un mensaje que llega tarde NO abre un turno con el contexto de antes.

    Dos mensajes con segundos de diferencia: el segundo abría su propio turno
    mientras el primero seguía corriendo, así que la cita se reservaba sin
    haber leído el mensaje que la corregía y salían dos respuestas encimadas.
    """
    routes = mock_crm_basics(respx_mock)

    class LlmLento(FakeLLM):
        async def complete(self, messages, tools=None, tool_choice=None):
            await asyncio.sleep(0.3)
            return await super().complete(messages, tools, tool_choice)

    ctx.llm = LlmLento()

    await client.post("/webhook", content=wa_body(text="Si 10.30", wamid="wamid.a"))
    await asyncio.sleep(0.15)  # el turno A ya arrancó y sigue en el LLM
    await client.post("/webhook", content=wa_body(text="De mañana", wamid="wamid.b"))
    await asyncio.sleep(1.2)

    assert routes["messages"].call_count == 2  # una respuesta por turno...
    rutas = [
        str(c.request.url.path)
        for c in respx_mock.calls
        if str(c.request.url.path) in ("/api/bot/context", "/api/bot/messages")
    ]
    # ...y el turno B lee el contexto DESPUÉS de que A mandó la suya: si no,
    # decide sobre un estado que ya cambió.
    assert rutas.count("/api/bot/context") == 2
    assert rutas.index("/api/bot/messages") < rutas.index(
        "/api/bot/context", rutas.index("/api/bot/context") + 1
    )


async def test_forzar_verificar_cobertura_si_lead_menciona_colonia(ctx, client, respx_mock):
    """Regresión (2026-09-06): con tool_choice="auto" el LLM respondió "está
    en zona de cobertura" tres veces seguidas SIN llamar verificar_cobertura
    ni una sola vez, aunque la tool estaba disponible y el chasis la exigía
    en prosa. La ronda 0 del turno debe forzarla cuando el lead menciona su
    colonia/ubicación -- no basta con confiar en que el modelo la use solo."""
    mock_crm_basics(respx_mock)
    ctx.llm.replies = [
        LlmReply(
            content=None,
            tool_calls=[
                ToolCall(
                    id="tc1",
                    name="verificar_cobertura",
                    arguments={
                        "colonia": "Buenos Aires",
                        "alcaldia_municipio": "",
                        "codigo_postal": "",
                    },
                )
            ],
        ),
        LlmReply(content="¿Me compartes tu código postal para confirmar cobertura?"),
    ]
    await client.post("/webhook", content=wa_body(text="Vivo en la Colonia Buenos Aires"))
    await asyncio.sleep(0.25)

    assert ctx.llm.calls[0]["tool_choice"] == VERIFICAR_COBERTURA_CHOICE
    # ronda 1 (tras ejecutar la tool) vuelve a "auto": no atora el resto del turno
    assert ctx.llm.calls[1]["tool_choice"] is None


async def test_no_forzar_verificar_cobertura_sin_mencion_de_ubicacion(ctx, client, respx_mock):
    routes = mock_crm_basics(respx_mock)
    ctx.llm.replies = [LlmReply(content="¡Hola! ¿Qué plaga tienes?")]
    await client.post("/webhook", content=wa_body(text="Hola, buenas tardes"))
    await asyncio.sleep(0.25)

    assert routes["messages"].call_count == 1
    assert ctx.llm.calls[0]["tool_choice"] is None
