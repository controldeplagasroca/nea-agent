"""API para que Vocero (la bandeja) liste y resuelva las citas por aprobar.

Es la segunda y tercera vía de confirmación, junto a «sí N» por WhatsApp del dueño:
- el panel de Vocero con Aprobar / Rechazar / Proponer otra hora, y
- el interruptor «Confirmar cita» del chat, que aprueba y deja que Nea escriba al
  cliente el texto de confirmación.

Las tres terminan en `resolver_aprobacion`: se crea (o se mueve) el evento y el cliente
recibe la confirmación UNA sola vez. Si una vía ya la resolvió, las demás ya no la ven.

Autenticación: header `X-Vocero-Secret` contra VOCERO_API_SECRET. Sin secreto, 503
(falla cerrado: estos endpoints crean citas y escriben a clientes).
"""
from __future__ import annotations

import hmac
import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.approvals import proponer_horario, resolver_aprobacion
from app.gcal import SERVICE_RULES
from app.state import PendingBooking

logger = logging.getLogger("nea.citas_api")
router = APIRouter()


def _no_autorizado(request: Request) -> JSONResponse | None:
    ctx = request.app.state.ctx
    if ctx is None:
        return JSONResponse({"error": "arrancando"}, status_code=503)
    secreto = ctx.settings.vocero_api_secret
    if not secreto:
        logger.error("citas_api: VOCERO_API_SECRET sin configurar — 503")
        return JSONResponse({"error": "api no configurada"}, status_code=503)
    recibido = request.headers.get("x-vocero-secret") or ""
    if not hmac.compare_digest(recibido, secreto):
        logger.warning("citas_api: secreto inválido — 401")
        return JSONResponse({"error": "secreto inválido"}, status_code=401)
    return None


def _dto(p: PendingBooking) -> dict[str, Any]:
    regla = SERVICE_RULES.get(p.service_key)
    return {
        "id": p.id,
        "tipo": "reagendo" if p.kind == "reagendar" else "nueva",
        "estado": p.estado,
        "conversationId": p.crm_conversation_id,
        "plaga": regla.label if regla is not None else p.service_key,
        "fecha": p.label,
        "inicio": p.start_utc.isoformat(),
        "direccion": p.direccion,
        "nota": p.nota,
        "creada": p.created_at.isoformat(),
    }


@router.get("/vocero/citas-pendientes")
async def citas_pendientes(request: Request, conversationId: str | None = None) -> JSONResponse:
    if (negado := _no_autorizado(request)) is not None:
        return negado
    ctx = request.app.state.ctx
    citas = await ctx.store.list_open_pending_bookings()
    if conversationId:
        citas = [p for p in citas if p.crm_conversation_id == conversationId]
    return JSONResponse({"citas": [_dto(p) for p in citas]})


@router.post("/vocero/citas/{cita_id}/resolver")
async def resolver_cita(cita_id: int, request: Request) -> JSONResponse:
    if (negado := _no_autorizado(request)) is not None:
        return negado
    ctx = request.app.state.ctx
    try:
        cuerpo = await request.json()
    except Exception:
        return JSONResponse({"error": "json inválido"}, status_code=400)
    accion = str((cuerpo or {}).get("accion") or "").strip().lower()
    if accion not in ("aprobar", "rechazar", "proponer"):
        return JSONResponse({"error": "accion debe ser aprobar, rechazar o proponer"}, status_code=400)

    pending = await ctx.store.get_pending_booking(cita_id)
    if pending is None:
        return JSONResponse({"error": "cita no encontrada"}, status_code=404)
    if pending.estado not in ("pendiente", "esperando_cliente"):
        # Otra vía (WhatsApp del dueño, otro operador) ya la resolvió.
        return JSONResponse(
            {"error": "ya_resuelta", "estado": pending.estado}, status_code=409
        )

    if accion == "proponer":
        texto = str((cuerpo or {}).get("texto") or "").strip()
        if not texto:
            return JSONResponse({"error": "texto requerido (ej. «jueves 10 am»)"}, status_code=400)
        mensaje = await proponer_horario(ctx, pending, texto)
    else:
        mensaje = await resolver_aprobacion(ctx, pending, accion == "aprobar")
    logger.info("citas_api: cita #%s → %s", cita_id, accion)
    despues = await ctx.store.get_pending_booking(cita_id)
    return JSONResponse({"ok": True, "mensaje": mensaje, "estado": despues.estado if despues else None})
