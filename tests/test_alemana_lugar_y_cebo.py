"""4 oct (conversación de Ethel): «tengo cucaracha de la cocina de las chiquitas» y el
bot, en vez de confirmar, volvió a preguntar «¿en qué parte las ves más: en la
cocina…?». Y el tratamiento se explicaba como «polvo fino focalizado»; la forma
correcta es un cebo en polvo en las zonas de refugio que el técnico ya sabe identificar.
"""
from __future__ import annotations

import pytest

from app.plagas import candados, catalogo, diagnostico
from app.plagas.herramientas import bloque_de_tratamiento


def _cuca(senales, mensajes, **extra):
    return diagnostico.evaluar("cucaracha", senales, mensajes_lead=mensajes, **extra)


def test_si_dijo_de_la_cocina_no_se_le_vuelve_a_preguntar_el_lugar():
    """El modelo solo etiquetó el tamaño; el lugar ya estaba en el mensaje."""
    d = _cuca(
        [{"senal": "tamano_chica", "cita": "las chiquitas"}],
        ["creo que son cucarachas", "tengo cucaracha de la cocina de las chiquitas"],
    )
    assert d.estado == "confirmada" and d.plaga == "cucaracha_alemana"


def test_ya_te_dije_que_en_la_cocina_tambien_cuenta():
    d = _cuca(
        [{"senal": "tamano_chica", "cita": "las chiquitas"}],
        ["tengo cucaracha de las chiquitas", "ya te dije que en la cocina!"],
    )
    assert d.estado == "confirmada"


@pytest.mark.parametrize("mensaje", [
    "no las he visto en la cocina",
    "en la cocina nunca",
    "ni en la cocina ni en el baño",
])
def test_un_lugar_negado_no_cuenta(mensaje):
    d = _cuca([{"senal": "tamano_chica", "cita": "chiquitas"}], ["son chiquitas", mensaje])
    assert "ubicacion_cocina" not in d.senales
    assert d.estado != "confirmada"


def test_el_drenaje_dicho_por_el_cliente_cuenta_para_la_americana():
    d = _cuca(
        [{"senal": "tamano_grande", "cita": "son grandes"}],
        ["son grandes", "salen de la coladera del patio"],
    )
    assert d.estado == "confirmada" and d.plaga == "cucaracha_americana"


def test_el_bano_solo_no_confirma_ninguna_especie():
    d = _cuca(
        [{"senal": "tamano_chica", "cita": "son chiquitas"}],
        ["son chiquitas", "las veo en el baño"],
    )
    assert d.estado != "confirmada"


def test_la_pregunta_de_lugar_trae_pistas_concretas_y_no_repite_cocina_o_drenaje():
    p = catalogo.PREGUNTA_CUCARACHA_UBICACION
    assert p.count("?") == 1
    assert "refrigerador" in p and "contactos de luz" in p and "coladeras" in p
    assert "¿En qué parte las ves más" not in p


def test_contestar_con_las_pistas_de_la_cocina_cuenta_como_lugar():
    d = _cuca(
        [{"senal": "tamano_chica", "cita": "chiquitas"},
         {"senal": "ubicacion_cocina", "cita": "detrás del refri y en los contactos de luz"}],
        ["son chiquitas", "sí, detrás del refri y en los contactos de luz"],
    )
    assert d.estado == "confirmada" and d.plaga == "cucaracha_alemana"


# ------------------------------------------------------ el cebo en polvo ---


def test_el_tratamiento_de_la_alemana_dice_cebo_en_polvo_en_zonas_de_refugio():
    bloque = bloque_de_tratamiento("cucaracha_alemana")
    plano = bloque.lower()
    assert "cebo en polvo" in plano and "zonas de refugio" in plano
    assert "técnico" in plano and "no es una aspersión general" in plano
    assert "focalizado" not in plano


@pytest.mark.parametrize("texto", [
    "El técnico coloca un cebo en polvo en las zonas donde se refugian.",
    "No es una neblina: es un cebo en polvo fino que él ya sabe dónde poner.",
])
def test_el_modelo_puede_decir_cebo_en_polvo_de_la_alemana(texto):
    assert candados.tratamiento_ajeno(texto, "cucaracha_alemana") == []


def test_pero_no_puede_decir_gel_ni_trampas_de_la_alemana():
    ajenos = candados.tratamiento_ajeno("Se aplica gel y se ponen trampas.", "cucaracha_alemana")
    assert "gel" in ajenos and "trampas" in ajenos
