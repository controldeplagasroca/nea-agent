"""Recordatorio de la visita al cliente, por plantilla de WhatsApp (Meta directo).

Reglas del dueño:
- Se manda el día ANTERIOR a la visita, entre 8:00 y 12:00 (hora de México).
- Si la visita se agendó ese mismo día del recordatorio, no hay: ya se le acaba de confirmar.
- Una sola vez por horario; si se reagenda, la cita nueva tiene el suyo.
- Respeta ALLOWED_WA_IDS (en pruebas no le escribe a nadie fuera de la lista).

Se enciende solo si están META_WA_TOKEN, META_WA_PHONE_NUMBER_ID y
META_WA_TEMPLATE_RECORDATORIO. La plantilla debe estar APROBADA en Meta.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.crm import CrmError
from app.gcal import SERVICE_RULES, _day_label_es
from app.horarios import zona_agente
from app.meta_wa import MetaError
from app.plagas.caso import Caso
from app.state import AppContext, CalendarBooking, utcnow

logger = logging.getLogger("nea.visit_reminders")

HORA_DESDE, HORA_HASTA = 8, 12  # el recordatorio sale la mañana del día anterior


def ventana_de_envio(inicio_utc: datetime, tz) -> tuple[datetime, datetime]:
    """(desde, hasta) en UTC: de 8:00 a 12:00 del día ANTERIOR a la visita."""
    dia = inicio_utc.astimezone(tz).date() - timedelta(days=1)
    desde = datetime(dia.year, dia.month, dia.day, HORA_DESDE, tzinfo=tz)
    hasta = datetime(dia.year, dia.month, dia.day, HORA_HASTA, tzinfo=tz)
    return desde.astimezone(timezone.utc), hasta.astimezone(timezone.utc)


class VisitReminderWorker:
    INTERVAL = 300.0

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.INTERVAL)
            try:
                await self.tick()
            except Exception:
                logger.exception("visit_reminders: fallo en el barrido")

    async def tick(self, now: datetime | None = None) -> int:
        """Manda los recordatorios que ya tocan; regresa cuántos salieron."""
        now = now or utcnow()
        ctx = self._ctx
        tz = zona_agente(ctx.settings.agent_timezone)
        enviados = 0
        # Las visitas de hoy y de mañana; cada una tiene su propia ventana.
        for booking in await ctx.store.list_bookings_for_visit_reminder(now + timedelta(days=2)):
            desde, hasta = ventana_de_envio(booking.start_utc, tz)
            if not (desde <= now < hasta):
                continue
            if booking.created_at >= desde:
                continue  # se agendó ese mismo día: ya se le acaba de confirmar
            try:
                if await self._enviar(booking, tz, now):
                    enviados += 1
            except Exception:
                logger.exception("visit_reminders: recordatorio de la cita %s falló", booking.id)
        return enviados

    async def _enviar(self, booking: CalendarBooking, tz, now: datetime) -> bool:
        ctx = self._ctx
        conv = await ctx.store.get_conversation(booking.conversation_id)
        if conv is None:
            return False
        permitidos = ctx.settings.allowed_identities
        if permitidos and conv.wa_identity not in permitidos:
            logger.info("visit_reminders: %s fuera de ALLOWED_WA_IDS, no se manda", conv.wa_identity)
            return False
        caso = Caso.desde(conv.caso)
        local = booking.start_utc.astimezone(tz)
        cuando = f"{_day_label_es(local.date(), now.astimezone(tz).date())}, {local:%H:%M}"
        regla = SERVICE_RULES.get(booking.service_key)
        plaga = regla.label.lower() if regla is not None else booking.service_key
        direccion = caso.direccion_texto() or "la dirección que nos diste"
        nombre = await self._nombre(conv.wa_identity)
        try:
            await ctx.meta.enviar_plantilla(
                conv.wa_identity,
                ctx.settings.meta_wa_template_recordatorio,
                [nombre, plaga, cuando, direccion],
            )
        except MetaError as exc:
            # Sin marcar: se reintenta en el siguiente barrido.
            logger.warning("visit_reminders: no pude mandar el recordatorio %s: %s", booking.id, exc)
            return False
        await ctx.store.mark_visit_reminder_sent(booking.id)
        logger.info("visit_reminders: recordatorio de la cita %s enviado", booking.id)
        return True

    async def _nombre(self, identity: str) -> str:
        """Primer nombre del contacto en el CRM; «cliente» si no hay."""
        try:
            contexto = await self._ctx.crm.get_context(identity)
        except CrmError:
            return "cliente"
        nombre = str(((contexto or {}).get("contact") or {}).get("name") or "").strip()
        primero = nombre.split()[0] if nombre else ""
        # El CRM a veces guarda el teléfono como nombre.
        return primero if primero and not primero.lstrip("+").isdigit() else "cliente"
