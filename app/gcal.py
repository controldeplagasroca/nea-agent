"""Motor de agendamiento propio de Nea, contra Google Calendar.

vocero-crm deja el motor de agendamiento fuera de alcance A PROPÓSITO (ver su
README, sección "Fuera de alcance a propósito", e issue #8 de
kevinrivm/vocero-crm): el estado de qué huecos se ofrecieron pertenece a la
conversación, o sea al agente — no al CRM. Aquí vive esa implementación.

Autenticación con cuenta de servicio (sin login interactivo: Nea corre 24/7
sin intervención humana). Un solo calendario de Google, compartido con el
email de la cuenta de servicio, es la fuente de verdad de huecos y citas
reales.

Duración por tipo de servicio (aplicación + 30 min de traslado, YA incluidos)
y las ventanas restringidas de hormiga: reglas de negocio de ROCA confirmadas
por el dueño (Leopoldo, 2026-08-26) — no inventadas. Termita (madera seca) NO
tiene regla aquí a propósito: es "bajo consulta", así que nunca se agenda
sola, siempre handoff (ver app/tools.py).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account
from zoneinfo import ZoneInfo

logger = logging.getLogger("nea.gcal")

_SCOPES = ["https://www.googleapis.com/auth/calendar"]
_API_BASE = "https://www.googleapis.com/calendar/v3"

# Rejilla de inicios candidatos. Ninguna duración de servicio es múltiplo
# exacto de 30 (pulgas = 100 min), y no hace falta: la rejilla solo fija
# dónde puede EMPEZAR una cita, no cuánto dura.
SLOT_GRID_MINUTES = 30


@dataclass(frozen=True)
class ServiceRule:
    key: str
    label: str
    duration_minutes: int  # aplicación + 30 min de traslado, ya sumados
    windows: tuple[tuple[time, time], ...] | None = None  # None = horario general


# Duración total de bloqueo por servicio. Roedores usa 1.5h fija como punto de
# partida (varía con el tamaño del inmueble/número de trampas — precio, no
# calendario — se puede afinar más adelante si da problemas).
SERVICE_RULES: dict[str, ServiceRule] = {
    "alemana": ServiceRule("alemana", "cucaracha alemana", 90),
    "americana": ServiceRule("americana", "cucaracha americana", 90),
    "chinches": ServiceRule("chinches", "chinches de cama", 150),
    "alacran_arana": ServiceRule("alacran_arana", "alacrán/araña", 150),
    # Ventanas agendables por mayor actividad de la hormiga — sustituyen al
    # horario general del negocio para este servicio, no lo intersectan.
    "hormiga": ServiceRule(
        "hormiga", "hormiga común", 120,
        windows=((time(9, 0), time(11, 30)), (time(16, 0), time(18, 30))),
    ),
    "pulgas": ServiceRule("pulgas", "pulgas", 100),
    "roedores": ServiceRule("roedores", "roedores", 120),
    # La tijerilla no estaba en las reglas confirmadas por el dueño: se bloquea
    # como la alemana (90 min) hasta que diga otra cosa.
    "tijerilla": ServiceRule("tijerilla", "tijerilla", 90),
}

# Clave del catálogo de plagas (app/plagas/catalogo.py) -> clave de SERVICE_RULES.
# Lo que no está aquí (termitas, moscas y mosquitos…) no se agenda solo: es
# «bajo consulta» y va siempre al dueño.
SERVICIO_DE_PLAGA: dict[str, str] = {
    "cucaracha_alemana": "alemana",
    "cucaracha_americana": "americana",
    "hormiga": "hormiga",
    "roedores": "roedores",
    "alacran": "alacran_arana",
    "arana": "alacran_arana",
    "tijerilla": "tijerilla",
    "chinches": "chinches",
    "pulgas": "pulgas",
}

# Horario general del negocio (lunes=0 … sábado=5). Domingo (6) ausente = cerrado.
BUSINESS_HOURS: dict[int, tuple[time, time]] = {
    0: (time(9, 0), time(18, 0)),
    1: (time(9, 0), time(18, 0)),
    2: (time(9, 0), time(18, 0)),
    3: (time(9, 0), time(18, 0)),
    4: (time(9, 0), time(18, 0)),
    5: (time(9, 0), time(14, 0)),
}

_ES_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_ES_DIAS_CORTOS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
_ES_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


class CalendarError(Exception):
    """Fallo genérico hablando con Google Calendar, o agenda sin configurar."""


class CalendarSlotTaken(CalendarError):
    """El slot se ocupó entre oferta y confirmación; trae alternativas frescas."""

    def __init__(self, slots: list[dict[str, Any]]) -> None:
        super().__init__("slot_taken")
        self.slots = slots


def _day_label_es(d: date, today: date) -> str:
    nombre = f"{_ES_DIAS[d.weekday()]} {d.day} de {_ES_MESES[d.month - 1]}"
    if d == today:
        return f"hoy {nombre}"
    if d == today + timedelta(days=1):
        return f"mañana {nombre}"
    return f"el {nombre}"


def _short_label_es(d: date, hhmm: str) -> str:
    return f"{_ES_DIAS_CORTOS[d.weekday()]} {d.day} {_ES_MESES[d.month - 1][:3]}, {hhmm}"


def _windows_for(rule: ServiceRule, weekday: int) -> list[tuple[time, time]]:
    """Ventanas agendables ESE día para este servicio; vacío = cerrado.

    Las ventanas propias de un servicio (hormiga) SUSTITUYEN el horario
    general en vez de intersectarlo: son las horas correctas por actividad de
    la plaga, no un subconjunto del horario de atención general.
    """
    if rule.windows is not None:
        return list(rule.windows) if weekday in BUSINESS_HOURS else []
    open_close = BUSINESS_HOURS.get(weekday)
    return [open_close] if open_close else []


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


class NullCalendarClient:
    """Agenda sin configurar (faltan credenciales/calendar id).

    Degrada sin tumbar el turno (Constitución: "degradación silenciosa") — el
    LLM recibe un error de herramienta y puede ofrecer handoff en vez de
    romper la conversación.
    """

    async def get_availability(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        raise CalendarError("agenda no configurada (falta GOOGLE_SERVICE_ACCOUNT_JSON/GOOGLE_CALENDAR_ID)")

    async def get_day(self, *args: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], str]:
        raise CalendarError("agenda no configurada (falta GOOGLE_SERVICE_ACCOUNT_JSON/GOOGLE_CALENDAR_ID)")

    async def create_booking(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise CalendarError("agenda no configurada (falta GOOGLE_SERVICE_ACCOUNT_JSON/GOOGLE_CALENDAR_ID)")

    async def reschedule_booking(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise CalendarError("agenda no configurada (falta GOOGLE_SERVICE_ACCOUNT_JSON/GOOGLE_CALENDAR_ID)")

    async def hay_cupo(self, *args: Any, **kwargs: Any) -> bool:
        raise CalendarError("agenda no configurada (falta GOOGLE_SERVICE_ACCOUNT_JSON/GOOGLE_CALENDAR_ID)")

    async def cancel_booking(self, *args: Any, **kwargs: Any) -> None:
        raise CalendarError("agenda no configurada (falta GOOGLE_SERVICE_ACCOUNT_JSON/GOOGLE_CALENDAR_ID)")

    async def aclose(self) -> None:
        return None


class GoogleCalendarClient:
    """Cliente REST directo (sin google-api-python-client, que es síncrono):
    google-auth solo para firmar/refrescar el token, httpx.AsyncClient para
    hablar con la API — consistente con el resto de Nea (httpx en todos lados)
    y sin bloquear el loop de eventos."""

    def __init__(
        self,
        service_account_info: dict[str, Any],
        calendar_id: str,
        timezone_name: str = "America/Mexico_City",
        lead_hours: float = 24.0,
        max_parallel: int = 1,
        client: httpx.AsyncClient | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._calendar_id = calendar_id
        self._tz = ZoneInfo(timezone_name)
        self._lead = timedelta(hours=lead_hours)
        # Cuántas visitas pueden coincidir en el MISMO horario (técnicos en
        # paralelo). Con 1, un solo evento ocupa el hueco, como antes.
        self._max_parallel = max(1, int(max_parallel))
        self._creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=_SCOPES
        )
        self._http = client or httpx.AsyncClient(base_url=_API_BASE, timeout=15.0)
        self._token_lock = asyncio.Lock()
        self._now = now_fn or (lambda: datetime.now(self._tz))

    async def _bearer(self) -> str:
        async with self._token_lock:
            if not self._creds.valid:
                await asyncio.to_thread(self._creds.refresh, GoogleAuthRequest())
            return str(self._creds.token)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {await self._bearer()}"}
        try:
            return await self._http.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise CalendarError(f"error de red hacia Google Calendar: {exc}") from exc

    # --------------------------------------------------------------- ocupado ---
    #
    # Se leen los EVENTOS (no freeBusy): freeBusy fusiona los bloques que se
    # traslapan y entonces no se puede saber cuántas visitas coinciden, que es
    # justo lo que importa con varios técnicos.

    async def _busy_intervals(
        self, time_min: datetime, time_max: datetime
    ) -> list[tuple[datetime, datetime]]:
        """Un intervalo por evento. Un evento de día completo (feriado, cierre)
        ocupa TODA la capacidad ese día."""
        out: list[tuple[datetime, datetime]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {
                "timeMin": time_min.astimezone(timezone.utc).isoformat(),
                "timeMax": time_max.astimezone(timezone.utc).isoformat(),
                "singleEvents": "true",
                "maxResults": 2500,
            }
            if page_token:
                params["pageToken"] = page_token
            resp = await self._request(
                "GET", f"/calendars/{self._calendar_id}/events", params=params
            )
            if resp.status_code != 200:
                raise CalendarError(f"events.list devolvió {resp.status_code}")
            data = resp.json()
            for ev in data.get("items") or []:
                if ev.get("status") == "cancelled" or ev.get("transparency") == "transparent":
                    continue  # cancelado, o marcado «disponible»: no ocupa
                ini, fin = ev.get("start") or {}, ev.get("end") or {}
                if ini.get("dateTime") and fin.get("dateTime"):
                    out.append((
                        datetime.fromisoformat(str(ini["dateTime"]).replace("Z", "+00:00")),
                        datetime.fromisoformat(str(fin["dateTime"]).replace("Z", "+00:00")),
                    ))
                elif ini.get("date") and fin.get("date"):
                    dia_ini = datetime.combine(date.fromisoformat(ini["date"]), time(0, 0), tzinfo=self._tz)
                    dia_fin = datetime.combine(date.fromisoformat(fin["date"]), time(0, 0), tzinfo=self._tz)
                    out.extend([(dia_ini, dia_fin)] * self._max_parallel)
            page_token = data.get("nextPageToken")
            if not page_token:
                return out

    def _sin_cupo(
        self, start: datetime, end: datetime, busy: list[tuple[datetime, datetime]]
    ) -> bool:
        """¿En algún momento de [start, end) ya coinciden `max_parallel` visitas?"""
        cruzan = [
            (max(b_s, start), min(b_e, end))
            for b_s, b_e in busy
            if _overlaps(start, end, b_s, b_e)
        ]
        if len(cruzan) < self._max_parallel:
            return False
        # Barrido: el máximo de eventos simultáneos dentro de la ventana. Al
        # empatar el instante, primero se cierran los que terminan.
        puntos = sorted(
            [(a, 1) for a, _ in cruzan] + [(b, -1) for _, b in cruzan],
            key=lambda p: (p[0], p[1]),
        )
        activos = maximo = 0
        for _, delta in puntos:
            activos += delta
            maximo = max(maximo, activos)
        return maximo >= self._max_parallel

    async def _slot_busy(self, start: datetime, end: datetime) -> bool:
        busy = await self._busy_intervals(start, end)
        return self._sin_cupo(start, end, busy)

    def _candidate_starts(
        self, rule: ServiceRule, now_local: datetime, horizon_days: int
    ) -> list[datetime]:
        """Inicios candidatos (tz local) alineados a la rejilla, dentro de las
        ventanas agendables del servicio, respetando el aviso mínimo."""
        earliest = now_local + self._lead
        out: list[datetime] = []
        for offset in range(horizon_days):
            day = (now_local + timedelta(days=offset)).date()
            for win_start, win_end in _windows_for(rule, day.weekday()):
                cursor = datetime.combine(day, win_start, tzinfo=self._tz)
                close = datetime.combine(day, win_end, tzinfo=self._tz)
                step = timedelta(minutes=SLOT_GRID_MINUTES)
                duration = timedelta(minutes=rule.duration_minutes)
                while cursor + duration <= close:
                    if cursor >= earliest:
                        out.append(cursor)
                    cursor += step
        return out

    async def get_availability(
        self,
        service_key: str,
        limit: int = 12,
        per_day: int = 3,
        days: int = 5,
        horizon_days: int = 21,
    ) -> list[dict[str, Any]]:
        rule = SERVICE_RULES.get(service_key)
        if rule is None:
            raise CalendarError(f"servicio sin regla de agenda: {service_key!r}")
        now_local = self._now()
        candidates = self._candidate_starts(rule, now_local, horizon_days)
        if not candidates:
            return []
        duration = timedelta(minutes=rule.duration_minutes)
        busy = await self._busy_intervals(candidates[0], candidates[-1] + duration)
        today = now_local.date()
        by_day: dict[date, list[dict[str, Any]]] = {}
        for start in candidates:
            day = start.date()
            bucket = by_day.setdefault(day, [])
            if len(bucket) >= per_day:
                continue
            end = start + duration
            if self._sin_cupo(start, end, busy):
                continue
            hhmm = start.strftime("%H:%M")
            bucket.append(
                {
                    "startUtc": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "endUtc": end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "dayLabel": _day_label_es(day, today),
                    "time": hhmm,
                    "label": _short_label_es(day, hhmm),
                }
            )
        out: list[dict[str, Any]] = []
        for day in sorted(d for d, slots in by_day.items() if slots)[:days]:
            out.extend(by_day[day])
        return out[:limit]

    async def get_day(
        self, service_key: str, day: date
    ) -> tuple[list[dict[str, Any]], str]:
        """TODAS las horas libres de un día, y su estado.

        Estado: `available` (hay horas), `closed` (el negocio no abre ese día o
        el servicio no tiene ventana), `full` (abre pero no queda nada con el
        aviso mínimo) o `past` (ya pasó).
        """
        rule = SERVICE_RULES.get(service_key)
        if rule is None:
            raise CalendarError(f"servicio sin regla de agenda: {service_key!r}")
        now_local = self._now()
        if day < now_local.date():
            return [], "past"
        ventanas = _windows_for(rule, day.weekday())
        if not ventanas:
            return [], "closed"
        earliest = now_local + self._lead
        step = timedelta(minutes=SLOT_GRID_MINUTES)
        duration = timedelta(minutes=rule.duration_minutes)
        starts: list[datetime] = []
        for win_start, win_end in ventanas:
            cursor = datetime.combine(day, win_start, tzinfo=self._tz)
            close = datetime.combine(day, win_end, tzinfo=self._tz)
            while cursor + duration <= close:
                if cursor >= earliest:
                    starts.append(cursor)
                cursor += step
        if not starts:
            return [], "full"
        busy = await self._busy_intervals(starts[0], starts[-1] + duration)
        today = now_local.date()
        out: list[dict[str, Any]] = []
        for start in starts:
            end = start + duration
            if self._sin_cupo(start, end, busy):
                continue
            hhmm = start.strftime("%H:%M")
            out.append(
                {
                    "startUtc": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "endUtc": end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "dayLabel": _day_label_es(day, today),
                    "time": hhmm,
                    "label": _short_label_es(day, hhmm),
                }
            )
        return out, ("available" if out else "full")

    # -------------------------------------------------------------- booking ---

    async def create_booking(
        self,
        start_utc: datetime,
        end_utc: datetime,
        summary: str,
        description: str,
        service_key: str,
    ) -> dict[str, Any]:
        if await self._slot_busy(start_utc, end_utc):
            raise CalendarSlotTaken(await self.get_availability(service_key))
        resp = await self._request(
            "POST",
            f"/calendars/{self._calendar_id}/events",
            json=self._event_body(start_utc, end_utc, summary, description),
        )
        if resp.status_code not in (200, 201):
            raise CalendarError(f"events.insert devolvió {resp.status_code}")
        data = resp.json()
        return {"event_id": data["id"]}

    async def reschedule_booking(
        self,
        event_id: str,
        old_start: datetime,
        old_end: datetime,
        new_start: datetime,
        new_end: datetime,
        summary: str,
        description: str,
        service_key: str,
    ) -> dict[str, Any]:
        if await self._slot_busy(new_start, new_end):
            raise CalendarSlotTaken(await self.get_availability(service_key))
        resp = await self._request(
            "PATCH",
            f"/calendars/{self._calendar_id}/events/{event_id}",
            json=self._event_body(new_start, new_end, summary, description),
        )
        if resp.status_code != 200:
            raise CalendarError(f"events.patch devolvió {resp.status_code}")
        return {}

    async def hay_cupo(self, start: datetime, end: datetime) -> bool:
        """¿Cabe una visita en [start, end) sin pasar de las visitas en paralelo?

        No mira horario laboral ni aviso mínimo: lo usa el dueño, que puede sugerir
        un horario fuera de ellos. Solo respeta la capacidad real del calendario.
        """
        return not await self._slot_busy(start, end)

    async def cancel_booking(self, event_id: str) -> None:
        resp = await self._request(
            "DELETE", f"/calendars/{self._calendar_id}/events/{event_id}"
        )
        # 204 = borrado; 404/410 = ya no existía (idempotente, no es error del
        # lead ni del negocio — puede haberse borrado a mano en Google Calendar).
        if resp.status_code not in (204, 404, 410):
            raise CalendarError(f"events.delete devolvió {resp.status_code}")

    def _event_body(
        self, start: datetime, end: datetime, summary: str, description: str
    ) -> dict[str, Any]:
        tz_name = str(self._tz)
        return {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": tz_name},
            "end": {"dateTime": end.isoformat(), "timeZone": tz_name},
        }

    async def aclose(self) -> None:
        await self._http.aclose()
