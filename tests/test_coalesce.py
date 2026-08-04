"""Coalescencia: ráfaga de 3 mensajes → UN turno; referral personaliza el saludo."""
from __future__ import annotations

import asyncio
import json

from app.coalesce import Coalescer
from tests.conftest import mock_crm_basics, wa_body


async def test_coalescer_unitario_reinicia_timer():
    flushes: list[tuple[str, list[int]]] = []

    async def on_flush(identity: str, items: list[int]) -> None:
        flushes.append((identity, items))

    c = Coalescer(0.05, on_flush)
    c.add("id1", 1)
    await asyncio.sleep(0.02)
    c.add("id1", 2)  # reinicia el timer
    await asyncio.sleep(0.02)
    c.add("id1", 3)
    assert flushes == []  # todavía no vence
    await asyncio.sleep(0.1)
    assert flushes == [("id1", [1, 2, 3])]
    await c.aclose()


async def test_rafaga_de_3_una_sola_respuesta(ctx, client, respx_mock):
    routes = mock_crm_basics(respx_mock)
    for i, texto in enumerate(["hola", "tengo una clínica", "somos 12"]):
        await client.post(
            "/webhook", content=wa_body(text=texto, wamid=f"wamid.burst{i}")
        )
        await asyncio.sleep(0.01)
    await asyncio.sleep(0.25)

    # UN solo turno LLM y UNA sola respuesta al lead (AC-6)
    assert len(ctx.llm.calls) == 1
    assert routes["messages"].call_count == 1

    # los 3 textos llegaron juntos en el mensaje de usuario
    user_msgs = [
        m for m in ctx.llm.calls[0]["messages"] if m["role"] == "user"
    ]
    assert len(user_msgs) == 1
    for texto in ["hola", "tengo una clínica", "somos 12"]:
        assert texto in user_msgs[0]["content"]


async def test_referral_personaliza_el_saludo(ctx, client, respx_mock):
    mock_crm_basics(respx_mock)
    headline = "No contrates otro empleado para el WhatsApp"
    await client.post(
        "/webhook",
        content=wa_body(text="hola vi tu anuncio", referral_headline=headline),
    )
    await asyncio.sleep(0.2)
    assert len(ctx.llm.calls) == 1
    system = ctx.llm.calls[0]["messages"][0]
    assert system["role"] == "system"
    assert headline in system["content"]
    assert "PRIMER contacto" in system["content"]


async def test_respuesta_se_envia_y_registra(ctx, client, respx_mock):
    routes = mock_crm_basics(respx_mock)
    await client.post("/webhook", content=wa_body(text="hola"))
    await asyncio.sleep(0.2)
    sent = json.loads(routes["messages"].calls[0].request.content)
    assert sent["conversationId"] == "cv_test1"
    assert sent["text"]  # el texto del FakeLLM
    roles = [m.role for m in ctx.store.messages]
    assert roles == ["user", "assistant"]
