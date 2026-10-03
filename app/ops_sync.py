"""Integración ROCA OPS → Nea.

ROCA OPS (backend Express del negocio) empuja cambios de cliente hacia el CRM
para que la ficha del lead (`update_ficha`) se mantenga consistente con su base
de clientes: estado y próximo tratamiento son justo los datos que sostienen los
recordatorios de mantenimiento.

Antes de esto, `VOCERO_SYNC_URL` apuntaba a `POST /roca-ops/sync`, un endpoint
que **no existía** en este servicio: OPS recibía un 404 en cada intento, lo
reintentaba 4 veces con backoff y terminaba escribiendo el fallo en su log. La
sincronización nunca ocurrió, en silencio y desde el primer día.

Contrato (el que ya manda OPS, no se inventó uno nuevo):

    POST /roca-ops/sync
    X-Vocero-Secret: <ROCA_OPS_SYNC_SECRET>
    {
      "clientId": "cli_123",
      "phone": "525512345678",
      "fullName": "Ana Pérez",
      "status": "activo",
      "nextTreatmentDate": "2026-10-15"   // o null
    }

Responde 200 si la ficha quedó actualizada, 404 si el teléfono no tiene
conversación en el CRM (lead que aún no escribe: no es un error, OPS solo
registra), 401 si el secreto no cuadra y 503 si este servicio no tiene el
secreto configurado.
"""
from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import canonical_identity
from app.crm import CrmError

logger = logging.getLogger("nea.ops_sync")

router = APIRouter()


def _ficha_desde_payload(payload: dict) -> dict:
    """Mapea el payload de OPS a campos de la ficha del CRM.

    Se prefijan con `ops_` a propósito: la ficha la comparte el agente con los
    campos que descubre en la conversación (`geo`, `calificado`, ...) y no
    queremos que un sync del sistema pise lo que el lead dijo por WhatsApp.
    """
    ficha: dict = {}
    if payload.get("clientId"):
        ficha["ops_client_id"] = str(payload["clientId"])
    if payload.get("fullName"):
        ficha["ops_nombre"] = str(payload["fullName"])
    if payload.get("status"):
        ficha["ops_estado"] = str(payload["status"])
    # `nextTreatmentDate` puede venir explícitamente en null: eso BORRA el
    # recordatorio (el cliente ya no tiene tratamiento programado), así que se
    # escribe igual en vez de omitirse.
    if "nextTreatmentDate" in payload:
        ficha["ops_proximo_tratamiento"] = (
            str(payload["nextTreatmentDate"])
            if payload.get("nextTreatmentDate")
            else None
        )
    return ficha


@router.post("/roca-ops/sync")
async def sync_cliente(request: Request) -> JSONResponse:
    ctx = request.app.state.ctx
    if ctx is None:
        return JSONResponse({"error": "arrancando"}, status_code=503)

    secreto = ctx.settings.roca_ops_sync_secret
    if not secreto:
        # Falla CERRADO: este endpoint escribe datos de clientes. Sin secreto
        # configurado no se atiende, en vez de aceptar a cualquiera.
        logger.error("roca-ops/sync: ROCA_OPS_SYNC_SECRET sin configurar — 503")
        return JSONResponse(
            {"error": "sincronización no configurada"}, status_code=503
        )
    recibido = request.headers.get("x-vocero-secret") or ""
    if not hmac.compare_digest(recibido, secreto):
        logger.warning("roca-ops/sync: secreto inválido — 401")
        return JSONResponse({"error": "secreto inválido"}, status_code=401)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "json inválido"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "payload debe ser un objeto"}, status_code=400)

    phone = canonical_identity(str(payload.get("phone") or ""))
    if not phone:
        return JSONResponse({"error": "phone requerido"}, status_code=400)

    try:
        context = await ctx.crm.get_context(phone)
    except CrmError as exc:
        logger.warning("roca-ops/sync: el CRM no respondió (%s)", exc)
        return JSONResponse({"error": "crm_no_disponible"}, status_code=502)

    conversacion = ((context or {}).get("conversation") or {})
    crm_conv_id = conversacion.get("id")
    if not crm_conv_id:
        # Lead que todavía no escribe por WhatsApp: no hay dónde escribir la
        # ficha. No es un error del llamador; OPS solo lo registra.
        logger.info("roca-ops/sync: %s sin conversación en el CRM — nada que hacer", phone)
        return JSONResponse({"ok": True, "sincronizado": False}, status_code=200)

    ficha = _ficha_desde_payload(payload)
    if not ficha:
        return JSONResponse({"ok": True, "sincronizado": False}, status_code=200)

    try:
        await ctx.crm.put_ficha(str(crm_conv_id), ficha)
    except CrmError as exc:
        logger.warning("roca-ops/sync: no pude escribir la ficha (%s)", exc)
        return JSONResponse({"error": "crm_no_disponible"}, status_code=502)

    logger.info(
        "roca-ops/sync: ficha de %s actualizada desde OPS (%d campos)",
        phone,
        len(ficha),
    )
    return JSONResponse({"ok": True, "sincronizado": True})
