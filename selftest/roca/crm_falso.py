"""Un Vocero CRM de mentira, en memoria, para la autoprueba.

Implementa lo que `app/turn.py` y `app/tools.py` usan del cliente del CRM
(`app/crm.py`) y nada más. No hay red, no hay WhatsApp y no hay base: lo que
Nea «envía» queda en `enviados`, la ficha en `ficha` y los pases a humano en
`handoffs`, para que las comprobaciones miren lo mismo que vería el dueño.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.crm import AgendaUnavailable, CrmConflict, SlotNotOffered, canonical_handoff_reason
from app.prompt import DIAS, MESES

TZ = ZoneInfo("America/Mexico_City")
HORAS_REPARTO = (time(9, 0), time(12, 0), time(16, 0))
HORAS_DEL_DIA = (time(9, 0), time(11, 0), time(13, 0), time(16, 0))
HORIZONTE_DIAS = 21
CONV_DUENO = "cv_dueno"


class CrmFalso:
    supports_agenda_v2 = False
    supports_coordination = False

    def __init__(
        self,
        *,
        identidad: str,
        perfil: dict[str, Any],
        nombre: str = "",
        etapa: str = "Nuevo",
        agenda: bool = True,
        cita_previa: dict[str, Any] | None = None,
        ahora: datetime | None = None,
        dueno: str = "",
        ventana_dueno: bool = True,
    ) -> None:
        # El WhatsApp del dueño (AVISO_DUENO_WA) y lo que le llegó ahí.
        self.dueno = dueno
        self.ventana_dueno = ventana_dueno
        self.avisos: list[str] = []
        self.identidad = identidad
        self.perfil = perfil
        self.nombre = nombre
        self.etapa = etapa
        self.agenda = agenda
        self.cita = cita_previa
        self.ahora = ahora or datetime.now(timezone.utc)
        self.conv_id = f"cv_{identidad}"
        self.ai_enabled = True
        self.ficha: dict[str, Any] = {}
        self.enviados: list[str] = []
        self.handoffs: list[str] = []
        self.ofrecidos: set[str] = set()
        self.reservas: list[str] = []

    # ------------------------------------------------------------ lectura ---

    async def get_context(self, wa_identity: str) -> dict[str, Any] | None:
        if self.dueno and wa_identity == self.dueno:
            return {
                "contact": {"id": "ct_dueno", "name": "Dueño", "waIdentity": wa_identity},
                "conversation": {
                    "id": CONV_DUENO, "aiEnabled": True,
                    "windowOpen": self.ventana_dueno, "handoffAt": None,
                },
            }
        return {
            "contact": {
                "id": "ct_1", "name": self.nombre or None,
                "waIdentity": wa_identity, "phone": wa_identity,
                "ficha": dict(self.ficha),
            },
            "conversation": {
                "id": self.conv_id, "aiEnabled": self.ai_enabled,
                "windowOpen": True, "handoffAt": None,
            },
            "lead": {"id": "ld_1", "stageName": self.etapa},
            "adOrigen": None,
            "booking": {"next": self.cita, "timezone": TZ.key} if self.agenda else None,
        }

    async def get_profile(self) -> dict[str, Any] | None:
        return self.perfil

    # ----------------------------------------------------------- escritura ---

    async def send_message(self, conversation_id: str, text: str) -> dict[str, Any]:
        if conversation_id == CONV_DUENO:
            self.avisos.append(text)
            return {"messageId": f"msg_dueno_{len(self.avisos)}"}
        if not self.ai_enabled:
            raise CrmConflict("ai_paused")
        self.enviados.append(text)
        return {"messageId": f"msg_{len(self.enviados)}"}

    async def put_ficha(self, conversation_id: str, ficha: dict[str, Any]) -> dict[str, Any]:
        for k, v in ficha.items():
            if v is None:
                self.ficha.pop(k, None)
            elif isinstance(v, (str, int, float, bool)):
                self.ficha[k] = v
        return {"ficha": dict(self.ficha)}

    async def post_handoff(self, conversation_id: str, reason: str | None = None) -> None:
        self.handoffs.append(canonical_handoff_reason(reason))
        self.ai_enabled = False

    async def post_typing(self, conversation_id: str) -> None:
        return None

    async def post_reset(self, conversation_id: str) -> None:
        self.ficha.clear()
        self.ai_enabled = True

    # -------------------------------------------------------------- agenda ---

    async def sondear_agenda(self, timeout: float | None = None) -> bool | None:
        return self.agenda

    async def agenda_available(self) -> bool:
        return self.agenda

    def _slot(self, dia: date, hora: time) -> dict[str, Any]:
        inicio = datetime.combine(dia, hora, TZ)
        hoy = self.ahora.astimezone(TZ).date()
        prefijo = "hoy " if dia == hoy else "mañana " if dia == hoy + timedelta(days=1) else ""
        etiqueta = f"{prefijo}{DIAS[dia.weekday()]} {dia.day} de {MESES[dia.month - 1]}"
        return {
            "startUtc": inicio.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "endUtc": (inicio + timedelta(hours=1)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "label": f"{DIAS[dia.weekday()][:3]} {dia.day} {MESES[dia.month - 1][:3]}, {hora:%H:%M}",
            "dayLabel": etiqueta,
            "time": f"{hora:%H:%M}",
            "dayIso": dia.isoformat(),
        }

    async def consultar_huecos(
        self,
        conversation_id: str,
        date: str | None = None,
        limit: int = 12,
        per_day: int | None = None,
        days: int | None = None,
    ) -> dict[str, Any]:
        if not self.agenda:
            raise AgendaUnavailable("sin agenda")
        hoy = self.ahora.astimezone(TZ).date()
        horizonte = hoy + timedelta(days=HORIZONTE_DIAS)
        if date:
            from datetime import date as _date

            dia = _date.fromisoformat(date)
            query: dict[str, Any] = {"date": date, "horizonEnd": horizonte.isoformat()}
            if dia <= hoy:
                query["status"] = "past" if dia < hoy else "full"
                return {"slots": [], "query": query}
            if dia > horizonte:
                query["status"] = "beyond_horizon"
                return {"slots": [], "query": query}
            if dia.weekday() == 6:  # domingo: cerrado
                query["status"] = "closed"
                return {"slots": [], "query": query}
            slots = [self._slot(dia, h) for h in HORAS_DEL_DIA]
            query["status"] = "available"
            self.ofrecidos = {s["startUtc"] for s in slots}
            return {"slots": slots, "query": query}

        slots: list[dict[str, Any]] = []
        dia, vistos = hoy + timedelta(days=1), 0
        while vistos < (days or 5) and dia <= horizonte:
            if dia.weekday() != 6:
                slots += [self._slot(dia, h) for h in HORAS_REPARTO[: per_day or 3]]
                vistos += 1
            dia += timedelta(days=1)
        slots = slots[:limit]
        self.ofrecidos = {s["startUtc"] for s in slots}
        return {
            "slots": slots,
            "query": {
                "coveredUntil": (dia - timedelta(days=1)).isoformat(),
                "perDay": per_day or 3,
                "horizonEnd": horizonte.isoformat(),
            },
        }

    async def create_booking(self, conversation_id: str, start_utc: str) -> dict[str, Any]:
        if not self.agenda:
            raise AgendaUnavailable("sin agenda")
        if start_utc not in self.ofrecidos:
            raise SlotNotOffered({"slots": []})
        self.reservas.append(start_utc)
        self.cita = {"startUtc": start_utc, "label": start_utc}
        return {"bookingId": "bk_1", "label": start_utc, "meetingLink": None}

    async def reschedule_booking(self, conversation_id: str, start_utc: str) -> dict[str, Any]:
        if self.cita is None:
            raise CrmConflict("no_booking")
        self.cita = {"startUtc": start_utc, "label": start_utc}
        return {"label": start_utc}

    async def aclose(self) -> None:
        return None
