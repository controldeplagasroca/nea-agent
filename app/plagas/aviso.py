"""Aviso al dueño por WhatsApp cuando Nea le pasa una conversación (opcional).

Lo que el dueño contó de su bot anterior (audio del 1 de octubre): «le pedí que
me mande autorización y nomás no la manda; le responde al cliente "nosotros te
avisamos", pero a mí nunca me llega un mensaje». En este fork el pase al dueño
SIEMPRE queda en el CRM (la conversación sale de la IA y aparece en la bandeja
con su motivo y la ficha llena). Esto añade, si se configura `AVISO_DUENO_WA`,
un mensaje a su propio WhatsApp con el resumen.

Va por el CRM, como todo lo que Nea envía, y por eso tiene las reglas de
WhatsApp:

- El dueño debe haberle escrito al número del negocio en las últimas 24 h (la
  ventana de conversación). Fuera de la ventana el aviso no sale y solo queda
  la bandeja del CRM.
- En su conversación la IA debe estar encendida (si no, el CRM no deja
  escribir al bot). Nea no le contesta al dueño como a un lead: sus mensajes
  solo sirven para mantener abierta la ventana (ver el gate en app/turn.py).

Es best-effort: un aviso que no sale jamás afecta el turno del lead.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import canonical_identity
from app.plagas import catalogo
from app.plagas.caso import Caso

logger = logging.getLogger("nea.plagas")

MOTIVOS = {
    "cliente": "Pidió hablar con una persona, o ya es cliente",
    "modelo": "Necesita que lo veas tú",
    "hostilidad": "Conversación hostil: se cerró con respeto",
}


def texto_del_aviso(caso: Caso, motivo: str, nombre: str, identidad: str) -> str:
    """El resumen que recibe el dueño. Solo datos del expediente: nada inventado."""
    telefono = identidad if identidad.isdigit() else ""
    quien = " · ".join(p for p in (nombre.strip(), telefono) if p) or "un contacto"
    lineas = ["🔔 *Nea te pasó una conversación*", f"👤 {quien}"]
    if caso.cita:
        lineas.append(
            f"🗓️ Pide visita: {caso.cita.get('label')} — pendiente de que la confirmes"
        )
    else:
        lineas.append(f"📌 {caso.escalado or MOTIVOS.get(motivo, MOTIVOS['modelo'])}")
    if caso.plaga:
        info = catalogo.PLAGAS[caso.plaga]
        lineas.append(f"{info.get('emoji', '🐛')} {info['nombre']}")
    elif caso.candidata and caso.candidata not in ("otra", "no_se_sabe"):
        lineas.append(f"🐛 Plaga sin confirmar: {caso.candidata}")
    if caso.cobertura.get("zona") or caso.cobertura.get("cp"):
        zona = " ".join(
            str(p) for p in (caso.cobertura.get("zona"),
                             f"CP {caso.cobertura['cp']}" if caso.cobertura.get("cp") else "") if p
        )
        lineas.append(f"🗺️ {zona}")
    if caso.variables:
        lineas.append("🏠 " + ", ".join(f"{k}: {v}" for k, v in caso.variables.items()))
    if caso.cotizacion:
        lineas.append(f"💵 {caso.cotizacion.get('linea')}")
    if any(caso.direccion.values()):
        lineas.append(f"📍 {caso.direccion_texto()}")
    lineas.append(
        "Contéstale desde la bandeja de Vocero: en esa conversación Nea ya no escribe."
    )
    return "\n".join(lineas)


async def avisar_al_dueno(
    ctx: Any,
    *,
    identidad_lead: str,
    context: dict[str, Any] | None,
    caso: Caso,
    motivo: str,
) -> bool:
    """Manda el aviso si hay a quién y se puede. True = salió."""
    destino = ctx.settings.aviso_dueno_identity
    if not destino or canonical_identity(identidad_lead) == destino:
        return False
    if caso.cita and caso.cita.get("folio"):
        # Ya se le mandó la solicitud con folio («sí N» / «no N»): no duplicar.
        return False
    nombre = str(((context or {}).get("contact") or {}).get("name") or "")
    texto = texto_del_aviso(caso, motivo, nombre, canonical_identity(identidad_lead))
    if await _enviar_al_dueno(ctx, destino, texto):
        logger.info("aviso al dueño enviado (motivo=%s)", motivo)
        return True
    return False


async def _enviar_al_dueno(ctx: Any, destino: str, texto: str) -> bool:
    """Escribe `texto` en la conversación del dueño. Best-effort: nunca lanza."""
    try:
        del_dueno = await ctx.crm.get_context(destino)
        info = (del_dueno or {}).get("conversation") or {}
        if not info.get("id"):
            logger.warning(
                "aviso al dueño: el CRM no tiene conversación con AVISO_DUENO_WA — "
                "que le escriba una vez al número del negocio"
            )
            return False
        if not info.get("windowOpen", False):
            logger.warning(
                "aviso al dueño: su ventana de 24 h está cerrada — el pase queda "
                "solo en la bandeja del CRM"
            )
            return False
        if not info.get("aiEnabled", False):
            logger.warning(
                "aviso al dueño: en su conversación la IA está en pausa y el CRM "
                "no deja escribir al bot — reactívala en la bandeja"
            )
            return False
        await ctx.crm.send_message(str(info["id"]), texto)
    except Exception as exc:  # best-effort: el turno del lead ya terminó bien
        logger.warning("aviso al dueño: no salió (%s)", exc)
        return False
    return True


# Cada cuánto, como mucho, se le repite al dueño que Nea sigue callada con el
# MISMO cliente (si el cliente escribe cinco veces, un solo aviso).
PARO_REPETIR_MINUTOS = 30


async def avisar_paro(
    ctx: Any, *, identidad_lead: str, nombre: str = "", que_paso: str, ultimo_mensaje: str = ""
) -> bool:
    """Le avisa al dueño que Nea NO está atendiendo a un cliente.

    Distinto de `avisar_al_dueno`: aquello es un pase a propósito (visita,
    cotización a mano). Esto es cuando Nea se detiene sin que nadie lo decida:
    el modelo falló, el turno reventó, o la IA quedó apagada y el cliente sigue
    escribiendo. Sin este aviso el cliente espera en silencio y nadie se entera.
    """
    destino = ctx.settings.aviso_dueno_identity or ctx.settings.owner_identity
    cliente = canonical_identity(identidad_lead)
    if not destino or cliente == destino:
        return False
    ahora = datetime.now(timezone.utc)
    previos = ctx.paros_avisados
    ultimo = previos.get(cliente)
    if ultimo is not None and ahora - ultimo < timedelta(minutes=PARO_REPETIR_MINUTOS):
        return False
    quien = " · ".join(p for p in (nombre.strip(), cliente if cliente.isdigit() else "") if p) or "un cliente"
    lineas = ["⚠️ *Nea se detuvo con un cliente*", f"👤 {quien}", f"❓ {que_paso}"]
    if ultimo_mensaje.strip():
        lineas.append(f"💬 Último mensaje: «{' '.join(ultimo_mensaje.split())[:160]}»")
    lineas.append("Contéstale tú desde la bandeja de Vocero: mientras la IA siga apagada, Nea no escribe.")
    if not await _enviar_al_dueno(ctx, destino, "\n".join(lineas)):
        return False
    previos[cliente] = ahora
    logger.info("aviso de paro al dueño enviado (%s)", que_paso)
    return True
