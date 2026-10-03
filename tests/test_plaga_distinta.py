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
