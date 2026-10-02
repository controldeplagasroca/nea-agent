"""Corre un escenario contra la Nea de verdad, con un modelo de verdad.

Lo único simulado es lo de afuera: el CRM (en memoria) y el lead (el mismo
modelo haciendo de cliente). Por dentro corre `app.turn.run_turn` tal cual
corre en producción: mismo prompt, mismas herramientas, mismos candados.
"""
from __future__ import annotations

import asyncio
import time
import traceback
from typing import Any

from app.config import Settings
from app.llm import LlmReply, OpenAiLlm
from app.plagas.candados import montos
from app.plagas.caso import Caso, paso_actual
from app.profile import ProfileProvider
from app.state import AppContext, InboundMessage, MemoryStore
from app.turn import run_turn
from selftest.roca.crm_falso import HORAS_DEL_DIA, HORAS_REPARTO, CrmFalso
from selftest.roca.escenarios import Escenario

# El WhatsApp «del dueño» en la autoprueba: a ese número debe llegarle un aviso
# cada vez que Nea le pasa una conversación (app/plagas/aviso.py).
DUENO = "5215500000001"

PERSONA = """Eres una persona real en México escribiéndole por WhatsApp a un negocio de control de plagas. NO eres un asistente ni un bot: eres el cliente.

TU SITUACIÓN (son tus hechos; no los contradigas):
{persona}

CÓMO ESCRIBES:
- Como la gente en WhatsApp: corto, informal, a veces sin acentos ni signos de apertura. Máximo 25 palabras por mensaje.
- Contestas SOLO lo que te preguntan. No sueltas todos tus datos de golpe.
- Si te preguntan algo que no está en tu situación, contestas algo creíble y sencillo, coherente con lo demás.
- No repites lo que ya dijiste salvo que te lo vuelvan a preguntar.
- Nunca escribes como vendedor ni haces el trabajo del negocio.

CUÁNDO TERMINAS:
Cuando ya conseguiste lo que buscabas, o te dicen que te comunican con una persona, o que no hay servicio en tu zona, o ya no tienes nada más que decir, respondes EXACTAMENTE: [FIN]

Responde únicamente con tu siguiente mensaje de WhatsApp (o [FIN])."""


class LlmEspia(OpenAiLlm):
    """El modelo de siempre, anotando qué herramientas pidió en cada turno."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.bitacora: list[dict[str, Any]] = []

    async def complete(self, messages: Any, tools: Any = None, tool_choice: Any = None) -> LlmReply:
        reply = await super().complete(messages, tools=tools, tool_choice=tool_choice)
        for tc in reply.tool_calls:
            self.bitacora.append({"herramienta": tc.name, "args": tc.arguments})
        return reply


def _llm(cfg: dict[str, Any], espia: bool = False) -> OpenAiLlm:
    clase = LlmEspia if espia else OpenAiLlm
    return clase(
        cfg["llm_api_key"],
        cfg["llm_model"],
        base_url=cfg.get("llm_base_url") or None,
        reasoning_effort="minimal",
        provider_sort="throughput",
        timeout=60.0,
    )


async def _mensaje_del_lead(llm: OpenAiLlm, persona: str, turnos: list[dict[str, Any]]) -> str:
    """El siguiente mensaje del cliente simulado (o [FIN])."""
    mensajes: list[dict[str, Any]] = [
        {"role": "system", "content": PERSONA.format(persona=persona)}
    ]
    for t in turnos:
        mensajes.append({"role": "assistant", "content": "\n".join(str(m) for m in t["lead"])})
        mensajes.append({"role": "user", "content": t.get("bot") or "(el negocio no contestó)"})
    reply = await llm.complete(mensajes)
    texto = (reply.content or "").strip().strip('"')
    return texto or "[FIN]"


def _entrantes(identidad: str, rafaga: list[Any], n: int) -> list[InboundMessage]:
    out: list[InboundMessage] = []
    for i, item in enumerate(rafaga):
        wamid = f"wamid.{identidad}.{n}.{i}"
        if isinstance(item, dict):
            out.append(InboundMessage(
                wa_message_id=wamid, identity=identidad,
                type=str(item.get("type") or "text"), text=item.get("text"),
                location=item.get("location"),
            ))
        else:
            out.append(InboundMessage(wa_message_id=wamid, identity=identidad, type="text", text=str(item)))
    return out


async def correr(
    esc: Escenario, *, modo: str, cfg: dict[str, Any], rep: int, perfil: dict[str, Any]
) -> dict[str, Any]:
    """Una conversación completa. `modo`: "vertical" (este fork) o "base" (Nea genérica + brief)."""
    identidad = f"52155{abs(hash((esc.id, rep, modo))) % 10**8:08d}"
    settings = Settings(
        _env_file=None,
        verify_token="autoprueba",
        crm_base_url="http://crm.falso",
        crm_bot_api_key="autoprueba",
        llm_api_key=cfg["llm_api_key"],
        llm_model=cfg["llm_model"],
        llm_base_url=cfg.get("llm_base_url") or "",
        history_window=24,
        stall_max_turns=24,
        database_url="",
        vertical="plagas" if modo == "vertical" else "",
        agenda_modo="aprobacion" if modo == "vertical" else "directa",
        aviso_dueno_wa=DUENO if modo == "vertical" else "",
    )
    crm = CrmFalso(
        identidad=identidad,
        perfil=perfil,
        nombre=str(esc.crm.get("nombre") or ""),
        etapa=str(esc.crm.get("etapa") or "Nuevo"),
        agenda=bool(esc.crm.get("agenda", True)),
        cita_previa=esc.crm.get("cita_previa"),
        dueno=settings.aviso_dueno_identity,
    )
    nea = _llm(cfg, espia=True)
    lead = _llm(cfg)
    store = MemoryStore()
    ctx = AppContext(
        settings=settings, store=store, crm=crm, llm=nea,
        profile=ProfileProvider(crm, default_name="Nea"),
    )
    ctx.agenda_enabled = crm.agenda
    candados_vistos: list[str] = []
    ctx.registro_de_candados = candados_vistos  # type: ignore[attr-defined]

    turnos: list[dict[str, Any]] = []
    guion_tras_precio = list(esc.tras_precio)
    precio = esc.espera.get("precio")
    for n in range(esc.max_turnos):
        ya_tiene_precio = bool(precio) and any(
            precio in montos(t.get("bot") or "") for t in turnos
        )
        if n < len(esc.apertura):
            rafaga = list(esc.apertura[n])
        elif guion_tras_precio and ya_tiene_precio:
            rafaga = [guion_tras_precio.pop(0)]
        elif esc.persona:
            try:
                texto = await _mensaje_del_lead(lead, esc.persona, turnos)
            except Exception as exc:  # el lead simulado falló: se corta aquí
                turnos.append({"lead": [], "bot": None, "error": f"lead simulado: {exc}"})
                break
            if "[FIN]" in texto.upper():
                break
            rafaga = [texto]
        else:
            break

        enviados_antes = len(crm.enviados)
        llamadas_antes = len(nea.bitacora)
        candados_antes = len(candados_vistos)
        inicio = time.monotonic()
        error = None
        try:
            await run_turn(ctx, identidad, _entrantes(identidad, rafaga, n))
        except Exception:
            error = traceback.format_exc(limit=4)
        conv = await store.get_or_create_conversation(identidad)
        caso = Caso.desde(conv.caso)
        nuevos = crm.enviados[enviados_antes:]
        turno: dict[str, Any] = {
            "lead": [m if isinstance(m, str) else f"[{m.get('type')}]" for m in rafaga],
            "bot": "\n\n".join(nuevos) if nuevos else None,
            "herramientas": nea.bitacora[llamadas_antes:],
            "candados": candados_vistos[candados_antes:],
            "paso": paso_actual(caso, agenda=crm.agenda).nombre if modo == "vertical" else conv.phase,
            "segundos": round(time.monotonic() - inicio, 1),
        }
        if error:
            turno["error"] = error
        turnos.append(turno)
        if error or not crm.ai_enabled or not nuevos:
            break  # reventó, pasó a humano, o Nea calló

    conv = await store.get_or_create_conversation(identidad)
    horas = {f"{h:%H:%M}" for h in (*HORAS_DEL_DIA, *HORAS_REPARTO)} if crm.agenda else set()
    return {
        "id": esc.id,
        "titulo": esc.titulo,
        "rep": rep,
        "modo": modo,
        "turnos": turnos,
        "caso": conv.caso,
        "ficha": crm.ficha,
        "handoffs": crm.handoffs,
        "avisos": crm.avisos,
        "reservas": crm.reservas,
        "horas_ofrecidas": sorted(horas),
        "uso": {"nea": nea.usage, "lead": lead.usage},
    }


async def correr_todos(
    escenarios: list[Escenario], *, modo: str, cfg: dict[str, Any], reps: int,
    paralelo: int, perfil: dict[str, Any], avisar: Any = None,
) -> list[dict[str, Any]]:
    semaforo = asyncio.Semaphore(paralelo)

    async def uno(esc: Escenario, rep: int) -> dict[str, Any]:
        async with semaforo:
            try:
                res = await correr(esc, modo=modo, cfg=cfg, rep=rep, perfil=perfil)
            except Exception:
                res = {
                    "id": esc.id, "titulo": esc.titulo, "rep": rep, "modo": modo,
                    "turnos": [{"lead": [], "bot": None, "error": traceback.format_exc(limit=4)}],
                    "caso": {}, "ficha": {}, "handoffs": [], "reservas": [],
                    "horas_ofrecidas": [], "uso": {},
                }
            if avisar:
                avisar(res)
            return res

    return await asyncio.gather(*(uno(e, r) for e in escenarios for r in range(1, reps + 1)))
