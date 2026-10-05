"""4 oct, conversación de chinches: el cliente contestó «en cama y cabecera», «ya las vi,
son chinches», «pican», y el bot siguió preguntando lo mismo; la dirección del primer
mensaje se pidió otra vez al final. Lo que el cliente ya dijo se toma de su texto."""
from __future__ import annotations

from types import SimpleNamespace

from app.plagas import diagnostico
from app.plagas.direccion import direccion_dicha
from app.plagas.turno import abrir_caso


def test_direccion_del_primer_mensaje_de_ethel():
    d = direccion_dicha(
        "vivo en portales en 03300 calle vertiz 2200 alcaldia benito juarez, tengo chinche de cama"
    )
    assert d["colonia"] == "Portales"
    assert d["calle"] == "Vertiz" and d["numero_exterior"] == "2200"
    assert d["alcaldia_municipio"] == "Benito Juarez"


def test_direccion_con_acentos_conserva_la_ortografia_del_cliente():
    d = direccion_dicha("Calle Dr. Vértiz 1386, colonia Narvarte Poniente, alcaldía Benito Juárez, int. 4B")
    assert d["numero_exterior"] == "1386" and d["numero_interior"] == "4B"
    assert d["colonia"] == "Narvarte Poniente" and d["alcaldia_municipio"] == "Benito Juárez"


def test_referencia_y_avenida():
    d = direccion_dicha("Av. Insurgentes 300, col. Roma, ref: casa azul junto al Oxxo")
    assert d["calle"].startswith("Av") and "Insurgentes" in d["calle"]
    assert d["referencia"] == "casa azul junto al Oxxo"


def test_sin_marcadores_no_se_inventa_nada():
    assert direccion_dicha("tengo cucarachas en mi departamento, quiero precio") == {}
    assert direccion_dicha("el departamento es de 60 m2") == {}


def test_abrir_caso_guarda_la_direccion_y_no_pisa_lo_que_ya_estaba():
    conv = SimpleNamespace(caso={"direccion": {"colonia": "Del Valle"}})
    caso = abrir_caso(conv, None, "calle Vertiz 2200, colonia Portales, alcaldía Benito Juárez")
    assert caso.direccion["calle"] == "Vertiz" and caso.direccion["numero_exterior"] == "2200"
    assert caso.direccion["colonia"] == "Del Valle"  # lo anterior manda
    assert caso.direccion_faltante() == ["referencia"]


def test_chinches_en_cama_y_cabecera_ya_las_vi_pican_confirma_sin_mas_preguntas():
    d = diagnostico.evaluar(
        "chinches",
        [],
        mensajes_lead=[
            "en cama y cabecera.",
            "no tantos piquetes pero ya las vi son chinches, ya lo compare en internet, pican y no puedo dormir",
        ],
    )
    assert d.estado == "confirmada" and d.plaga == "chinches"
    assert d.pregunta == ""


def test_solo_decir_en_la_cama_no_basta_si_no_hay_mas():
    d = diagnostico.evaluar("chinches", [], mensajes_lead=["tengo bichos en la casa"])
    assert d.estado != "confirmada"
