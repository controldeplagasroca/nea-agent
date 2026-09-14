"""Aviso entrante de cambios de servicio, desde ROCA Ops / Hermes.

Nea agenda la cita inicial en Calendar y la rastrea en `calendar_bookings`
(ver app/state.py), pero nunca se entera de lo que pasa despues del lado de
ROCA Ops: asignacion de tecnico, cancelacion, o reagendado manual. Sin este
endpoint, `calendar_bookings` queda desactualizado -- reschedule_session
podria intentar mover una cita ya cancelada, o el booking-reminder-worker
seguiria avisando de una cita que ya no existe.

Aditivo: no toca el flujo de WhatsApp/Meta (app/webhook.py) para nada. Si
SERVICE_SYNC_SECRET no esta configurado, el endpoint rechaza todo con 401 y
el resto del bot sigue funcionando exactamente igual que antes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from app.state import AppContext

logger = logging.getLogger("nea.service_events")

router = APIRouter()


class ServiceEventPayload(BaseModel):
    calendarEventId: str
    eventType: str  # "asignado" | "cancelado" | "reagendado" | "fallido"
    nuevaFecha: str | None = None  # YYYY-MM-DD, solo con eventType="reagendado"
    nuevaHora: str | None = None  # HH:MM (24h), solo con eventType="reagendado"


@router.post("/internal/service-events")
async def service_event(
    payload: ServiceEventPayload,
    request: Request,
    x_service_sync_secret: str | None = Header(default=None),
) -> dict[str, object]:
    ctx: AppContext = request.app.state.ctx
    secret = ctx.settings.service_sync_secret
    if not secret or x_service_sync_secret != secret:
        raise HTTPException(status_code=401, detail="secreto invalido o ausente")

    booking = await ctx.store.get_booking_by_event_id(payload.calendarEventId)
    if booking is None:
        # No es un error: la cita puede haberse agendado manualmente (no via
        # Nea), o ya estar cancelada/fuera de calendar_bookings.
        logger.info(
            "service_event: sin booking activo para calendarEventId=%s (%s)",
            payload.calendarEventId,
            payload.eventType,
        )
        return {"ok": True, "matched": False}

    if payload.eventType == "cancelado":
        await ctx.store.cancel_calendar_booking(booking.conversation_id)
        logger.info(
            "service_event: booking conversation_id=%s cancelado (evento %s)",
            booking.conversation_id,
            payload.calendarEventId,
        )
    elif payload.eventType == "reagendado" and payload.nuevaFecha and payload.nuevaHora:
        try:
            tz = ZoneInfo(ctx.settings.agent_timezone)
            local_dt = datetime.strptime(
                f"{payload.nuevaFecha} {payload.nuevaHora}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=tz)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"fecha/hora invalida: {exc}") from exc
        start_utc = local_dt.astimezone(timezone.utc)
        end_utc = start_utc + timedelta(hours=2)
        await ctx.store.update_calendar_booking_time(booking.conversation_id, start_utc, end_utc)
        logger.info(
            "service_event: booking conversation_id=%s movido a %s (evento %s)",
            booking.conversation_id,
            start_utc.isoformat(),
            payload.calendarEventId,
        )
    else:
        # "asignado" / "fallido": informativo -- no cambia el booking en si,
        # solo queda en el log para trazabilidad.
        logger.info(
            "service_event: %s para booking conversation_id=%s (sin cambio de estado)",
            payload.eventType,
            booking.conversation_id,
        )

    return {"ok": True, "matched": True, "conversation_id": booking.conversation_id}
