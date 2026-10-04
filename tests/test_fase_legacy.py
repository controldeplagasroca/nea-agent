"""La base de producción trae un CHECK de fases de la Nea anterior que rechazaba
las fases de esta ('agendando' al cotizar, 'descubrimiento' en /reset). El turno
reventaba DESPUÉS de enviar, la red de seguridad apagaba la IA de esa
conversación y el expediente no se guardaba (3-4 oct 2026)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.llm import LlmReply, ToolCall
from app.state import InboundMessage
from app.turn import run_turn
from tests.conftest import IDENTITY, make_ctx, make_settings, mock_crm_basics

MIGRACION = Path(__file__).resolve().parent.parent / "migrations" / "012_fase_sin_check_legacy.sql"


def test_la_migracion_quita_el_check_que_dejo_la_nea_anterior():
    sql = MIGRACION.read_text(encoding="utf-8")
    assert "DROP CONSTRAINT IF EXISTS bot_conversation_phase_valida" in sql
    assert re.search(r"SET DEFAULT 'descubrimiento'", sql)
    # No vuelve a poner otro CHECK: las fases las controla el código.
    assert "ADD CONSTRAINT" not in sql


def test_las_fases_que_escribe_el_codigo_no_chocan_con_la_migracion():
    """Todas las fases que el código escribe quedan a salvo (sin CHECK) o son
    de las que la migración deja intactas."""
    escritas = set()
    for ruta in (Path(__file__).resolve().parent.parent / "app").rglob("*.py"):
        texto = ruta.read_text(encoding="utf-8")
        escritas |= set(re.findall(r'phase\s*=\s*"([a-z_]+)"', texto))
        escritas |= set(re.findall(r'\["phase"\]\s*=\s*"([a-z_]+)"', texto))
    assert {"descubrimiento", "agendando", "cerrada"} <= escritas
    assert escritas <= {"descubrimiento", "agendando", "cerrada", "insight", "salida"}


async def test_si_la_base_rechaza_la_fase_el_turno_no_apaga_la_ia_y_se_guarda_el_resto(respx_mock):
    rutas = mock_crm_basics(respx_mock)
    ctx = make_ctx(make_settings())
    original = ctx.store.update_conversation

    async def _rechaza_la_fase(conv_id, **cambios):
        if "phase" in cambios:
            raise RuntimeError('violates check constraint "bot_conversation_phase_valida"')
        return await original(conv_id, **cambios)

    ctx.store.update_conversation = _rechaza_la_fase  # type: ignore[method-assign]
    # El modelo pasa la conversación al dueño: eso intenta escribir phase='cerrada'.
    ctx.llm.replies = [
        LlmReply(content=None, tool_calls=[ToolCall(id="t1", name="handoff", arguments={"reason": "pidió humano"})]),
        LlmReply(content="Con gusto te comunico con el ingeniero."),
    ]

    await run_turn(
        ctx, IDENTITY,
        [InboundMessage(wa_message_id="w1", identity=IDENTITY, type="text", text="quiero hablar con una persona")],
    )

    conv = await ctx.store.get_or_create_conversation(IDENTITY)
    assert conv.greeted is True  # el resto de la actualización sí se guardó
    motivos = [json.loads(c.request.content)["reason"] for c in rutas["handoff"].calls]
    assert "error" not in motivos  # no hubo handoff de emergencia por la fase
