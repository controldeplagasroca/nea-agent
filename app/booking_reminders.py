"""Recordatorio de aprobación: reenvío al dueño mientras una cita siga
`pendiente` (ver app/approvals.py y app/tools.py::book_session).

Loop asyncio cada 60 s. Cada `pending_booking` vencido (`next_reminder_at`)
se reenvía y se reprograma `settings.booking_reminder_minutes` adelante —
indefinido, sin límite de reintentos (decisión explícita del dueño: prefiere
esperar antes que perder el control de qué se agenda).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.approvals import enviar_solicitud_aprobacion, next_reminder
from app.state import AppContext, utcnow

logger = logging.getLogger("nea.booking_reminders")


class ApprovalReminderWorker:
    INTERVAL = 60.0

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.INTERVAL)
            try:
                await self.tick()
            except Exception:
                logger.exception("booking_reminders: fallo en el barrido")

    async def tick(self, now: datetime | None = None) -> None:
        now = now or utcnow()
        for pending in await self._ctx.store.due_booking_reminders(now):
            try:
                enviado = await enviar_solicitud_aprobacion(self._ctx, pending)
                if enviado:
                    logger.info(
                        "booking_reminders: recordatorio de la cita #%s reenviado "
                        "(van %d)",
                        pending.id,
                        pending.reminders_sent + 1,
                    )
                else:
                    logger.warning(
                        "booking_reminders: no pude reenviar el recordatorio de "
                        "la cita #%s — reintento en %s min",
                        pending.id,
                        self._ctx.settings.booking_reminder_minutes,
                    )
                await self._ctx.store.mark_booking_reminder_sent(
                    pending.id,
                    next_reminder(self._ctx.settings.booking_reminder_minutes),
                )
            except Exception:
                logger.exception(
                    "booking_reminders: recordatorio de la cita #%s falló",
                    pending.id,
                )
