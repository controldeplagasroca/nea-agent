"""4 oct (conversación de Ethel): la visita ya no es una «solicitud que el dueño debe
autorizar»; con calendario propio es una CONFIRMACIÓN que se agenda al instante.

Reglas del dueño:
- El horario sale de la disponibilidad real: si está libre, queda agendada ya.
- El cliente no oye «solicitud», «autorizar» ni que «el técnico te confirma»: oye que
  quedó agendada y que cuando se designe técnico se le enviará un mensaje.
- Las zonas de un solo día (Toluca, Lerma) siguen pasando por aprobación.
- También: «niguna» (con errata) cuenta como ninguna; las arañas se preguntan dónde.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import httpx
import pytest
import respx

from app.gcal import CalendarError, CalendarSlotTaken
from app.plagas import catalogo, diagnostico
from app.plagas.caso import Caso, paso_actual
from app.plagas.fechas import fecha_pedida
from app.plagas.herramientas import RuntimeDePlagas, _dice_cero, bloque_de_tratamiento
from app.state import OfferedSlot
from tests.conftest import CRM_CONV_ID, CRM_URL, IDENTITY, FakeCalendar, make_ctx, make_settings

INICIO = datetime(2026, 10, 5, 16, 0, tzinfo=timezone.utc)  # lunes 10:00 CDMX
ETIQUETA = "mañana lunes 5 de octubre, 10:00"


async def _rt(zona_restringida: bool = False, calendar=None):
    ctx = make_ctx(
        make_settings(vertical="plagas", owner_wa_id="525529161746"),
        calendar=calendar or FakeCalendar(),
    )
    conv = await ctx.store.get_or_create_conversation(IDENTITY)
    caso = Caso(plaga="cucaracha_alemana", turno=3)
    caso.cotizacion = {"precio": 1100.0, "linea": "$1,100 MXN por visita (departamento)", "bloque": "", "turno": 1}
    caso.aceptada = True
    caso.direccion = {"calle": "Dr. Vértiz", "numero_exterior": "1386", "colonia": "Portales",
                      "alcaldia_municipio": "Benito Juárez", "referencia": "portón negro"}
    caso.cobertura = {"estado": "dentro_de_zona"}
    if zona_restringida:
        caso.cobertura = {"estado": "solo_dia_especifico", "zona": "Toluca",
                          "dia_restringido": 2, "dia_nombre": "miércoles"}
    rt = RuntimeDePlagas(ctx, conv, CRM_CONV_ID, caso=caso, mensajes_lead=[])
    return rt, ctx


def _slot(rt):
    return OfferedSlot(conversation_id=rt._conv.id, start_utc=INICIO, end_utc=None, label=ETIQUETA)


def _crm_falso():
    respx.get(f"{CRM_URL}/api/bot/context").mock(return_value=httpx.Response(
        200, json={"conversation": {"id": "dueno", "windowOpen": True, "aiEnabled": True}}))
    envio = respx.post(f"{CRM_URL}/api/bot/messages").mock(return_value=httpx.Response(200, json={}))
    respx.put(f"{CRM_URL}/api/bot/ficha").mock(return_value=httpx.Response(200, json={}))
    return envio


# ------------------------------------------------ se agenda al instante ---


@respx.mock
async def test_con_calendario_la_visita_se_agenda_al_instante_en_google_calendar():
    rt, ctx = await _rt()
    envio = _crm_falso()

    res = await rt._solicitar_visita(_slot(rt))

    assert res["estado"] == "visita_confirmada"
    llamada = ctx.calendar.booking_calls[0]
    assert llamada["service_key"] == "alemana"
    assert "Dr. Vértiz 1386" in llamada["description"]  # la dirección va en el evento (ROCA Ops)
    assert rt.booked is True and rt.handoff_reason is None  # y la IA sigue encendida
    assert (await ctx.store.get_active_calendar_booking(rt._conv.id)) is not None
    assert rt.caso.cita["estado"] == "confirmada"
    assert await ctx.store.list_pending_bookings_pendientes() == []  # nada que aprobar
    assert "Cita agendada" in envio.calls.last.request.content.decode()  # aviso informativo al dueño


@respx.mock
async def test_el_texto_al_cliente_es_una_confirmacion_sin_solicitud_ni_autorizacion():
    rt, ctx = await _rt()
    _crm_falso()
    await rt._solicitar_visita(_slot(rt))
    texto = rt.texto_garantizado
    assert "quedó agendada" in texto and "mañana lunes 5 de octubre, 10:00" in texto
    assert "Dr. Vértiz 1386" in texto
    assert "designado a tu técnico" in texto and "te enviaremos un mensaje" in texto
    for prohibida in ("solicitud", "autoriz", "pendiente", "confirme", "Leopoldo", "dueño", "disponibilidad"):
        assert prohibida not in texto, prohibida


@respx.mock
async def test_si_el_horario_se_ocupo_se_ofrecen_alternativas_y_no_se_agenda():
    cal = FakeCalendar()
    cal.create_result = CalendarSlotTaken([
        {"startUtc": "2026-10-05T17:00:00Z", "endUtc": "2026-10-05T18:30:00Z",
         "dayLabel": "mañana lunes 5 de octubre", "time": "11:00", "label": "lun 5 oct, 11:00"},
    ])
    rt, ctx = await _rt(calendar=cal)
    _crm_falso()
    res = await rt._solicitar_visita(_slot(rt))
    assert res["error"] == "slot_taken" and res["slots"]
    assert rt.booked is False and rt.caso.cita is None


@respx.mock
async def test_si_google_calendar_falla_cae_a_solicitud_con_aprobacion_del_dueno():
    cal = FakeCalendar()
    cal.create_result = CalendarError("sin conexión")
    rt, ctx = await _rt(calendar=cal)
    _crm_falso()
    await rt._solicitar_visita(_slot(rt))
    assert rt.caso.cita["estado"] == "pendiente_de_aprobacion"
    assert len(await ctx.store.list_pending_bookings_pendientes()) == 1


@respx.mock
async def test_en_zonas_de_un_solo_dia_sigue_la_aprobacion_del_dueno():
    rt, ctx = await _rt(zona_restringida=True)
    _crm_falso()
    await rt._solicitar_visita(_slot(rt))
    assert ctx.calendar.booking_calls == []  # el calendario no se toca hasta que apruebe
    assert rt.caso.cita["estado"] == "pendiente_de_aprobacion"
    assert len(await ctx.store.list_pending_bookings_pendientes()) == 1
    assert "Todavía no está confirmada" in rt.texto_garantizado


async def test_confirmada_el_paso_no_habla_de_solicitud_y_cubre_cancelar():
    caso = Caso(plaga="cucaracha_alemana")
    caso.cita = {"label": "lunes 5 de octubre, 10:00", "estado": "confirmada"}
    paso = paso_actual(caso)
    assert paso.nombre == "visita_confirmada"
    assert "técnico" in paso.toca and "por qué" in paso.toca and "reagendar" in paso.toca
    assert "solicitud" in paso.prohibido


# ------------------------------------- el día que pide el cliente (fechas) ---

HOY = date(2026, 10, 4)  # domingo


@pytest.mark.parametrize("texto,esperada", [
    ("tiene a las 10 am? mañana!", "2026-10-05"),
    ("pasado mañana a las 5", "2026-10-06"),
    ("si podrían el martes a las 9;00 am", "2026-10-06"),
    ("el domingo", "2026-10-11"),                  # hoy es domingo: el próximo
    ("el 12 de octubre", "2026-10-12"),
    ("el 3 de octubre", "2027-10-03"),              # ya pasó: el del año siguiente
    ("el 15", "2026-10-15"),
    ("15/10", "2026-10-15"),
])
def test_el_dia_que_pide_el_cliente(texto, esperada):
    assert fecha_pedida(texto, HOY) == esperada


@pytest.mark.parametrize("texto", [
    "por la mañana mejor", "en la mañana", "a las 10", "sí, agéndame", "tengo 2 colchones",
])
def test_si_no_pide_un_dia_no_se_inventa(texto):
    assert fecha_pedida(texto, HOY) is None


@pytest.mark.asyncio
async def test_si_pide_mañana_se_consulta_ese_dia_en_el_calendario():
    rt, ctx = await _rt(calendar=FakeCalendar())
    rt._mensajes_lead = ["tiene a las 10 am? mañana!"]
    ctx.calendar.availability_queue.append([
        {"startUtc": "2026-10-05T16:00:00Z", "endUtc": "2026-10-05T17:30:00Z",
         "dayLabel": "mañana lunes 5 de octubre", "time": "10:00", "label": "lun 5 oct, 10:00"},
    ])
    rt.caso.turno = 3
    rt.caso.cotizacion["turno"] = 1
    res = await rt._propose_slots({})
    assert "day" in ctx.calendar.availability_calls[0]  # consultó UN día, no el reparto
    assert rt.handoff_reason is None
    assert res.get("ok") is True


# ---------------------------------------------- «niguna» (con errata) ---


@pytest.mark.parametrize("texto", [
    "2 colchones, 2 sillones, 4 sillas de comedor niguna silla secretarial",
    "ninguna", "no tengo", "cero", "sin ninguna", "ningunas", "ningna",
])
def test_una_errata_en_ninguna_sigue_siendo_ninguna(texto):
    assert _dice_cero(texto) is True


@pytest.mark.parametrize("texto", ["tengo 3", "hola", "dos sillas", "ya te dije que 4"])
def test_sin_cero_no_se_asume(texto):
    assert _dice_cero(texto) is False


# ---------------------------------------------------------------- arañas ---


def test_con_arañas_lo_primero_que_se_pregunta_es_donde_las_ve():
    d = diagnostico.evaluar(
        "arana", [{"senal": "telarana", "cita": "con telarañas"}],
        mensajes_lead=["tengo arañas en mi casa", "con telarañas y unas grandes"],
    )
    assert d.estado == "faltan_senales"
    assert d.senal_preguntada == "ubicacion_arana"
    assert "jardín" in d.pregunta and "dentro de tu casa" in d.pregunta
    assert d.pregunta.count("?") == 1


def test_decir_donde_las_ve_cuenta_como_indicio_aunque_el_modelo_no_lo_etiquete():
    d = diagnostico.evaluar(
        "arana", [{"senal": "telarana", "cita": "con telarañas"}],
        mensajes_lead=["tengo arañas con telarañas", "las veo más en el jardín"],
    )
    assert d.estado == "confirmada" and d.plaga == "arana"


def test_en_mi_casa_a_secas_no_dice_si_es_jardin_o_interior():
    d = diagnostico.evaluar(
        "arana", [{"senal": "telarana", "cita": "con telarañas"}],
        mensajes_lead=["tengo arañas en mi casa con telarañas"],
    )
    assert d.estado != "confirmada" and d.senal_preguntada == "ubicacion_arana"


def test_ante_la_violinista_o_la_viuda_negra_se_da_tranquilidad_y_no_alarma():
    texto = bloque_de_tratamiento("arana", "tengo miedo que sean violinitas o viuda negra")
    t = texto.lower()
    assert "técnico especializado" in t and "foto muy nítida" in t
    assert "cualquier" in t or "sea cual sea la especie" in t
    assert "viven y se desarrollan en el exterior" in t and "refugiarse" in t
    assert "⚠️" not in texto and "cuidado extra" not in t
    assert "sí es" not in t and "no es una viuda" not in t


def test_sin_nombrar_una_peligrosa_no_se_agrega_esa_tranquilidad():
    texto = bloque_de_tratamiento("arana", "tienen patas largas y hay telarañas")
    assert catalogo.PLAGAS["arana"]["tranquilidad_peligrosa"] not in texto
