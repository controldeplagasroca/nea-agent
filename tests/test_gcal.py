"""GoogleCalendarClient: horario/duración por servicio, aviso mínimo, filtro
de ocupados vía freeBusy, y booking/reschedule contra la API real (mockeada).

La cuenta de servicio se firma con una llave RSA DESCARTABLE generada en la
propia prueba (nunca se usa para autenticar contra Google de verdad) — y
`_bearer` se reemplaza por un token fijo, porque lo que se prueba aquí es la
lógica de agenda, no el flujo de OAuth de google-auth.
"""
from __future__ import annotations

import json
from datetime import datetime, time, timedelta, timezone
from typing import Any

import httpx
import pytest
from zoneinfo import ZoneInfo

from app.gcal import (
    BUSINESS_HOURS,
    CalendarError,
    CalendarSlotTaken,
    GoogleCalendarClient,
)

CAL_ID = "cal-test@group.calendar.google.com"
TZ = ZoneInfo("America/Mexico_City")
# Lunes 3 de agosto 2026, 09:00 hora local — exactamente al abrir.
NOW = datetime(2026, 8, 3, 9, 0, tzinfo=TZ)
API_BASE = "https://www.googleapis.com/calendar/v3"


def _fake_sa_info() -> dict[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "test-key-id",
        "private_key": pem,
        "client_email": "nea-bot@test-project.iam.gserviceaccount.com",
        "client_id": "123456789",
        "token_uri": "https://oauth2.googleapis.com/token",
    }


@pytest.fixture(scope="module")
def sa_info() -> dict[str, str]:
    return _fake_sa_info()


@pytest.fixture
def calendar(sa_info: dict[str, str]) -> GoogleCalendarClient:
    client = GoogleCalendarClient(
        sa_info, CAL_ID, "America/Mexico_City", lead_hours=24.0, now_fn=lambda: NOW
    )

    async def _fake_bearer() -> str:
        return "test-token"

    client._bearer = _fake_bearer  # type: ignore[method-assign]  # no se prueba OAuth aquí
    return client


def mock_freebusy(respx_mock: Any, busy: list[dict[str, str]] | None = None) -> Any:
    return respx_mock.post(f"{API_BASE}/freeBusy").mock(
        return_value=httpx.Response(200, json={"calendars": {CAL_ID: {"busy": busy or []}}})
    )


async def test_get_availability_respeta_horario_y_aviso_minimo(calendar, respx_mock):
    mock_freebusy(respx_mock)
    slots = await calendar.get_availability("alemana", limit=50, per_day=10, days=3)
    assert slots
    earliest_allowed = NOW + timedelta(hours=24)
    for s in slots:
        start = datetime.fromisoformat(s["startUtc"].replace("Z", "+00:00")).astimezone(TZ)
        end = datetime.fromisoformat(s["endUtc"].replace("Z", "+00:00")).astimezone(TZ)
        assert start >= earliest_allowed
        open_t, close_t = BUSINESS_HOURS[start.weekday()]
        assert open_t <= start.time()
        assert end.time() <= close_t


async def test_get_availability_reparte_por_dia_y_respeta_limit(calendar, respx_mock):
    mock_freebusy(respx_mock)
    slots = await calendar.get_availability("alemana", limit=5, per_day=2, days=3)
    assert len(slots) <= 5
    por_dia: dict[str, int] = {}
    for s in slots:
        dia = s["startUtc"][:10]
        por_dia[dia] = por_dia.get(dia, 0) + 1
    assert all(c <= 2 for c in por_dia.values())
    assert len(por_dia) <= 3


async def test_get_availability_hormiga_usa_ventanas_propias(calendar, respx_mock):
    mock_freebusy(respx_mock)
    slots = await calendar.get_availability("hormiga", limit=20, per_day=10, days=2)
    assert slots
    for s in slots:
        t = datetime.fromisoformat(s["startUtc"].replace("Z", "+00:00")).astimezone(TZ).time()
        en_manana = time(9, 0) <= t < time(11, 30)
        en_tarde = time(16, 0) <= t < time(18, 30)
        assert en_manana or en_tarde, f"{t} fuera de las ventanas de hormiga"


async def test_get_availability_servicio_desconocido_lanza_error(calendar):
    with pytest.raises(CalendarError):
        await calendar.get_availability("termita")


async def test_get_availability_filtra_ocupados(calendar, respx_mock):
    # Ocupa exactamente el primer candidato del día más próximo (martes
    # 4 ago, 09:00-10:30 local = 15:00-16:30 UTC, sin horario de verano en
    # America/Mexico_City). El siguiente candidato libre por rejilla de 30
    # min que ya no encima es 10:30.
    mock_freebusy(
        respx_mock,
        busy=[{"start": "2026-08-04T15:00:00Z", "end": "2026-08-04T16:30:00Z"}],
    )
    slots = await calendar.get_availability("alemana", limit=3, per_day=3, days=1)
    assert slots
    assert slots[0]["time"] == "10:30"


async def test_create_booking_inserta_evento(calendar, respx_mock):
    mock_freebusy(respx_mock)
    insert = respx_mock.post(f"{API_BASE}/calendars/{CAL_ID}/events").mock(
        return_value=httpx.Response(200, json={"id": "evt_abc"})
    )
    start = NOW + timedelta(hours=25)
    end = start + timedelta(minutes=90)
    result = await calendar.create_booking(
        start, end, "Visita alemana — 5215500", "descripción", "alemana"
    )
    assert result == {"event_id": "evt_abc"}
    body = json.loads(insert.calls[0].request.content)
    assert body["summary"] == "Visita alemana — 5215500"
    assert body["start"]["timeZone"] == "America/Mexico_City"
    assert body["start"]["dateTime"] == start.isoformat()


async def test_create_booking_conflicto_dispara_alternativas_frescas(calendar, respx_mock):
    start = NOW + timedelta(hours=25)
    end = start + timedelta(minutes=90)
    ocupado = httpx.Response(
        200,
        json={
            "calendars": {
                CAL_ID: {
                    "busy": [
                        {
                            "start": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                            "end": end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                        }
                    ]
                }
            }
        },
    )
    libre = httpx.Response(200, json={"calendars": {CAL_ID: {"busy": []}}})
    respx_mock.post(f"{API_BASE}/freeBusy").mock(side_effect=[ocupado, libre])
    with pytest.raises(CalendarSlotTaken) as exc_info:
        await calendar.create_booking(start, end, "resumen", "desc", "alemana")
    assert exc_info.value.slots  # trae alternativas frescas de una segunda consulta


async def test_reschedule_booking_patch(calendar, respx_mock):
    mock_freebusy(respx_mock)
    patch = respx_mock.patch(f"{API_BASE}/calendars/{CAL_ID}/events/evt_1").mock(
        return_value=httpx.Response(200, json={})
    )
    old_start = NOW + timedelta(hours=25)
    old_end = old_start + timedelta(minutes=90)
    new_start = old_start + timedelta(days=1)
    new_end = new_start + timedelta(minutes=90)
    result = await calendar.reschedule_booking(
        "evt_1", old_start, old_end, new_start, new_end, "resumen", "desc", "alemana"
    )
    assert result == {}
    body = json.loads(patch.calls[0].request.content)
    assert body["start"]["dateTime"] == new_start.isoformat()
