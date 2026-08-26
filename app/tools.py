"""Herramientas del LLM: update_ficha, propose_slots, book_session, route_out, handoff.

La validación es server-side: `book_session` SOLO acepta slots previamente
ofrecidos (tabla offered_slots, comparación por epoch exacto). Un fallo del
CRM dentro de una tool regresa `{"ok": false, ...}` al LLM — nunca tumba el
turno.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.crm import CrmError
from app.gcal import SERVICE_RULES, CalendarError, CalendarSlotTaken
from app.profile import BusinessProfile
from app.state import AppContext, Conversation, OfferedSlot

logger = logging.getLogger("nea.tools")

# Cuántos huecos quedan RESERVABLES tras un propose_slots. El agente muestra 3
# a la vez (regla del prompt), pero guardar solo 3 lo dejaba sin nada que
# ofrecer cuando el lead pedía otro día: el catálogo reservable es más ancho
# que el menú que se enseña.
MAX_OFFERED = 12
# Reparto pedido al CRM: hasta 3 huecos por día, en 5 días distintos.
OFFER_PER_DAY = 3
OFFER_DAYS = 5

# Palabras clave documentadas por el negocio para diferenciar especie de
# cucaracha (ver conocimiento del negocio en el CRM). Determinístico a
# propósito: no es al LLM a quien le toca decidir esto.
#
# Separadas en dos categorías (tamaño/color vs. ubicación) a propósito: un
# solo dato suelto (p.ej. "chiquita") NO basta para concluir la especie —
# se vio en vivo que el modelo declaraba "alemana" con una sola palabra de
# tamaño y CERO ubicación real. El candado exige una señal de CADA categoría
# apuntando a la misma especie antes de dar el veredicto por concluyente.
_ALEMANA_TAMANO_COLOR = ("chiquita", "chica", "pequena", "delgadita", "clara")
_ALEMANA_UBICACION = (
    "cocina", "estufa", "refri", "refrigerador", "microondas", "licuadora",
    "tostadora", "tarja", "alacena", "gabinete", "electrodomestico",
)
_AMERICANA_TAMANO_COLOR = (
    "grandota", "grande", "voladora", "patineta", "cucarachota", "fea",
    "rojiza", "oscura",
)
_AMERICANA_UBICACION = (
    "drenaje", "coladera", "alcantarilla", "patio", "exterior", "sotano",
    "estacionamiento", "registro", "tuberia",
)


def _sin_acentos(texto: str) -> str:
    reemplazos = str.maketrans("áéíóúñ", "aeioun")
    return texto.translate(reemplazos)


def _clasificar_cucaracha(tamano_color: str, ubicacion: str) -> dict[str, Any]:
    tc = _sin_acentos(tamano_color.lower())
    ub = _sin_acentos(ubicacion.lower())
    alemana_tc = any(kw in tc for kw in _ALEMANA_TAMANO_COLOR)
    alemana_ub = any(kw in ub for kw in _ALEMANA_UBICACION)
    americana_tc = any(kw in tc for kw in _AMERICANA_TAMANO_COLOR)
    americana_ub = any(kw in ub for kw in _AMERICANA_UBICACION)
    # Concluyente SOLO si tamaño/color Y ubicación apuntan a la MISMA especie
    # — una señal sola (aunque sea clara) no cierra el candado.
    alemana_completa = alemana_tc and alemana_ub and not (americana_tc or americana_ub)
    americana_completa = americana_tc and americana_ub and not (alemana_tc or alemana_ub)
    if alemana_completa:
        return {
            "ok": True,
            "especie": "alemana",
            "instrucciones": (
                "Especie identificada: cucaracha alemana (tamaño/color Y "
                "ubicación coinciden). Ya puedes explicar el tratamiento y, "
                "si el lead lo pide, cotizar — usa el conocimiento del "
                "negocio cargado para esta especie."
            ),
        }
    if americana_completa:
        return {
            "ok": True,
            "especie": "americana",
            "instrucciones": (
                "Especie identificada: cucaracha americana (tamaño/color Y "
                "ubicación coinciden). Ya puedes explicar el tratamiento y, "
                "si el lead lo pide, cotizar — usa el conocimiento del "
                "negocio cargado para esta especie."
            ),
        }
    tiene_alguna_senal = alemana_tc or alemana_ub or americana_tc or americana_ub
    if not tiene_alguna_senal:
        return {
            "ok": True,
            "especie": "no_concluyente",
            "instrucciones": (
                "No hay suficiente información para identificar la especie. "
                "Pregunta de nuevo, con más detalle, por el tamaño/color y "
                "por dónde exactamente la ha visto — no cotices ni agendes "
                "todavía, y no nombres ninguna especie todavía."
            ),
        }
    # Hay AL MENOS una señal pero no las dos categorías coinciden en la misma
    # especie (falta una categoría, o se contradicen entre sí).
    falta_ubicacion = (alemana_tc or americana_tc) and not (alemana_ub or americana_ub)
    if falta_ubicacion:
        pista = (
            "Tienes tamaño/color pero falta ubicación real. Pregunta "
            "EXACTAMENTE dónde la ha visto (p.ej. cocina/atrás del refri, o "
            "patio/coladera) — un dato de tamaño o color solo NUNCA basta "
            "para nombrar la especie. No cotices ni agendes todavía, y no "
            "nombres ninguna especie todavía."
        )
    else:
        pista = (
            "Los datos no distinguen con claridad entre las dos especies "
            "(se contradicen o falta tamaño/color). Pregunta UN detalle más "
            "y vuelve a llamar esta herramienta — no cotices ni agendes "
            "todavía, y no nombres ninguna especie todavía."
        )
    return {
        "ok": True,
        "especie": "ambigua" if not falta_ubicacion else "no_concluyente",
        "instrucciones": pista,
    }

# Palabras para mapear el texto libre del LLM a una clave de
# app.gcal.SERVICE_RULES — tolerante a como lo escriba ("cucaracha alemana",
# "hormigas", "araña"), igual que _clasificar_cucaracha arriba.
_SERVICIO_PALABRAS: dict[str, tuple[str, ...]] = {
    "alemana": ("alemana",),
    "americana": ("americana",),
    "chinches": ("chinche",),
    "hormiga": ("hormiga",),
    "pulgas": ("pulga",),
    "roedores": ("roedor", "rata", "raton"),
    "alacran_arana": ("alacran", "arana"),
}
# Termita (madera seca) es "bajo consulta" — nunca se agenda sola, siempre
# handoff. No vive en SERVICE_RULES/gcal a propósito.
_SERVICIO_BAJO_CONSULTA = ("termita",)


def _normalizar_servicio(texto: str) -> str | None:
    t = _sin_acentos(texto.lower())
    for key, palabras in _SERVICIO_PALABRAS.items():
        if any(p in t for p in palabras):
            return key
    return None


def _es_bajo_consulta(texto: str) -> bool:
    t = _sin_acentos(texto.lower())
    return any(p in t for p in _SERVICIO_BAJO_CONSULTA)


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "update_ficha",
            "description": (
                "Guarda o actualiza la ficha del lead en el CRM (merge: solo los "
                "campos que mandes). Llámala en cuanto descubras un dato nuevo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "rubro": {"type": "string"},
                    "rol": {
                        "type": "string",
                        "description": "dueno | hijo_del_dueno | empleado | otro",
                    },
                    "tamano_aprox": {"type": "string"},
                    "sistemas": {"type": "string"},
                    "dolor_principal": {"type": "string"},
                    "geo": {"type": "string"},
                    "calificado": {"type": "boolean"},
                    "resultado": {
                        "type": "string",
                        "description": "agendo | dio_diy | handoff | sin_respuesta",
                    },
                    "notas": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_slots",
            "description": (
                "Consulta la disponibilidad real de la agenda del negocio PARA "
                "LA PLAGA YA IDENTIFICADA (cada servicio dura distinto). Te "
                "regresa los huecos libres REPARTIDOS entre los próximos días, "
                "cada uno con su día en palabras (hoy/mañana/nombre del día). "
                "Ofrece al lead máximo 3, los que embonen con lo que pidió. Si "
                "el día que pidió no aparece, es que no hay agenda ese día: "
                "dilo. SOLO estos horarios serán reservables después. Termita "
                "NO se agenda aquí (bajo consulta) — usa handoff para esa."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "servicio": {
                        "type": "string",
                        "description": (
                            "La plaga ya identificada: alemana | americana | "
                            "chinches | hormiga | pulgas | roedores | "
                            "alacran_arana (alacrán o araña, mismo tratamiento "
                            "base)."
                        ),
                    }
                },
                "required": ["servicio"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_session",
            "description": (
                "Reserva la cita en uno de los horarios previamente ofrecidos. "
                "start_utc debe ser EXACTAMENTE el start_utc de un slot ofrecido "
                "en esta conversación. Llámala SOLO después de haber nombrado el "
                "día completo y de que el lead lo aceptara sin ambigüedad."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_utc": {
                        "type": "string",
                        "description": "ISO 8601 UTC del slot elegido, tal cual se ofreció",
                    },
                    "dia_confirmado": {
                        "type": "string",
                        "description": (
                            "Lo que el lead escribió para aceptar ESE día concreto. "
                            "Si no puedes citarlo, todavía no confirmó: pregunta "
                            "en vez de reservar."
                        ),
                    },
                },
                "required": ["start_utc", "dia_confirmado"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_session",
            "description": (
                "Mueve la cita YA agendada del lead a otro horario ofrecido. "
                "Mismo protocolo que book_session: primero propose_slots, luego "
                "confirmas el día completo, y hasta entonces mueves."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_utc": {
                        "type": "string",
                        "description": "ISO 8601 UTC del nuevo slot, tal cual se ofreció",
                    },
                    "dia_confirmado": {
                        "type": "string",
                        "description": "Lo que el lead escribió para aceptar ESE día",
                    },
                },
                "required": ["start_utc", "dia_confirmado"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "route_out",
            "description": (
                "Marca al lead como no calificado (hoy). Después despídete con "
                "honestidad, compartiendo los recursos alternativos del negocio "
                "si existen, puerta abierta."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "identificar_plaga",
            "description": (
                "Identifica la especie de cucaracha (alemana/cocina vs. "
                "americana/drenaje) a partir de tamaño-color y ubicación que "
                "describió el lead. Llámala en cuanto tengas AMBOS datos, "
                "SIEMPRE antes de cotizar o agendar cuando el lead reportó "
                "cucarachas sin decir cuál especie. Nunca le pidas al lead "
                "que adivine la especie él mismo — tú la identificas con lo "
                "que te describa."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tamano_color": {
                        "type": "string",
                        "description": (
                            "Lo que el lead dijo sobre tamaño y/o color "
                            "(p.ej. 'chiquita cafecita', 'grande rojiza oscura')"
                        ),
                    },
                    "ubicacion": {
                        "type": "string",
                        "description": (
                            "Dónde el lead ha visto la plaga (p.ej. 'cocina, "
                            "atrás del refri', 'coladera del patio')"
                        ),
                    },
                },
                "required": ["tamano_color", "ubicacion"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "handoff",
            "description": (
                "Pasa la conversación a un humano del negocio y pausa la IA. Tu "
                "mensaje de despedida se envía ANTES de la pausa — salvo en el "
                "handoff por hostilidad, donde cierras sobrio sin anunciarlo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Motivo breve (p.ej. 'pidió humano', 'duda fuera del conocimiento')",
                    }
                },
            },
        },
    },
]


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _label_of(raw: dict[str, Any], start: datetime) -> str:
    """Etiqueta con el día en palabras: "hoy viernes 7 de agosto, 10:30".

    La corta del CRM ("vie 7 ago, 10:30") se presta a que el lead entienda
    otro día: basta que conteste "10:30, de mañana" a una oferta de HOY para
    agendar mal. Si el CRM no manda `dayLabel` (respuestas sin reparto, p. ej.
    las alternativas de un slot_taken), se cae a la corta.
    """
    day_label = str(raw.get("dayLabel") or "").strip()
    time = str(raw.get("time") or "").strip()
    if day_label and time:
        return f"{day_label}, {time}"
    return str(raw.get("label") or _iso_z(start))


def _slots_from_payload(
    conversation_id: int, raw_slots: list[dict[str, Any]], service_key: str
) -> list[OfferedSlot]:
    """Convierte slots de la agenda ({startUtc,endUtc,label}) a OfferedSlot,
    tolerante. `service_key` es el servicio para el que se generaron —
    book_session lo reusa tal cual para armar el evento de Google Calendar."""
    out: list[OfferedSlot] = []
    for raw in raw_slots[:MAX_OFFERED]:
        start = _parse_utc(str(raw.get("startUtc") or ""))
        if start is None:
            continue
        end = _parse_utc(str(raw.get("endUtc") or "")) if raw.get("endUtc") else None
        out.append(
            OfferedSlot(
                conversation_id=conversation_id,
                start_utc=start,
                end_utc=end,
                label=_label_of(raw, start),
                service_key=service_key,
            )
        )
    return out


def _slots_for_llm(slots: list[OfferedSlot]) -> list[dict[str, str]]:
    return [{"start_utc": _iso_z(s.start_utc), "label": s.label} for s in slots]


class ToolRuntime:
    """Ejecuta las tool-calls de UN turno y acumula sus efectos."""

    def __init__(
        self,
        ctx: AppContext,
        conv: Conversation,
        crm_conversation_id: str,
        profile: BusinessProfile | None = None,
    ) -> None:
        self._ctx = ctx
        self._conv = conv
        self._crm_conv_id = crm_conversation_id
        self._profile = profile or BusinessProfile()
        # Efectos observables por turn.py:
        self.handoff_reason: str | None = None  # se ejecuta DESPUÉS de la despedida
        self.booked = False
        self.routed_out = False
        self.proposed = False

    async def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            if name == "update_ficha":
                return await self._update_ficha(args)
            if name == "propose_slots":
                return await self._propose_slots(args)
            if name == "book_session":
                return await self._book_session(args)
            if name == "reschedule_session":
                return await self._reschedule_session(args)
            if name == "route_out":
                return await self._route_out()
            if name == "identificar_plaga":
                return self._identificar_plaga(args)
            if name == "handoff":
                return self._handoff(args)
            logger.warning("tools: herramienta desconocida %r", name)
            return {"ok": False, "error": f"herramienta desconocida: {name}"}
        except CrmError as exc:
            logger.warning("tools: %s falló contra el CRM: %s", name, exc)
            return {
                "ok": False,
                "error": "crm_error",
                "detalle": "no pude completar la acción; continúa la conversación o haz handoff",
            }
        except CalendarError as exc:
            logger.warning("tools: %s falló contra la agenda: %s", name, exc)
            return {
                "ok": False,
                "error": "agenda_error",
                "detalle": "no pude completar la acción en la agenda; continúa la conversación o haz handoff",
            }

    async def _update_ficha(self, args: dict[str, Any]) -> dict[str, Any]:
        # Tolera el drift del LLM: manda lo que haya, el CRM normaliza flojo.
        ficha = {k: v for k, v in args.items() if v is not None}
        if not ficha:
            return {"ok": True, "nota": "sin campos nuevos"}
        await self._ctx.crm.put_ficha(self._crm_conv_id, ficha)
        return {"ok": True}

    async def _propose_slots(self, args: dict[str, Any]) -> dict[str, Any]:
        servicio_raw = str(args.get("servicio") or "")
        servicio = _normalizar_servicio(servicio_raw)
        if servicio is None:
            bajo_consulta = _es_bajo_consulta(servicio_raw)
            return {
                "ok": False,
                "error": "servicio_no_agendable",
                "detalle": (
                    "esta plaga es bajo consulta y no se agenda sola — haz "
                    "handoff para coordinar directo"
                    if bajo_consulta
                    else "no reconozco ese servicio; usa una plaga del catálogo o haz handoff"
                ),
            }
        raw = await self._ctx.calendar.get_availability(
            servicio, limit=MAX_OFFERED, per_day=OFFER_PER_DAY, days=OFFER_DAYS
        )
        slots = _slots_from_payload(self._conv.id, raw, servicio)
        if not slots:
            return {
                "ok": False,
                "error": "sin_disponibilidad",
                "detalle": "no hay horarios abiertos; ofrece handoff para coordinar directo",
            }
        await self._ctx.store.replace_offered_slots(self._conv.id, slots)
        self.proposed = True
        return {
            "ok": True,
            "slots": _slots_for_llm(slots),
            "dias_con_agenda": sorted(
                {s.label.rsplit(",", 1)[0].strip() for s in slots}
            ),
            "instrucciones": (
                "esta es TODA la agenda abierta: los días que no aparecen aquí "
                "NO tienen agenda, dilo en vez de mover al lead a otro día. "
                "Ofrécele máximo 3, con su etiqueta tal cual (día incluido), "
                "los que embonen con lo que pidió."
            ),
        }

    async def _resolve_offered(
        self, args: dict[str, Any], accion: str
    ) -> tuple[OfferedSlot | None, dict[str, Any] | None]:
        """Slot elegido, o el error listo para devolverle al LLM.

        Validación server-side por epoch exacto: solo lo ofrecido es reservable.
        """
        wanted = _parse_utc(str(args.get("start_utc") or ""))
        offered = await self._ctx.store.get_offered_slots(self._conv.id)
        if wanted is None:
            return None, {
                "ok": False,
                "error": "start_utc_invalido",
                "slots_ofrecidos": _slots_for_llm(offered),
            }
        chosen = next(
            (
                s
                for s in offered
                if int(s.start_utc.timestamp()) == int(wanted.timestamp())
            ),
            None,
        )
        if chosen is None:
            logger.info(
                "tools: %s rechazado — %s no está entre los ofrecidos",
                accion,
                args.get("start_utc"),
            )
            return None, {
                "ok": False,
                "error": "slot_no_ofrecido",
                "detalle": "solo puedes agendar un horario que ya ofreciste",
                "slots_ofrecidos": _slots_for_llm(offered),
            }
        # Deja rastro de sobre qué frase del lead se tomó la decisión: cuando
        # una cita sale mal, esto dice si hubo confirmación o se asumió.
        logger.info(
            "tools: %s a %s (el lead confirmó con: %r)",
            accion,
            chosen.label,
            str(args.get("dia_confirmado") or "")[:120],
        )
        return chosen, None

    def _resumen_evento(self, service_key: str) -> str:
        rule = SERVICE_RULES.get(service_key)
        etiqueta = rule.label if rule is not None else service_key
        return f"Visita {etiqueta} — {self._conv.wa_identity}"

    async def _book_session(self, args: dict[str, Any]) -> dict[str, Any]:
        chosen, error = await self._resolve_offered(args, "book_session")
        if error is not None or chosen is None:
            return error or {"ok": False, "error": "slot_no_ofrecido"}
        end = chosen.end_utc or (chosen.start_utc + timedelta(hours=1))
        try:
            result = await self._ctx.calendar.create_booking(
                chosen.start_utc,
                end,
                self._resumen_evento(chosen.service_key),
                f"Agendado por Nea. Conversación CRM {self._crm_conv_id}.",
                chosen.service_key,
            )
        except CalendarSlotTaken as exc:
            # El slot se ocupó entre oferta y elección: alternativas frescas.
            fresh = _slots_from_payload(self._conv.id, exc.slots, chosen.service_key)
            await self._ctx.store.replace_offered_slots(self._conv.id, fresh)
            return {
                "ok": False,
                "error": "slot_taken",
                "detalle": "ese horario se acaba de ocupar; discúlpate breve y ofrece estas alternativas",
                "slots": _slots_for_llm(fresh),
            }
        await self._ctx.store.clear_offered_slots(self._conv.id)
        await self._ctx.store.save_calendar_booking(
            self._conv.id, result["event_id"], chosen.service_key, chosen.start_utc, end
        )
        self.booked = True
        try:
            await self._ctx.crm.put_ficha(
                self._crm_conv_id, {"calificado": True, "resultado": "agendo"}
            )
        except CrmError as exc:  # best-effort: la cita ya existe
            logger.warning("tools: no pude actualizar ficha tras booking: %s", exc)
        return {
            "ok": True,
            "label": chosen.label,
            "instrucciones": (
                "confirma el día COMPLETO y la hora tal cual dice label, y "
                "menciona lo que el negocio pida para llegar preparado"
            ),
        }

    async def _reschedule_session(self, args: dict[str, Any]) -> dict[str, Any]:
        chosen, error = await self._resolve_offered(args, "reschedule_session")
        if error is not None or chosen is None:
            return error or {"ok": False, "error": "slot_no_ofrecido"}
        active = await self._ctx.store.get_active_calendar_booking(self._conv.id)
        if active is None:
            return {
                "ok": False,
                "error": "sin_cita",
                "detalle": "el lead no tiene cita por delante; usa book_session",
            }
        end = chosen.end_utc or (chosen.start_utc + timedelta(hours=1))
        try:
            await self._ctx.calendar.reschedule_booking(
                active.google_event_id,
                active.start_utc,
                active.end_utc,
                chosen.start_utc,
                end,
                self._resumen_evento(chosen.service_key),
                f"Agendado por Nea. Conversación CRM {self._crm_conv_id}.",
                chosen.service_key,
            )
        except CalendarSlotTaken as exc:
            fresh = _slots_from_payload(self._conv.id, exc.slots, chosen.service_key)
            await self._ctx.store.replace_offered_slots(self._conv.id, fresh)
            return {
                "ok": False,
                "error": "slot_taken",
                "detalle": "ese horario se acaba de ocupar; discúlpate breve y ofrece estas alternativas",
                "slots": _slots_for_llm(fresh),
            }
        await self._ctx.store.clear_offered_slots(self._conv.id)
        await self._ctx.store.update_calendar_booking_time(self._conv.id, chosen.start_utc, end)
        self.booked = True
        return {
            "ok": True,
            "label": chosen.label,
            "instrucciones": (
                "confirma que quedó movida, con el día COMPLETO y la hora tal "
                "cual dice label"
            ),
        }

    async def _route_out(self) -> dict[str, Any]:
        # "dio_diy" es el valor del enum `resultado` en el gateway del CRM
        # (006); el nombre de la herramienta es genérico, el cable no cambia.
        await self._ctx.crm.put_ficha(
            self._crm_conv_id, {"calificado": False, "resultado": "dio_diy"}
        )
        self.routed_out = True
        out: dict[str, Any] = {"ok": True}
        if self._profile.resources:
            out["recursos"] = self._profile.resources
            out["instrucciones"] = "comparte estos recursos al despedirte, puerta abierta"
        return out

    def _identificar_plaga(self, args: dict[str, Any]) -> dict[str, Any]:
        tamano_color = str(args.get("tamano_color") or "")
        ubicacion = str(args.get("ubicacion") or "")
        return _clasificar_cucaracha(tamano_color, ubicacion)

    def _handoff(self, args: dict[str, Any]) -> dict[str, Any]:
        self.handoff_reason = str(args.get("reason") or "lead_request")
        return {
            "ok": True,
            "nota": (
                "el pase a humano se ejecutará después de tu mensaje de despedida"
            ),
        }
