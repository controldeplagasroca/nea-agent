"""Caso real (3 oct, prueba de Mariana): dijo «chinche» y le cotizaron cucaracha
alemana, porque lo confirmado de una prueba anterior seguía en el expediente.
Una cotización siempre es de la plaga de la que el cliente habla AHORA."""
from __future__ import annotations

import pytest

from app.plagas.caso import Caso
from app.plagas.herramientas import RuntimeDePlagas, _ultima_plaga_nombrada
from tests.conftest import CRM_CONV_ID, IDENTITY, FakeCalendar, make_ctx, make_settings


async def _rt(plaga_confirmada: str, mensajes: list[str]) -> RuntimeDePlagas:
    ctx = make_ctx(make_settings(vertical="plagas"), calendar=FakeCalendar())
    conv = await ctx.store.get_or_create_conversation(IDENTITY)
    caso = Caso(plaga=plaga_confirmada, turno=5, turno_plaga=1)
    caso.cobertura = {"estado": "dentro_de_zona"}
    caso.variables = {"tipo_inmueble": "departamento"}
    return RuntimeDePlagas(ctx, conv, CRM_CONV_ID, caso=caso, mensajes_lead=mensajes)


async def test_chinches_nunca_se_cotizan_como_cucaracha_alemana():
    rt = await _rt("cucaracha_alemana", [
        "son chiquitas y salen en la cocina",       # lo de la prueba anterior
        "Chinche tengo",
        "Si piquetes muchos y manchas en la sabana",
        "Tengo cuatro colchones",
    ])
    res = await rt._cotizar({"tipo_inmueble": "departamento"})

    assert res["error"] == "plaga_distinta_a_la_confirmada"
    assert "chinches" in res["instrucciones"]
    assert rt.caso.plaga is None and rt.caso.cotizacion is None
    assert rt.texto_garantizado is None  # no salió ningún resumen con precio


async def test_si_el_cliente_sigue_hablando_de_la_misma_plaga_si_se_cotiza():
    rt = await _rt("cucaracha_alemana", ["son cucarachas chiquitas en la cocina", "es un departamento"])
    res = await rt._cotizar({"tipo_inmueble": "departamento"})
    assert res.get("ok") is True and rt.cotizado


async def test_cucaracha_alemana_y_americana_son_la_misma_familia():
    rt = await _rt("cucaracha_americana", ["tengo cucarachas grandes", "departamento"])
    res = await rt._cotizar({"tipo_inmueble": "departamento"})
    assert res.get("error") != "plaga_distinta_a_la_confirmada"


@pytest.mark.parametrize("texto,esperada", [
    ("no son cucarachas, son chinches", "chinches"),
    ("Chinche tengo", "chinches"),
    ("hola buenas tardes", None),
])
def test_la_ultima_plaga_nombrada_es_la_que_manda(texto, esperada):
    assert _ultima_plaga_nombrada(texto) == esperada


# ------------------------------------------- diagnóstico de chinches (3 oct) ---


def _evaluar(senales, mensajes):
    from app.plagas import diagnostico

    return diagnostico.evaluar("chinches", senales, mensajes_lead=mensajes)


def test_dos_indicios_ya_confirman_chinches():
    d = _evaluar(
        [{"senal": "dice_chinches", "cita": "Tengo chinches"},
         {"senal": "manchas_sabanas", "cita": "He visto manchas en las sábanas"}],
        ["Tengo chinches", "He visto manchas en las sábanas y detrás de la cabecera animalitos"],
    )
    assert d.estado == "confirmada" and d.plaga == "chinches"


def test_ver_los_bichos_cuenta_como_indicio():
    d = _evaluar(
        [{"senal": "manchas_sabanas", "cita": "manchas en las sábanas"},
         {"senal": "bicho_visto", "cita": "detrás de la cabecera animalitos"}],
        ["He visto manchas en las sábanas y detrás de la cabecera animalitos"],
    )
    assert d.estado == "confirmada"


def test_un_solo_indicio_todavia_no_confirma_y_no_se_pregunta_por_el_viaje():
    d = _evaluar(
        [{"senal": "dice_chinches", "cita": "Tengo chinches"}], ["Tengo chinches"]
    )
    assert d.estado == "faltan_senales"
    assert d.senal_preguntada == "bicho_visto" or d.senal_preguntada == "piquetes_linea"
    assert "viaje" not in d.pregunta and "chinches?" not in d.pregunta


def test_nunca_se_pregunta_por_viajes_ni_por_si_dice_que_son_chinches():
    from app.plagas import catalogo, diagnostico

    d = diagnostico.evaluar("chinches", [], mensajes_lead=[])
    preguntadas: list[str] = []
    for _ in range(10):
        d = diagnostico.evaluar("chinches", [], preguntadas=preguntadas, mensajes_lead=[])
        if not d.senal_preguntada:
            break
        assert d.senal_preguntada not in ("viaje_o_mueble", "dice_chinches")
        preguntadas.append(d.senal_preguntada)


# ------------------- caso real 3 oct, 21:26-21:32: identificó pero no cotizó ---


@pytest.mark.parametrize("mensajes", [
    ["Tengo manchas en las sábanas y piquetes"],
    ["he visto manchas en las sábanas", "no se en las costuras pero tengo piquetes"],
    ["tengo chinches", "vi animalitos detrás de la cabecera"],
    ["tengo chinches y manchas de sangre en la cama"],
])
def test_el_servidor_reconoce_los_indicios_aunque_el_modelo_no_los_etiquete(mensajes):
    d = _evaluar([], mensajes)  # el modelo no mandó ninguna señal
    assert d.estado == "confirmada" and d.plaga == "chinches"


@pytest.mark.parametrize("mensajes", [
    ["no he visto chinches"],
    ["no tengo piquetes ni manchas en las sábanas"],
    ["tengo un solo piquete"],
    ["hola, ¿cuánto cuesta?"],
])
def test_un_indicio_negado_o_ausente_no_confirma(mensajes):
    assert _evaluar([], mensajes).estado != "confirmada"


def test_prometer_que_el_dueno_dara_el_precio_sin_pasarlo_es_una_promesa_vacia():
    from app.plagas import candados

    texto = (
        "Lo que me cuentas sugiere que es chinche de cama. 🛏️\n\nEl tratamiento incluye dos "
        "visitas, y ya he enviado tus datos al Ing. Leopoldo. Te dará el precio exacto pronto. "
        "¿Hay algo más que te gustaría preguntar mientras tanto?"
    )
    assert candados.promesa_vacia(texto) != ""


@pytest.mark.parametrize("texto", [
    "Ya le pasé tus datos al Ing. Leopoldo.",
    "Mi equipo ya recibió tu solicitud y te confirmará la visita.",
    "El Ing. Leopoldo te escribirá en breve.",
])
def test_dar_por_hecho_un_pase_que_no_ocurrio_se_detecta(texto):
    from app.plagas import candados

    assert candados.promesa_vacia(texto) != ""


def test_una_pregunta_normal_de_cotizacion_no_es_promesa():
    from app.plagas import candados

    assert candados.promesa_vacia(
        "¿Cuántos colchones, sillones y sillas de comedor tapizadas hay en total en toda la casa?"
    ) == ""
