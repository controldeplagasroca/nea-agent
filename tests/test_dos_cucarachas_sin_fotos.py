"""4 oct: dos cucarachas en la misma casa, sin pedir fotos y sin nombrar al dueño.

Caso real (conversación de Mariana): «en la cocina chiquita y en el baño rojas
grandes». El bot mostró la comparación, pidió una foto, y la conversación terminó
pasada a una persona sin resolver nada. Y se le decía al cliente «el Ing. Leopoldo».
"""
from __future__ import annotations

import pytest

from app.plagas import candados, catalogo, diagnostico
from tests.conftest import FakeLLM
from tests.test_plagas_turno import _caso, _ctx, _dice, _llama, _turno


def _cuca(senales, mensajes, **extra):
    return diagnostico.evaluar("cucaracha", senales, mensajes_lead=mensajes, **extra)


def test_chicas_en_la_cocina_y_grandes_en_el_bano_son_las_dos_especies():
    d = _cuca(
        [{"senal": "tamano_chica", "cita": "cocina chiquita"},
         {"senal": "tamano_grande", "cita": "baño rojas grandes"},
         {"senal": "ubicacion_cocina", "cita": "en la cocina"},
         {"senal": "ubicacion_bano", "cita": "en el baño"}],
        ["Cucarachas en la cocina y en el baño", "De las dos",
         "En la cocina chiquita y en el baño rojas grandes"],
    )
    assert d.estado == "confirmada" and d.ambas is True


def test_chicas_y_grandes_en_un_solo_lugar_todavia_no_son_las_dos():
    d = _cuca(
        [{"senal": "tamano_chica", "cita": "chiquitas"},
         {"senal": "tamano_grande", "cita": "grandes"},
         {"senal": "ubicacion_cocina", "cita": "en la cocina"}],
        ["hay chiquitas y grandes", "todas en la cocina"],
    )
    assert d.ambas is False and d.estado != "confirmada"


def test_si_tamano_y_lugar_no_cierran_se_sigue_con_comportamiento_y_no_con_foto():
    senales = [{"senal": "tamano_chica", "cita": "chiquitas"},
               {"senal": "ubicacion_drenaje", "cita": "salen de la coladera"}]
    mensajes = ["son chiquitas y salen de la coladera"]
    d = _cuca(senales, mensajes)
    assert d.senal_preguntada == "comportamiento_1"
    assert "foto" not in d.pregunta.lower()
    d2 = _cuca(senales, mensajes, preguntadas=["comportamiento_1"])
    assert d2.senal_preguntada == "comportamiento_2"
    d3 = _cuca(senales, mensajes, preguntadas=["comportamiento_1", "comportamiento_2"])
    assert d3.atasco is True  # ya sí: tarjeta comparativa


def test_el_comportamiento_desempata():
    d = _cuca(
        [{"senal": "tamano_chica", "cita": "chiquitas"},
         {"senal": "ubicacion_drenaje", "cita": "salen de la coladera"},
         {"senal": "comp_muchas_juntas", "cita": "se ven muchas juntas de varios tamaños"}],
        ["son chiquitas y salen de la coladera", "se ven muchas juntas de varios tamaños"],
        preguntadas=["comportamiento_1", "comportamiento_2"],
    )
    assert d.estado == "confirmada" and d.plaga == "cucaracha_alemana" and not d.ambas


async def test_con_las_dos_cucarachas_se_explica_cada_una_y_se_pasa_a_un_tecnico():
    llm = FakeLLM()
    ctx = _ctx(llm)
    llm.replies += [
        _llama("verificar_cobertura", zona="Escandón", codigo_postal="11800"),
        _llama("identificar_plaga", plaga="cucaracha", senales=[
            {"senal": "tamano_chica", "cita": "chiquita"},
            {"senal": "tamano_grande", "cita": "rojas grandes"},
            {"senal": "ubicacion_cocina", "cita": "en la cocina"},
            {"senal": "ubicacion_bano", "cita": "en el baño"},
        ]),
        _dice("x"),
    ]
    texto = await _turno(
        ctx, "tengo cucarachas en la cocina chiquita y en el baño rojas grandes, Escandón 11800", 1
    )
    assert texto is not None and "las dos" in texto
    assert "Alemana:" in texto and "Americana:" in texto
    assert "foto" not in texto.lower()
    assert (await _caso(ctx))["ambas"] is True

    llm.replies += [_llama("cotizar", tipo_inmueble="departamento"), _dice("x")]
    texto = await _turno(ctx, "es un departamento, cuánto cuesta?", 2)
    assert texto is not None and "técnico especializado" in texto
    assert "Leopoldo" not in texto and "dueño" not in texto.lower()
    assert "$" not in texto  # el precio de las dos juntas lo define una persona
    assert ctx.crm.handoffs == ["modelo"]


async def test_si_ya_no_hay_mas_que_preguntar_pasa_a_un_tecnico_sin_pedir_foto():
    llm = FakeLLM()
    ctx = _ctx(llm)
    llm.replies += [
        _llama("identificar_plaga", plaga="cucaracha", senales=[
            {"senal": "tamano_chica", "cita": "son chiquitas"},
            {"senal": "ubicacion_drenaje", "cita": "salen de la coladera"},
        ]),
        _dice("x"),
    ]
    from tests.test_plagas_turno import LEAD

    c = await ctx.store.get_or_create_conversation(LEAD)
    await ctx.store.update_conversation(
        c.id,
        caso={"preguntadas": ["tamano", "ubicacion", "comportamiento_1", "comportamiento_2"],
              "atascos": 1, "tarjetas": 1, "turno_tarjeta": 0},
    )
    texto = await _turno(ctx, "son chiquitas y salen de la coladera", 1)
    assert texto is not None and "foto" not in texto.lower()
    assert "técnico especializado" in texto
    assert ctx.crm.handoffs == ["modelo"]


def test_el_catalogo_ya_no_trae_el_nombre_del_dueno():
    assert catalogo.NEGOCIO["dueno"] == "un técnico especializado"


@pytest.mark.parametrize("texto", [
    "¿Me puedes mandar una foto de una de ellas?",
    "Mándame una foto, aunque esté muerta",
    "Envíame una imagen de la plaga",
    "¿Podrías tomarle una foto?",
])
def test_pedir_una_foto_se_detecta(texto):
    assert candados.pide_foto(texto) != ""


@pytest.mark.parametrize("texto", [
    "Gracias por la foto que me enviaste.",
    "Gracias por enviarme la foto.",
    "Por la foto parece alemana.",
])
def test_comentar_la_foto_que_el_cliente_mando_no_es_pedirla(texto):
    assert candados.pide_foto(texto) == ""


@pytest.mark.parametrize("texto", [
    "Ya le avisé al Ing. Leopoldo.",
    "El dueño te contesta en breve.",
    "Le paso tu caso al ingeniero.",
    "Habla con Leopoldo directamente.",
    "Se lo paso a mi jefe.",
])
def test_nunca_se_nombra_al_dueno(texto):
    assert candados.menciona_al_dueno(texto) != ""


@pytest.mark.parametrize("texto", [
    "Te atiende un técnico especializado.",
    "¿Eres el dueño de la casa o rentas?",
    "El dueño del departamento autoriza la fumigación.",
])
def test_decir_tecnico_especializado_o_dueno_de_la_casa_esta_bien(texto):
    assert candados.menciona_al_dueno(texto) == ""
