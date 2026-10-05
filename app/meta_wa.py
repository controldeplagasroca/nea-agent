"""Envío de plantillas de WhatsApp directo por la API de Meta (Cloud API).

Solo para lo que ocurre FUERA de la ventana de 24 h del cliente (recordatorios de
visita), donde el CRM no puede mandar texto libre. Todo lo demás sigue pasando por
Vocero. El número es el mismo que atiende Nea, así que la respuesta del cliente
(«Confirmo mi visita», «Necesito cambiarla») entra por el flujo de siempre.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("nea.meta_wa")


class MetaError(Exception):
    """Meta rechazó el envío o no se pudo hablar con ella."""


class MetaWhatsApp:
    def __init__(
        self,
        *,
        token: str,
        phone_number_id: str,
        api_version: str = "v21.0",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token = token
        self._url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        self._client = client or httpx.AsyncClient(timeout=20.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def enviar_plantilla(
        self, a: str, plantilla: str, parametros: list[str], idioma: str = "es_MX"
    ) -> str:
        """Manda una plantilla con parámetros de cuerpo; regresa el id del mensaje."""
        cuerpo: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": a,
            "type": "template",
            "template": {
                "name": plantilla,
                "language": {"code": idioma},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": p} for p in parametros],
                    }
                ],
            },
        }
        try:
            resp = await self._client.post(
                self._url, json=cuerpo, headers={"Authorization": f"Bearer {self._token}"}
            )
        except httpx.HTTPError as exc:
            raise MetaError(f"sin respuesta de Meta: {type(exc).__name__}") from exc
        if resp.status_code != 200:
            # El cuerpo de error de Meta no lleva el token; el código y el mensaje sí ayudan.
            try:
                error = resp.json().get("error", {})
            except ValueError:
                error = {}
            raise MetaError(
                f"Meta devolvió {resp.status_code} (código {error.get('code')}): "
                f"{str(error.get('message', ''))[:200]}"
            )
        mensajes = resp.json().get("messages") or [{}]
        return str(mensajes[0].get("id", ""))
