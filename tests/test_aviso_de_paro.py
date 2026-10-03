"""Cuando Nea se detiene con un cliente, el cliente no espera en silencio y el
dueño se entera por su WhatsApp. Y una imagen que el modelo no puede ver no
corta la conversación."""
from __future__ import annotations

import json

import httpx
import pytest

from app.llm import LlmExhausted, LlmReply
from app.state import InboundMessage
from app.turn import run_turn
from tests.conftest import (
    CRM_CONV_ID, CRM_URL, IDENTITY, crm_context, make_ctx, make_settings, mock_crm_basics,
)

DUENO = "525529161746"
CONV_DUENO = "conv-dueno"


def _ctx(**ajustes):
    return make_ctx(make_settings(aviso_dueno_wa=DUENO, **ajustes))


def _contexto_segun_telefono(respx_mock, *, lead_ai: bool = True):
    """El CRM contesta distinto para el cliente y para el dueño."""
    def _responder(request: httpx.Request) -> httpx.Response:
        quien = request.url.params.get("waIdentity", "")
        if quien.endswith(DUENO[-10:]):
            return httpx.Response(200, json=crm_context(conv_id=CONV_DUENO))
        return httpx.Response(200, json=crm_context(ai_enabled=lead_ai))
    return respx_mock.get(f"{CRM_URL}/api/bot/context").mock(side_effect=_responder)


def _mensajes_a(rutas, conv: str) -> list[str]:
    return [
        json.loads(c.request.content).get("text") or json.loads(c.request.content).get("content", "")
        for c in rutas["messages"].calls
        if conv in c.request.content.decode()
    ]


def _entrada(texto: str = "hola", tipo: str = "text", **extra) -> InboundMessage:
    return InboundMessage(wa_message_id=f"w-{texto[:5]}", identity=IDENTITY, type=tipo, text=texto, **extra)


async def test_si_el_modelo_se_cae_el_cliente_recibe_aviso_y_el_dueno_se_entera(respx_mock):
    rutas = mock_crm_basics(respx_mock)
    _contexto_segun_telefono(respx_mock)
    ctx = _ctx()
    ctx.llm.raise_exc = LlmExhausted("proveedor caído")

    await run_turn(ctx, IDENTITY, [_entrada("¿es tóxico?")])

    al_cliente = _mensajes_a(rutas, CRM_CONV_ID)
    al_dueno = _mensajes_a(rutas, CONV_DUENO)
    assert len(al_cliente) == 1 and "problema para responderte" in al_cliente[0]
    assert len(al_dueno) == 1
    assert "Nea se detuvo" in al_dueno[0] and "no respondió" in al_dueno[0]
    assert "¿es tóxico?" in al_dueno[0]
    assert json.loads(rutas["handoff"].calls[0].request.content)["reason"] == "error"


async def test_el_cliente_que_escribe_con_la_ia_apagada_avisa_al_dueno_una_sola_vez(respx_mock):
    rutas = mock_crm_basics(respx_mock)
    _contexto_segun_telefono(respx_mock, lead_ai=False)
    ctx = _ctx()

    await run_turn(ctx, IDENTITY, [_entrada("¿es tóxico, tengo que mover algo?")])
    await run_turn(ctx, IDENTITY, [_entrada("Alguna respuesta")])

    al_dueno = _mensajes_a(rutas, CONV_DUENO)
    assert len(al_dueno) == 1  # el segundo mensaje no repite el aviso
    assert "IA de esta conversación está apagada" in al_dueno[0]
    assert "tengo que mover algo" in al_dueno[0]
    assert _mensajes_a(rutas, CRM_CONV_ID) == []  # al cliente no se le escribe


async def test_sin_numero_del_dueno_no_hay_aviso_ni_error(respx_mock):
    rutas = mock_crm_basics(respx_mock, ai_enabled=False)
    ctx = make_ctx(make_settings())  # sin AVISO_DUENO_WA ni OWNER_WA_ID
    await run_turn(ctx, IDENTITY, [_entrada("hola")])
    assert rutas["messages"].call_count == 0


async def test_una_imagen_que_el_modelo_no_puede_ver_no_corta_la_conversacion(respx_mock):
    rutas = mock_crm_basics(respx_mock)
    _contexto_segun_telefono(respx_mock)
    ctx = _ctx()
    llamadas = {"n": 0}
    original = ctx.llm.complete

    async def _complete(messages, tools=None, tool_choice=None):
        llamadas["n"] += 1
        ultimo = messages[-1]["content"]
        con_imagen = isinstance(ultimo, list)
        if con_imagen:
            raise LlmExhausted("el modelo no acepta imágenes")
        return LlmReply(content="No pude ver tu foto 🙏 ¿Me describes lo que querías mostrarme?")

    ctx.llm.complete = _complete  # type: ignore[method-assign]

    await run_turn(
        ctx, IDENTITY,
        [InboundMessage(wa_message_id="w-img", identity=IDENTITY, type="image",
                        media_id="m1", media_mime="image/jpeg")],
    )

    al_cliente = _mensajes_a(rutas, CRM_CONV_ID)
    assert al_cliente and "describes" in al_cliente[0]
    assert rutas["handoff"].call_count == 0  # no se apagó la IA
    assert _mensajes_a(rutas, CONV_DUENO) == []  # y al dueño no se le molesta
