"""Aprobación obligatoria del dueño antes de reservar una cita de verdad.

Cuando `settings.owner_identity` está configurado, `book_session`
(app/tools.py) ya no reserva directo en Google Calendar: crea un
`PendingBooking` y le pide al dueño "sí <folio>" / "no <folio>" por
WhatsApp. Este módulo centraliza el formateo del mensaje de solicitud, el
parseo de la respuesta del dueño, y la ejecución de la aprobación/rechazo —
lo reusan tanto el gate de `app/turn.py` (cuando el dueño responde) como
`app/booking_reminders.py` (reenvío periódico).
"""
from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar
from datetime import datetime, timedelta
from typing import Literal

from app.crm import CrmError
from app.gcal import SERVICE_RULES, CalendarError, CalendarSlotTaken
from app.state import AppContext, PendingBooking, utcnow

logger = logging.getLogger("nea.approvals")

# Marcador que delimita el bloque de datos estructurados dentro de la
# description del evento de Calendar -- ROCA Ops solo tiene acceso de
# LECTURA al calendario compartido (nunca a la BD de nea-agent), así que
# esto es la única forma de que sepa costo/dirección/teléfono sin un
# segundo sistema de integración. Ver roca-ops-backend/src/services/
# calendarService.ts (lectura) y la pestaña "Servicios" del admin-panel.
ROCA_OPS_DATA_MARKER = "---ROCA-OPS-DATA---"

# Mensaje al CLIENTE cuando la cita quedó SOLICITADA pero el dueño todavía no
# la aprueba. Es la única respuesta válida en ese turno: el agente no puede
# confirmar algo que no está confirmado. En vivo el modelo ignoró las
# instrucciones del prompt y del resultado de la herramienta y le dijo al
# cliente "¡Listo! He programado la cita para mañana a las 09:30" mientras la
# cita seguía pendiente — así que turn.py REEMPLAZA su texto por este.
MENSAJE_SOLICITUD_ENVIADA = (
    "Recibí tu solicitud 🙏 Estoy confirmando disponibilidad con el equipo y "
    "te aviso en breve."
)


def construir_description_evento(
    *,
    texto_base: str,
    telefono_cliente: str,
    direccion: str,
    service_key: str,
    costo: float,
    crm_conversation_id: str,
) -> str:
    payload = {
        "telefono_cliente": telefono_cliente,
        "direccion": direccion,
        "plaga": service_key,
        "costo": costo,
        "crm_conversation_id": crm_conversation_id,
    }
    return f"{texto_base}\n\n{ROCA_OPS_DATA_MARKER}\n{json.dumps(payload, ensure_ascii=False)}"

# ÚNICO formato que aprueba o rechaza: un verbo y el folio, en ese orden y sin
# nada más alrededor. Antes esto era "¿aparece la palabra sí o no en cualquier
# parte del mensaje?" y con una sola cita pendiente bastaba. En vivo el dueño
# escribió "Verifica si es para controlar roedores ya que la petición del
# cliente es cucaracha de cocina" — que contiene la palabra "si" como
# CONDICIONAL — y el sistema lo tomó como aprobación, reservó la cita y le
# mandó al cliente "¡Confirmado! Te esperamos...". Una cita que nadie aprobó.
_VERBOS_APRUEBA = (
    "si", "aprobar", "aprueba", "apruebo", "aprobado", "confirmar",
    "confirma", "confirmo", "autorizar", "autoriza", "ok", "dale",
)
_VERBOS_RECHAZA = (
    "no", "rechazar", "rechaza", "rechazo", "rechazado", "cancelar",
    "cancela", "anular", "anula",
)
_RE_APRUEBA = re.compile(
    r"^\W*(?:" + "|".join(_VERBOS_APRUEBA) + r")\b[^\d]{0,3}(?:#\s*)?(\d{1,6})\W*$"
)
_RE_RECHAZA = re.compile(
    r"^\W*(?:" + "|".join(_VERBOS_RECHAZA) + r")\b[^\d]{0,3}(?:#\s*)?(\d{1,6})\W*$"
)
# Para detectar si el mensaje PARECÍA un intento de responder (y merece que se
# le explique el formato) aunque no lo fuera.
_SI_PALABRAS = _VERBOS_APRUEBA
_NO_PALABRAS = _VERBOS_RECHAZA
_FOLIO_RE = re.compile(r"#\s*(\d+)|\b(\d+)\b")

ParseoKind = Literal["no_reconocido", "ambiguo", "resuelto", "formato_invalido"]


def _sin_acentos(texto: str) -> str:
    reemplazos = str.maketrans("áéíóúñ", "aeioun")
    return texto.translate(reemplazos)


def _contiene_palabra(texto: str, palabras: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(p)}\b", texto) for p in palabras)


def formatear_solicitud(pending: PendingBooking) -> str:
    rule = SERVICE_RULES.get(pending.service_key)
    plaga = rule.label if rule is not None else pending.service_key
    if pending.kind == "reagendar":
        return (
            f"🔄 Reagendo #{pending.id} por aprobar\n"
            f"Plaga: {plaga}\n"
            f"Nueva fecha: {pending.label}\n\n"
            f'Responde "sí {pending.id}" o "no {pending.id}" para confirmar o rechazar.'
        )
    nota = f"{pending.nota}\n" if pending.nota else ""
    return (
        f"🐜 Cita #{pending.id} por aprobar\n"
        f"Plaga: {plaga}\n"
        f"Fecha: {pending.label}\n"
        f"Dirección: {pending.direccion}\n"
        f"{nota}\n"
        f'Responde "sí {pending.id}" o "no {pending.id}" para confirmar o rechazar.'
    )


def parece_aprobacion(
    texto: str, pendientes: list[PendingBooking]
) -> tuple[ParseoKind, PendingBooking | None, bool | None]:
    """Interpreta un mensaje del dueño contra la lista de pendientes.

    Solo un formato EXPLÍCITO resuelve una cita: «sí 6», «no 6», «aprobar 6»,
    «rechazar 6», «confirmar 6», «cancelar 6» (con «#» opcional).

    - ("no_reconocido", None, None): no es una respuesta de aprobación. El
      mensaje sigue el flujo normal de conversación.
    - ("formato_invalido", None, None): PARECE un intento (trae un verbo de
      aprobación o un número) pero no cumple el formato. NO aprueba ni rechaza:
      la cita sigue pendiente y se le explica cómo responder.
    - ("ambiguo", None, None): el formato es válido pero el folio no existe
      entre las pendientes.
    - ("resuelto", pending, aprueba): aprobación o rechazo inequívoco.
    """
    if not pendientes:
        return "no_reconocido", None, None
    t = _sin_acentos(texto.lower())

    m_aprueba = _RE_APRUEBA.match(t)
    m_rechaza = _RE_RECHAZA.match(t)
    if m_aprueba or m_rechaza:
        folio = int((m_aprueba or m_rechaza).group(1))
        pending = next((p for p in pendientes if p.id == folio), None)
        if pending is None:
            return "ambiguo", None, None
        return "resuelto", pending, m_aprueba is not None

    # No cumple el formato. ¿Parecía un intento de responder? Entonces se le
    # explica el formato en vez de dejarlo pasar como conversación normal.
    if _contiene_palabra(t, _VERBOS_APRUEBA + _VERBOS_RECHAZA) or _FOLIO_RE.search(t):
        return "formato_invalido", None, None
    return "no_reconocido", None, None


def formato_invalido_para_dueno(pendientes: list[PendingBooking]) -> str:
    """Respuesta cuando el dueño escribió algo que no es un formato válido.

    Deja claro que la cita SIGUE PENDIENTE: que el dueño comente algo no es
    aprobar, y el cliente no puede recibir una confirmación por eso.
    """
    if len(pendientes) == 1:
        f = pendientes[0].id
        return (
            f"No entendí tu respuesta 🙏 La cita #{f} sigue PENDIENTE.\n"
            f"Responde «sí {f}» para aprobarla o «no {f}» para rechazarla."
        )
    folios = ", ".join(f"#{p.id}" for p in pendientes)
    return (
        f"No entendí tu respuesta 🙏 Siguen PENDIENTES: {folios}.\n"
        "Responde «sí <folio>» para aprobar o «no <folio>» para rechazar."
    )


def listar_pendientes_para_dueno(pendientes: list[PendingBooking]) -> str:
    lineas = [f"#{p.id} — {p.label} ({p.direccion})" for p in pendientes]
    return "Tienes varias citas por aprobar, dime el folio:\n" + "\n".join(lineas)


async def enviar_solicitud_aprobacion(ctx: AppContext, pending: PendingBooking) -> bool:
    """Le manda a Leopoldo el mensaje de folio. True si se pudo enviar."""
    owner_identity = ctx.settings.owner_identity
    if not owner_identity:
        return False
    try:
        owner_context = await ctx.crm.get_context(owner_identity)
        owner_conv_id = ((owner_context or {}).get("conversation") or {}).get("id")
        if not owner_conv_id:
            logger.warning("approvals: sin conversationId del dueño — no pude avisar")
            return False
        await ctx.crm.send_message(str(owner_conv_id), formatear_solicitud(pending))
        # Queda constancia de que el dueño YA lo recibió. El worker de
        # recordatorios lo consulta para no volver a mandar el mismo mensaje:
        # solo reenvía si esto es False (un reintento real, porque el envío
        # anterior nunca llegó).
        try:
            await ctx.store.mark_pending_avisado(pending.id)
        except Exception:  # best-effort: si falla, el peor caso es un reenvío
            logger.warning(
                "approvals: no pude marcar como avisado el pendiente #%s", pending.id
            )
        return True
    except CrmError as exc:
        logger.warning("approvals: no pude avisar al dueño de la cita #%s: %s", pending.id, exc)
        return False


# Cuántos avisos al lead fallaron dentro de la resolución en curso. Tras pasarle
# la conversación al dueño la IA queda en pausa y el CRM puede negarse a que el
# bot escriba: el dueño tiene que enterarse para avisarle él.
_avisos_fallidos: ContextVar[int] = ContextVar("avisos_fallidos", default=0)

NOTA_LEAD_SIN_AVISO = (
    "\n⚠️ No pude avisarle al cliente (la IA de esa conversación puede estar "
    "en pausa). Escríbele tú desde la bandeja."
)


async def _notificar_lead(ctx: AppContext, pending: PendingBooking, texto: str) -> None:
    try:
        await ctx.crm.send_message(pending.crm_conversation_id, texto)
        await ctx.store.add_message(pending.conversation_id, "assistant", texto)
    except CrmError as exc:
        _avisos_fallidos.set(_avisos_fallidos.get() + 1)
        logger.warning(
            "approvals: no pude avisarle al lead de la cita #%s: %s", pending.id, exc
        )


def _resumen_evento(pending: PendingBooking) -> str:
    rule = SERVICE_RULES.get(pending.service_key)
    etiqueta = rule.label if rule is not None else pending.service_key
    return f"Visita {etiqueta} (aprobado)"


async def _resolver_reagendo(ctx: AppContext, pending: PendingBooking) -> str:
    """Rama de resolver_aprobacion para kind="reagendar": mueve un evento
    YA existente en vez de crear uno nuevo (ver reschedule_session en
    app/tools.py)."""
    active = await ctx.store.get_active_calendar_booking(pending.conversation_id)
    if active is None or not pending.google_event_id:
        await ctx.store.resolve_pending_booking(pending.id, "rechazado")
        await _notificar_lead(
            ctx,
            pending,
            "No encontré tu cita original para moverla 😔 ¿Me compartes de nuevo "
            "los datos de tu cita?",
        )
        return (
            f"No encontré la cita original para el reagendo #{pending.id} — "
            "revísalo en Calendar."
        )
    try:
        await ctx.calendar.reschedule_booking(
            pending.google_event_id,
            active.start_utc,
            active.end_utc,
            pending.start_utc,
            pending.end_utc,
            _resumen_evento(pending),
            f"Agendado por Nea (aprobado). Conversación CRM {pending.crm_conversation_id}.",
            pending.service_key,
        )
    except CalendarSlotTaken:
        await ctx.store.resolve_pending_booking(pending.id, "rechazado")
        await _notificar_lead(
            ctx,
            pending,
            "Justo ese horario se acaba de ocupar mientras confirmábamos 😔 "
            "¿Buscamos otro?",
        )
        return (
            f"Uy, reagendo #{pending.id}: ese horario se ocupó justo ahora — "
            "avisé al cliente para que elija otro."
        )
    except CalendarError as exc:
        logger.warning("approvals: reschedule_booking falló para #%s: %s", pending.id, exc)
        return f"No pude mover la cita #{pending.id} en la agenda — revísalo en Calendar."

    await ctx.store.update_calendar_booking_time(
        pending.conversation_id, pending.start_utc, pending.end_utc
    )
    await ctx.store.resolve_pending_booking(pending.id, "aprobado")
    await _notificar_lead(
        ctx,
        pending,
        f"¡Listo! Tu cita quedó movida para {pending.label}. 🪳✅",
    )
    return f"Listo, reagendo #{pending.id} confirmado y avisado al cliente ✅"


async def _resolver(ctx: AppContext, pending: PendingBooking, aprobado: bool) -> str:
    """Ejecuta la aprobación/rechazo, avisa al lead, y regresa el texto de
    confirmación breve para el dueño."""
    if not aprobado:
        await ctx.store.resolve_pending_booking(pending.id, "rechazado")
        await _actualizar_caso(ctx, pending, confirmada=False)
        await _notificar_lead(
            ctx, pending, await _texto_rechazo_con_alternativas(ctx, pending)
        )
        if pending.kind == "reagendar":
            return f"Ok, reagendo #{pending.id} rechazado — ya avisé al cliente ❌"
        return f"Ok, cita #{pending.id} rechazada — ya avisé al cliente ❌"

    if pending.kind == "reagendar":
        return await _resolver_reagendo(ctx, pending)

    description = construir_description_evento(
        texto_base=f"Agendado por Nea (aprobado). Conversación CRM {pending.crm_conversation_id}.",
        telefono_cliente=pending.telefono_cliente,
        direccion=pending.direccion,
        service_key=pending.service_key,
        costo=pending.costo_cotizado,
        crm_conversation_id=pending.crm_conversation_id,
    )
    try:
        result = await ctx.calendar.create_booking(
            pending.start_utc,
            pending.end_utc,
            _resumen_evento(pending),
            description,
            pending.service_key,
        )
    except CalendarSlotTaken:
        # Alguien más tomó el horario mientras se esperaba la aprobación.
        await ctx.store.resolve_pending_booking(pending.id, "rechazado")
        await _notificar_lead(
            ctx,
            pending,
            "Justo ese horario se acaba de ocupar mientras confirmábamos 😔 "
            "¿Buscamos otro?",
        )
        return (
            f"Uy, cita #{pending.id}: ese horario se ocupó justo ahora — "
            f"avisé al cliente para que elija otro."
        )
    except CalendarError as exc:
        logger.warning("approvals: create_booking falló para #%s: %s", pending.id, exc)
        return f"No pude reservar la cita #{pending.id} en la agenda — revísalo en Calendar."

    await ctx.store.save_calendar_booking(
        pending.conversation_id,
        result["event_id"],
        pending.service_key,
        pending.start_utc,
        pending.end_utc,
    )
    await ctx.store.clear_offered_slots(pending.conversation_id)
    await ctx.store.resolve_pending_booking(pending.id, "aprobado")
    await _actualizar_caso(ctx, pending, confirmada=True)
    try:
        await ctx.crm.put_ficha(
            pending.crm_conversation_id,
            {"calificado": True, "resultado": "agendo", "geo": pending.direccion},
        )
    except CrmError as exc:
        logger.warning("approvals: no pude actualizar ficha tras aprobar #%s: %s", pending.id, exc)
    # Sin «hoy»/«mañana»: el dueño puede aprobar días después de la solicitud.
    await _notificar_lead(
        ctx,
        pending,
        f"¡Confirmado! ✅ Te esperamos el {_sin_relativo(pending.label)} en {pending.direccion}.",
    )
    return f"Listo, cita #{pending.id} confirmada y avisado al cliente ✅"


def _sin_relativo(etiqueta: str) -> str:
    """«mañana lunes 5 de octubre, 11:00» → «lunes 5 de octubre, 11:00»."""
    return re.sub(r"^(hoy|mañana)\s+", "", etiqueta.strip())


async def _actualizar_caso(ctx: AppContext, pending: PendingBooking, *, confirmada: bool) -> None:
    """Refleja la decisión del dueño en el expediente de la conversación.

    Si no, el bot sigue diciendo «tu solicitud está pendiente» después de la
    confirmación, o se queda sin poder ofrecer otro horario tras un rechazo.
    Best-effort: la decisión ya está tomada y avisada.
    """
    try:
        conv = await ctx.store.get_conversation(pending.conversation_id)
        if conv is None:
            return
        caso = dict(conv.caso or {})
        if confirmada:
            cita = dict(caso.get("cita") or {})
            cita["estado"] = "confirmada"
            caso["cita"] = cita
        else:
            caso["cita"] = None
            caso["escalado"] = ""
        await ctx.store.update_conversation(pending.conversation_id, caso=caso)
    except Exception as exc:  # noqa: BLE001
        logger.warning("approvals: no pude actualizar el expediente de #%s: %s", pending.id, exc)


# Frases del texto para el dueño que afirman que el cliente YA fue avisado; si el
# aviso falló, no se pueden dejar (el dueño leería «avisado» y la nota de que no).
_FRASES_DE_AVISO = (
    " y avisado al cliente",
    " — ya avisé al cliente",
    " — avisé al cliente para que elija otro",
    " avisé al cliente para que elija otro",
)


async def resolver_aprobacion(ctx: AppContext, pending: PendingBooking, aprobado: bool) -> str:
    """Ejecuta la aprobación/rechazo, avisa al lead y regresa el texto breve
    para el dueño (con una nota si el aviso al cliente no salió)."""
    _avisos_fallidos.set(0)
    texto = await _resolver(ctx, pending, aprobado)
    if _avisos_fallidos.get():
        for frase in _FRASES_DE_AVISO:
            texto = texto.replace(frase, "")
        texto += NOTA_LEAD_SIN_AVISO
    return texto


async def _texto_rechazo_con_alternativas(ctx: AppContext, pending: PendingBooking) -> str:
    """Rechazo del dueño con horarios REALES de la agenda como alternativa.

    Un "¿buscamos otro?" a secas deja al cliente haciendo el trabajo. El
    negocio pidió ofrecer opciones concretas, así que se consultan huecos
    reales y se guardan como ofrecidos: el cliente elige uno y el agente lo
    agenda sin tener que volver a proponer.
    """
    base = "No tengo disponible ese horario 😔"
    try:
        # Import local: app/tools.py importa este módulo a nivel de archivo.
        from app.tools import (
            MAX_OFFERED,
            OFFER_DAYS,
            OFFER_PER_DAY,
            _slots_from_payload,
        )

        crudos = await ctx.calendar.get_availability(
            pending.service_key,
            limit=MAX_OFFERED,
            per_day=OFFER_PER_DAY,
            days=OFFER_DAYS,
        )
    except Exception as exc:  # degradación amplia a propósito: nunca dejar al cliente sin respuesta
        logger.warning(
            "approvals: sin disponibilidad que ofrecer tras el rechazo de #%s: %s",
            pending.id,
            exc,
        )
        return f"{base} ¿Buscamos otro horario que te acomode?"

    slots = _slots_from_payload(pending.conversation_id, crudos)
    if not slots:
        return f"{base} ¿Buscamos otro horario que te acomode?"

    await ctx.store.replace_offered_slots(pending.conversation_id, slots)
    opciones = "\n".join(f"• {s.label}" for s in slots[:3])
    return f"{base}\n¿Te sirve alguno de estos?\n{opciones}"


def next_reminder(minutes: float) -> datetime:
    return utcnow() + timedelta(minutes=minutes)


async def atender_respuesta_del_dueno(ctx: AppContext, identity: str, inbound: list) -> bool:
    """Gate del turno: ¿este mensaje del dueño aprueba o rechaza una visita?

    True = el mensaje se atendió (se contestó al dueño) y el turno termina ahí;
    nunca debe llegar al modelo como si fuera un lead. False = no era una
    respuesta de aprobación: sigue el flujo normal.
    """
    pendientes = await ctx.store.list_pending_bookings_pendientes()
    if not pendientes:
        return False
    texto = " ".join((m.text or "") for m in inbound).strip()
    kind, pending, aprueba = parece_aprobacion(texto, pendientes)
    respuesta: str | None = None
    if kind == "resuelto" and pending is not None and aprueba is not None:
        respuesta = await resolver_aprobacion(ctx, pending, aprueba)
    elif kind == "formato_invalido":
        # Una pregunta, un comentario: NO aprueba ni rechaza. La visita sigue
        # pendiente y se le explica el formato.
        logger.info(
            "gate aprobación: mensaje del dueño sin formato válido — "
            "las citas siguen pendientes (%r)",
            texto[:80],
        )
        respuesta = formato_invalido_para_dueno(pendientes)
    elif kind == "ambiguo":
        respuesta = listar_pendientes_para_dueno(pendientes)
    if respuesta is None:
        return False
    try:
        contexto = await ctx.crm.get_context(identity)
        conv_id = ((contexto or {}).get("conversation") or {}).get("id")
        if conv_id:
            await ctx.crm.send_message(str(conv_id), respuesta)
        else:
            logger.warning("gate aprobación: sin conversationId del dueño para responder")
    except CrmError as exc:
        logger.warning("gate aprobación: no pude responderle al dueño: %s", exc)
    return True
