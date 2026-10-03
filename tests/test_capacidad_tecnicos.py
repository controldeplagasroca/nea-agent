"""Tres técnicos, uno de colchón: hasta 2 visitas a la misma hora (BOOKING_MAX_PARALELO).

Se lee de los EVENTOS del calendario compartido (freeBusy fusiona los bloques
que se traslapan y no deja contar cuántas visitas coinciden).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from zoneinfo import ZoneInfo

from app.gcal import GoogleCalendarClient
from app.plagas.caso import Caso
from app.plagas.herramientas import RuntimeDePlagas
from app.state import OfferedSlot
from tests.conftest import CRM_CONV_ID, CRM_URL, IDENTITY, FakeCalendar, make_ctx, make_settings
from tests.test_gcal import API_BASE, CAL_ID, NOW, _eventos, sa_info  # noqa: F401
from app.config import Settings

TZ = ZoneInfo("America/Mexico_City")
MARTES = (NOW + timedelta(days=1)).date()  # martes 4 ago 2026


def _utc(h: int, m: int = 0) -> str:
    return datetime(MARTES.year, MARTES.month, MARTES.day, h, m, tzinfo=TZ).astimezone(
        ZoneInfo("UTC")
    ).isoformat().replace("+00:00", "Z")


def _ev(ini: tuple[int, int], fin: tuple[int, int]) -> dict[str, str]:
    return {"start": _utc(*ini), "end": _utc(*fin)}


def _cal(sa_info, paralelo: int):  # noqa: F811
    c = GoogleCalendarClient(sa_info, CAL_ID, "America/Mexico_City", lead_hours=24.0,
                             max_parallel=paralelo, now_fn=lambda: NOW)

    async def _bearer() -> str:
        return "t"

    c._bearer = _bearer  # type: ignore[method-assign]
    return c


def _mock(respx_mock, items: dict[str, Any]):
    respx_mock.get(f"{API_BASE}/calendars/{CAL_ID}/events").mock(
        return_value=httpx.Response(200, json=items)
    )


async def _horas(c, dia=MARTES) -> list[str]:
    slots, _ = await c.get_day("alemana", dia)
    return [s["time"] for s in slots]


async def test_con_una_visita_a_esa_hora_todavia_hay_cupo(sa_info, respx_mock):  # noqa: F811
    _mock(respx_mock, _eventos([_ev((9, 0), (10, 30))]))
    assert "09:00" in await _horas(_cal(sa_info, 2))


async def test_con_dos_visitas_a_la_misma_hora_ya_no_hay_cupo(sa_info, respx_mock):  # noqa: F811
    _mock(respx_mock, _eventos([_ev((9, 0), (10, 30)), _ev((9, 0), (10, 30))]))
    horas = await _horas(_cal(sa_info, 2))
    assert not {"09:00", "09:30", "10:00"} & set(horas)
    assert "10:30" in horas


async def test_el_traslape_parcial_cuenta_solo_si_coinciden_a_la_vez(sa_info, respx_mock):  # noqa: F811
    # Una de 09:00-10:30 y otra de 10:30-12:00 NO coinciden nunca: siempre queda 1 libre.
    _mock(respx_mock, _eventos([_ev((9, 0), (10, 30)), _ev((10, 30), (12, 0))]))
    horas = await _horas(_cal(sa_info, 2))
    assert "09:00" in horas and "10:30" in horas


async def test_dos_visitas_que_solo_se_cruzan_a_media_hora_bloquean_esa_ventana(sa_info, respx_mock):  # noqa: F811
    # 09:00-10:30 y 10:00-11:30 coinciden de 10:00 a 10:30. Una visita de 90 min
    # que cruce esa franja sería la tercera a la vez y no cabe; una que empiece
    # a las 10:30 solo cruza a una de las dos, y sí cabe.
    _mock(respx_mock, _eventos([_ev((9, 0), (10, 30)), _ev((10, 0), (11, 30))]))
    horas = await _horas(_cal(sa_info, 2))
    assert not {"09:00", "09:30", "10:00"} & set(horas)
    assert "10:30" in horas and "11:30" in horas


async def test_con_capacidad_1_una_sola_visita_ya_ocupa_el_horario(sa_info, respx_mock):  # noqa: F811
    _mock(respx_mock, _eventos([_ev((9, 0), (10, 30))]))
    assert "09:00" not in await _horas(_cal(sa_info, 1))


async def test_un_evento_de_dia_completo_cierra_el_dia(sa_info, respx_mock):  # noqa: F811
    feriado = {"status": "confirmed", "start": {"date": MARTES.isoformat()},
               "end": {"date": (MARTES + timedelta(days=1)).isoformat()}}
    _mock(respx_mock, {"items": [feriado]})
    slots, estado = await _cal(sa_info, 2).get_day("alemana", MARTES)
    assert slots == [] and estado == "full"


async def test_los_cancelados_y_los_marcados_disponible_no_ocupan(sa_info, respx_mock):  # noqa: F811
    base = _eventos([_ev((9, 0), (10, 30))])["items"][0]
    _mock(respx_mock, {"items": [
        {**base, "status": "cancelled"},
        {**base, "transparency": "transparent"},
    ]})
    assert "09:00" in await _horas(_cal(sa_info, 1))


def test_la_capacidad_por_defecto_es_2():
    assert Settings(_env_file=None).booking_max_paralelo == 2


# ------------------------------------------------ aviso de zona al aprobar ---


async def _rt_toluca():
    ctx = make_ctx(make_settings(vertical="plagas", owner_wa_id="525529161746"), calendar=FakeCalendar())
    conv = await ctx.store.get_or_create_conversation(IDENTITY)
    caso = Caso(plaga="cucaracha_alemana", turno=1)
    caso.cotizacion = {"precio": 1200.0, "linea": "x", "bloque": "", "turno": 0}
    caso.cobertura = {"zona": "Toluca", "dia_restringido": 2, "dia_nombre": "miércoles"}
    caso.cita = {"label": "x"}
    return RuntimeDePlagas(ctx, conv, CRM_CONV_ID, caso=caso, mensajes_lead=[]), ctx


async def test_una_visita_en_toluca_lleva_la_nota_para_el_dueno():
    import respx

    rt, ctx = await _rt_toluca()
    with respx.mock:
        respx.get(f"{CRM_URL}/api/bot/context").mock(return_value=httpx.Response(
            200, json={"conversation": {"id": "dueno", "windowOpen": True}}))
        envio = respx.post(f"{CRM_URL}/api/bot/messages").mock(return_value=httpx.Response(200, json={}))
        slot = OfferedSlot(conversation_id=rt._conv.id, start_utc=NOW + timedelta(days=2),
                           end_utc=None, label="miércoles")
        await rt._registrar_pendiente(slot)
    pend = (await ctx.store.list_pending_bookings_pendientes())[0]
    assert "Toluca" in pend.nota and "técnico" in pend.nota
    assert "Toluca" in envio.calls.last.request.content.decode()


async def test_una_visita_fuera_de_esas_zonas_no_lleva_nota():
    rt, ctx = await _rt_toluca()
    rt.caso.cobertura = {}
    assert rt._nota_de_zona() == ""
