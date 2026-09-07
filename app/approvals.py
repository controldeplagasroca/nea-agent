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

_SI_PALABRAS = (
    "si", "sí", "aprobar", "aprobado", "aprueba", "apruebo", "confirmar",
    "confirmo",
)
_NO_PALABRAS = (
    "no", "rechazar", "rechazado", "rechaza", "rechazo", "cancelar",
)
_FOLIO_RE = re.compile(r"#\s*(\d+)|\b(\d+)\b")

ParseoKind = Literal["no_reconocido", "ambiguo", "resuelto"]


def _sin_acentos(texto: str) -> str:
    reemplazos = str.maketrans("áéíóúñ", "aeioun")
    return texto.translate(reemplazos)


def _contiene_palabra(texto: str, palabras: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(p)}\b", texto) for p in palabras)


def formatear_solicitud(pending: PendingBooking) -> str:
    rule = SERVICE_RULES.get(pending.service_key)
    plaga = rule.label if rule is not None else pending.service_key
    return (
        f"🐜 Cita #{pending.id} por aprobar\n"
        f"Plaga: {plaga}\n"
        f"Fecha: {pending.label}\n"
        f"Dirección: {pending.direccion}\n\n"
        f'Responde "sí {pending.id}" o "no {pending.id}" para confirmar o rechazar.'
    )


def parece_aprobacion(
    texto: str, pendientes: list[PendingBooking]
) -> tuple[ParseoKind, PendingBooking | None, bool | None]:
    """Interpreta un mensaje del dueño contra la lista de pendientes.

    - ("no_reconocido", None, None): no tiene pinta de respuesta de
      aprobación — el mensaje debe seguir el flujo normal de conversación.
    - ("ambiguo", None, None): SÍ tiene pinta de aprobación (dijo sí/no) pero
      no se pudo determinar a cuál folio aplica (citó uno que no existe, o
      hay varias pendientes y no citó ninguno).
    - ("resuelto", pending, aprueba): folio identificado sin ambigüedad.
    """
    if not pendientes:
        return "no_reconocido", None, None
    t = _sin_acentos(texto.lower())
    tiene_si = _contiene_palabra(t, _SI_PALABRAS)
    tiene_no = _contiene_palabra(t, _NO_PALABRAS)
    if tiene_si == tiene_no:  # ninguna de las dos, o las dos a la vez
        return "no_reconocido", None, None
    match = _FOLIO_RE.search(t)
    folio = int(match.group(1) or match.group(2)) if match else None
    if folio is not None:
        pending = next((p for p in pendientes if p.id == folio), None)
        if pending is None:
            return "ambiguo", None, None
        return "resuelto", pending, tiene_si
    if len(pendientes) == 1:
        return "resuelto", pendientes[0], tiene_si
    return "ambiguo", None, None


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
        return True
    except CrmError as exc:
        logger.warning("approvals: no pude avisar al dueño de la cita #%s: %s", pending.id, exc)
        return False


async def _notificar_lead(ctx: AppContext, pending: PendingBooking, texto: str) -> None:
    try:
        await ctx.crm.send_message(pending.crm_conversation_id, texto)
        await ctx.store.add_message(pending.conversation_id, "assistant", texto)
    except CrmError as exc:
        logger.warning(
            "approvals: no pude avisarle al lead de la cita #%s: %s", pending.id, exc
        )


def _resumen_evento(pending: PendingBooking) -> str:
    rule = SERVICE_RULES.get(pending.service_key)
    etiqueta = rule.label if rule is not None else pending.service_key
    return f"Visita {etiqueta} (aprobado)"


async def resolver_aprobacion(ctx: AppContext, pending: PendingBooking, aprobado: bool) -> str:
    """Ejecuta la aprobación/rechazo, avisa al lead, y regresa el texto de
    confirmación breve para el dueño."""
    if not aprobado:
        await ctx.store.resolve_pending_booking(pending.id, "rechazado")
        await _notificar_lead(
            ctx,
            pending,
            "Justo esa fecha y hora no se pudo confirmar con el equipo 🙏 "
            "¿Buscamos otro horario que te acomode?",
        )
        return f"Ok, cita #{pending.id} rechazada — ya avisé al cliente ❌"

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
    try:
        await ctx.crm.put_ficha(
            pending.crm_conversation_id,
            {"calificado": True, "resultado": "agendo", "geo": pending.direccion},
        )
    except CrmError as exc:
        logger.warning("approvals: no pude actualizar ficha tras aprobar #%s: %s", pending.id, exc)
    await _notificar_lead(
        ctx,
        pending,
        f"¡Listo! Tu cita quedó confirmada para {pending.label} en {pending.direccion}. 🪳✅",
    )
    return f"Listo, cita #{pending.id} confirmada y avisado al cliente ✅"


def next_reminder(minutes: float) -> datetime:
    return utcnow() + timedelta(minutes=minutes)
