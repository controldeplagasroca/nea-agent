"""Regla del negocio sobre el horario:

- Si el CLIENTE propone su día u hora, no se agenda ni se le contradice: se
  manda a verificar con el dueño.
- Si no propone ninguno, Nea ofrece los suyos: 24 h de anticipación, dentro del
  horario laboral; si ese momento cae fuera de horario, el siguiente inmediato.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from zoneinfo import ZoneInfo

from app.gcal import GoogleCalendarClient
from app.state import OfferedSlot
from tests.conftest import CRM_CONV_ID, IDENTITY, FakeCalendar, make_ctx, make_settings
from tests.test_gcal import calendar, mock_freebusy, sa_info  # noqa: F401
from app.plagas.caso import Caso
from app.plagas.herramientas import RuntimeDePlagas

TZ = ZoneInfo("America/Mexico_City")
MIE_10 = datetime(2026, 8, 5, 16, 0, tzinfo=timezone.utc)  # miércoles 10:00 CDMX
OFERTA = {"startUtc": "2026-08-05T16:00:00Z", "endUtc": "2026-08-05T17:30:00Z",
          "dayLabel": "el miércoles 5 de agosto", "time": "10:00", "label": "mié 5 ago, 10:00"}


async def _rt(mensajes: list[str], calendario: bool = False) -> tuple[RuntimeDePlagas, Any]:
    """Por defecto SIN calendario propio (agenda del CRM): ahí el horario que
    propone el cliente se manda a verificar con el dueño. Con calendario propio se
    consulta la disponibilidad (tests/test_confirmacion_inmediata.py)."""
    ctx = make_ctx(
        make_settings(vertical="plagas", owner_wa_id="525529161746"),
        calendar=FakeCalendar() if calendario else None,
    )
    conv = await ctx.store.get_or_create_conversation(IDENTITY)
    caso = Caso(plaga="cucaracha_alemana", turno=1)
    caso.cotizacion = {"precio": 1200.0, "linea": "$1,200 MXN por visita", "bloque": "", "turno": 0}
    caso.cobertura = {}
    rt = RuntimeDePlagas(ctx, conv, CRM_CONV_ID, caso=caso, mensajes_lead=mensajes)
    return rt, ctx


# --------------------------------------------- el cliente propone su horario ---


@pytest.mark.parametrize("texto", [
    "mejor el sábado a las 11",
    "¿puede ser mañana?",
    "el jueves en la tarde",
    "quiero que vengan a las 4:30 pm",
    "el 12 de octubre",
])
async def test_si_el_cliente_propone_horario_se_pasa_al_dueno(texto):
    rt, ctx = await _rt([texto])
    res = await rt._propose_slots({})
    assert res["estado"] == "horario_propuesto_en_verificacion"
    assert rt.handoff_reason == "cliente"
    assert "Se lo paso" in rt.texto_garantizado
    assert "propio horario" in rt.caso.escalado


@pytest.mark.parametrize("texto", [
    "sí, agéndame",
    "va, quiero la visita",
    "por la mañana mejor",       # franja, no un día ni una hora concreta
    "tengo 3 colchones",
])
async def test_si_no_propone_nada_nea_ofrece_los_suyos(texto):
    rt, ctx = await _rt([texto], calendario=True)
    ctx.calendar.availability_queue.append([OFERTA])
    res = await rt._propose_slots({})
    assert res.get("ok") is True and rt.handoff_reason is None
    assert ctx.calendar.availability_calls  # consultó el calendario


async def test_elegir_una_hora_ya_ofrecida_no_cuenta_como_proponer():
    rt, ctx = await _rt(["el de las 10:00 am"])
    await ctx.store.replace_offered_slots(
        rt._conv.id,
        [OfferedSlot(conversation_id=rt._conv.id, start_utc=MIE_10, end_utc=None, label="10:00")],
    )
    assert await rt._propone_su_horario({}) is False


async def test_pedir_otra_hora_distinta_a_las_ofrecidas_si_cuenta():
    rt, ctx = await _rt(["mejor a las 4 pm"])
    await ctx.store.replace_offered_slots(
        rt._conv.id,
        [OfferedSlot(conversation_id=rt._conv.id, start_utc=MIE_10, end_utc=None, label="10:00")],
    )
    assert await rt._propone_su_horario({}) is True


async def test_hora_no_ofrecida_al_agendar_se_pasa_al_dueno():
    rt, ctx = await _rt(["listo, a las 4 pm"])
    await ctx.store.replace_offered_slots(
        rt._conv.id,
        [OfferedSlot(conversation_id=rt._conv.id, start_utc=MIE_10, end_utc=None, label="10:00")],
    )
    await ctx.store.add_message(rt._conv.id, "user", "listo, a las 4 pm")
    elegido, error = await rt._resolve_offered({"start_utc": "2026-08-05T16:00:00Z"}, "book_session")
    assert elegido is None
    assert error["estado"] == "horario_propuesto_en_verificacion"
    assert rt.handoff_reason == "cliente"


# ------------------------------- Nea ofrece: 24 h, horario laboral, siguiente ---


def _cal(sa_info, ahora):  # noqa: F811
    c = GoogleCalendarClient(sa_info, "cal-test@group.calendar.google.com",
                             "America/Mexico_City", lead_hours=24.0, now_fn=lambda: ahora)

    async def _bearer() -> str:
        return "t"

    c._bearer = _bearer  # type: ignore[method-assign]
    return c


async def _primera(sa_info, ahora, respx_mock):  # noqa: F811
    mock_freebusy(respx_mock)
    slots = await _cal(sa_info, ahora).get_availability("alemana", limit=3, per_day=3, days=3)
    return datetime.fromisoformat(slots[0]["startUtc"].replace("Z", "+00:00")).astimezone(TZ)


async def test_en_horario_laboral_ofrece_desde_24_horas_despues(sa_info, respx_mock):  # noqa: F811
    lunes_11 = datetime(2026, 8, 3, 11, 0, tzinfo=TZ)
    primera = await _primera(sa_info, lunes_11, respx_mock)
    assert primera == datetime(2026, 8, 4, 11, 0, tzinfo=TZ)  # martes 11:00


async def test_fuera_de_horario_ofrece_el_siguiente_inmediato(sa_info, respx_mock):  # noqa: F811
    # Sábado 16:00 (ya cerró) + 24 h = domingo 16:00 (cerrado): el siguiente
    # horario laboral es el lunes a las 09:00.
    sabado_16 = datetime(2026, 8, 8, 16, 0, tzinfo=TZ)
    primera = await _primera(sa_info, sabado_16, respx_mock)
    assert primera == datetime(2026, 8, 10, 9, 0, tzinfo=TZ)


async def test_de_noche_ofrece_la_manana_siguiente_a_las_24h_o_despues(sa_info, respx_mock):  # noqa: F811
    # Lunes 20:00 + 24 h = martes 20:00 (cerrado): el siguiente es el miércoles 09:00.
    lunes_20 = datetime(2026, 8, 3, 20, 0, tzinfo=TZ)
    primera = await _primera(sa_info, lunes_20, respx_mock)
    assert primera == datetime(2026, 8, 5, 9, 0, tzinfo=TZ)


async def test_en_zona_de_un_solo_dia_pedir_otro_dia_lo_contesta_la_regla_de_zona():
    """Toluca/Lerma solo van los miércoles: pedir el lunes no lo verifica el
    dueño, se le explica la regla (ver test_plagas_turno)."""
    rt, ctx = await _rt(["y el lunes?"])
    rt.caso.cobertura = {"dia_restringido": 2, "dia_nombre": "miércoles"}
    res = await rt._propose_slots({"fecha": "2026-08-03"})  # un lunes
    assert res["error"] == "dia_no_disponible_en_su_zona"
    assert rt.handoff_reason is None
