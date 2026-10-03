"""BUG 1 — "9:30 pm" agendado como 09:30.

Caso real reportado:

    Agente ofrece: 09:00, 09:30, 10:00 (todos de la MAÑANA)
    Cliente dice:  "si mañana 21 dept 9:30 pm"
    Agente agenda: 09:30 — y confirma "mañana ... a las 09:30"

El epoch era válido (ese slot SÍ se había ofrecido), pero la interpretación del
cliente era la contraria. Mandar al técnico a las 09:30 cuando el cliente espera
las 21:30 es un servicio perdido.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.horarios import (
    analizar_horas,
    meridiem_global,
    validar_hora_contra_slot,
    zona_agente,
)

TZ = ZoneInfo("America/Mexico_City")


def _slot_local(hora: int, minuto: int, dia: int = 21) -> datetime:
    """Hora local de México → el datetime UTC que usa el agente."""
    return datetime(2026, 9, dia, hora, minuto, tzinfo=TZ).astimezone(timezone.utc)


# El slot que el agente ofreció y que el modelo eligió: 09:30 de la MAÑANA.
SLOT_0930_AM = _slot_local(9, 30)
SLOT_2130_PM = _slot_local(21, 30)


# =========================================================================
# EL CASO REAL
# =========================================================================


def test_caso_real_9_30_pm_no_puede_agendarse_como_09_30_am():
    """Reproduce el bug tal cual: se rechaza en vez de agendar la hora mala."""
    ok, error = validar_hora_contra_slot(
        "si mañana 21 dept 9:30 pm", SLOT_0930_AM, TZ
    )
    assert ok is False, "agendó 09:30 AM cuando el cliente pidió 9:30 PM"
    assert error is not None
    assert error["error"] == "ambiguo_am_pm"


def test_el_error_obliga_a_preguntar_de_la_manana_o_de_la_noche():
    _, error = validar_hora_contra_slot("si mañana 21 dept 9:30 pm", SLOT_0930_AM, TZ)
    texto = error["instrucciones"]
    assert "de la mañana o de la noche" in texto
    assert "NO agendes" in texto
    # Debe darle la salida si el cliente quiere una hora que no se ofreció.
    assert "propose_slots" in texto


def test_el_error_dice_que_hora_dijo_el_lead_y_cual_el_slot():
    _, error = validar_hora_contra_slot("si mañana 21 dept 9:30 pm", SLOT_0930_AM, TZ)
    assert "9:30" in error["hora_del_lead"]
    assert "noche" in error["hora_del_lead"]
    assert "09:30" in error["hora_del_slot"]
    assert "mañana" in error["hora_del_slot"]


# =========================================================================
# El contraste AM/PM en las dos direcciones
# =========================================================================


def test_9_30_pm_si_coincide_con_un_slot_de_la_noche():
    ok, error = validar_hora_contra_slot("a las 9:30 pm", SLOT_2130_PM, TZ)
    assert ok is True and error is None


def test_9_30_am_si_coincide_con_el_slot_de_la_manana():
    ok, error = validar_hora_contra_slot("mejor a las 9:30 am", SLOT_0930_AM, TZ)
    assert ok is True and error is None


def test_9_30_de_la_noche_tampoco_se_agenda_a_las_09_30():
    """El meridiano puede venir como frase, no como 'pm'."""
    ok, error = validar_hora_contra_slot("mejor a las 9:30 de la noche", SLOT_0930_AM, TZ)
    assert ok is False
    assert error["error"] == "ambiguo_am_pm"


def test_21_30_explicito_tampoco_cuela_como_09_30():
    """La hora en formato 24 h ya trae el meridiano implícito."""
    ok, error = validar_hora_contra_slot("a las 21:30", SLOT_0930_AM, TZ)
    assert ok is False
    assert error["error"] == "ambiguo_am_pm"


def test_una_hora_sin_meridiano_no_se_bloquea():
    """Si el cliente no dijo meridiano, no hay nada que contrastar: el slot
    ofrecido es la referencia y el agente ya nombró el horario completo."""
    ok, error = validar_hora_contra_slot("mejor a las 9:30", SLOT_0930_AM, TZ)
    assert ok is True and error is None


def test_sin_hora_en_el_mensaje_no_se_bloquea():
    ok, error = validar_hora_contra_slot("sí, perfecto", SLOT_0930_AM, TZ)
    assert ok is True and error is None


# =========================================================================
# Disponibilidad: una hora que nadie ofreció no se agenda
# =========================================================================


def test_una_hora_que_no_esta_entre_las_ofrecidas_se_rechaza():
    ok, error = validar_hora_contra_slot("mejor a las 11:00", SLOT_0930_AM, TZ)
    assert ok is False
    assert error["error"] == "hora_no_ofrecida"
    assert "propose_slots" in error["instrucciones"]


def test_no_se_asume_que_cualquier_hora_del_cliente_esta_libre():
    """El agente no puede inventar un horario que nunca propuso."""
    for hora in ("8:00", "12:30", "17:45"):
        ok, error = validar_hora_contra_slot(f"a las {hora}", SLOT_0930_AM, TZ)
        assert ok is False, hora
        assert error["error"] == "hora_no_ofrecida"


def test_si_menciona_varias_horas_basta_que_una_cuadre():
    ok, error = validar_hora_contra_slot("¿9:30 o 10:00 am?", SLOT_0930_AM, TZ)
    assert ok is True and error is None


# =========================================================================
# Parseo de horas
# =========================================================================


@pytest.mark.parametrize(
    "texto,hora,minuto,meridiem",
    [
        ("a las 9:30 pm", 9, 30, "pm"),
        ("9:30 p.m.", 9, 30, "pm"),
        ("9 pm", 9, 0, "pm"),
        ("9:15 a.m.", 9, 15, "am"),
        ("a las 3 de la tarde", 3, 0, "pm"),
        ("a las 7 de la noche", 7, 0, "pm"),
        ("a las 5 de la manana", 5, 0, "am"),
        ("21:30", 9, 30, "pm"),
        ("a las 11", 11, 0, None),
    ],
)
def test_parseo_de_horas(texto, hora, minuto, meridiem):
    horas = analizar_horas(texto)
    assert len(horas) == 1, texto
    assert (horas[0].hora, horas[0].minuto, horas[0].meridiem) == (hora, minuto, meridiem)


def test_manana_sola_no_es_meridiano_am():
    """'mañana' = el día de mañana. Solo 'de la mañana' es AM."""
    assert meridiem_global("nos vemos mañana") is None
    assert meridiem_global("mañana lunes 21") is None
    assert meridiem_global("a las 9 de la mañana") == "am"
    assert meridiem_global("por la noche") == "pm"


def test_el_caso_real_completo_se_parsea_como_pm():
    horas = analizar_horas("si mañana 21 dept 9:30 pm")
    assert len(horas) == 1
    assert horas[0].meridiem == "pm"
    assert horas[0].hora == 9 and horas[0].minuto == 30


def test_zona_agente_tolera_configuracion_invalida():
    assert str(zona_agente("America/Mexico_City")) == "America/Mexico_City"
    assert str(zona_agente("no/existe")) == "America/Mexico_City"
    assert str(zona_agente(None)) == "America/Mexico_City"


# =========================================================================
# Los formatos que escriben clientes REALES (muestreados del CRM)
#
# El caso reportado llegó literalmente como "si mañana 21 dept 9;30 pm": con
# PUNTO Y COMA, no dos puntos. La primera versión del parser solo entendía ":" ,
# así que con ese texto no encontraba ninguna hora, no tenía nada que contrastar
# y la reserva pasaba — el bug seguía vivo.
# =========================================================================


def test_el_texto_real_del_bug_con_punto_y_coma_se_detecta():
    horas = analizar_horas("si mañana 21 dept 9;30 pm")
    assert len(horas) == 1
    assert (horas[0].hora, horas[0].minuto, horas[0].meridiem) == (9, 30, "pm")


def test_el_texto_real_del_bug_se_rechaza_contra_el_slot_de_la_manana():
    ok, error = validar_hora_contra_slot("si mañana 21 dept 9;30 pm", SLOT_0930_AM, TZ)
    assert ok is False
    assert error["error"] == "ambiguo_am_pm"


@pytest.mark.parametrize(
    "texto_real,hora,minuto,meridiem",
    [
        ("si mañana 21 dept 9;30 pm", 9, 30, "pm"),
        ("mañana a las 4pm te acomoda?", 4, 0, "pm"),
        ("Hola 4 pm porfavor", 4, 0, "pm"),
        ("¿Podría ser que sea 10:30?", 10, 30, None),
        ("Si, a las 10 queda muy bien", 10, 0, None),
        ("igual a las 12:00", 12, 0, None),
        ("para el día lunes 21 a las 7:00", 7, 0, None),
        ("solo para confirmar el servicio de mañana a las 11 am", 11, 0, "am"),
    ],
)
def test_formatos_reales_de_clientes(texto_real, hora, minuto, meridiem):
    horas = analizar_horas(texto_real)
    assert len(horas) == 1, texto_real
    assert (horas[0].hora, horas[0].minuto, horas[0].meridiem) == (hora, minuto, meridiem)


def test_los_decimales_no_se_confunden_con_horas():
    """Por eso el punto NO es separador de hora: "$1,200.50" inyectaría una
    hora falsa y podría bloquear una reserva legítima."""
    assert analizar_horas("el costo es $1,200.50") == []
    assert analizar_horas("son 2,500.00 pesos") == []


def test_una_aclaracion_posterior_desbloquea_la_reserva():
    """Caso real de uso: el lead dice "9:30 pm", el agente pregunta por el
    meridiano y el lead contesta "de la mañana".

    Si el analizador se quedara solo con la PRIMERA lectura de esa hora, la
    reserva quedaría bloqueada para siempre en esa conversación — el agente
    preguntaría, el cliente respondería, y seguiría sin poder agendar.
    """
    hilo = "si mañana 21 dept 9;30 pm\nsí, a las 9:30 de la mañana"
    horas = analizar_horas(hilo)
    assert {(h.hora, h.minuto, h.meridiem) for h in horas} == {(9, 30, "pm"), (9, 30, "am")}

    # Y con la aclaración en el hilo, el slot de la mañana SÍ se puede agendar.
    ok, error = validar_hora_contra_slot(hilo, SLOT_0930_AM, TZ)
    assert ok is True and error is None


def test_la_aclaracion_no_desbloquea_una_hora_que_sigue_siendo_la_equivocada():
    """Control: si el lead confirma la hora de la NOCHE, el slot de la mañana
    sigue rechazándose."""
    hilo = "si mañana 21 dept 9;30 pm\nsí, de la noche"
    ok, error = validar_hora_contra_slot(hilo, SLOT_0930_AM, TZ)
    assert ok is False and error["error"] == "ambiguo_am_pm"
