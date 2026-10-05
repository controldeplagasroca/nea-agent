"""Propuestas 1 y 2 (4 oct): el servidor lee más de lo que dijo el cliente, y la autoprueba
con el modelo real caza las repreguntas. Aquí se prueba lo determinista: la lectura y los
chequeos, sin llamar a ningún modelo."""
from __future__ import annotations

from app.plagas.muebles import muebles_dichos
from selftest.roca import checks
from selftest.roca.escenarios import ESCENARIOS, POR_ID


def test_lee_banos_registros_y_refrigeradores():
    d = muebles_dichos(["tengo 3 baños, 2 registros y 2 refris en el negocio"])
    assert d == {"sanitarios": 3, "registros": 2, "refrigeradores": 2}


def test_dos_banos_y_medio_no_se_adivina():
    assert "sanitarios" not in muebles_dichos(["son dos baños y medio"])


def test_sin_registros_es_cero():
    assert muebles_dichos(["no tengo registros"]) == {"registros": 0}


def _res(turnos):
    return {"modo": "vertical", "turnos": [{"lead": l, "bot": b} for l, b in turnos]}


def test_chequeo_pregunta_repetida():
    res = _res([
        (["tengo chinches"], "Ya casi lo tengo 👌 ¿Has visto los insectos directamente, por ejemplo detrás de la cabecera?"),
        (["en cama y cabecera"], "Entendido 👌 ¿Has visto los insectos directamente, por ejemplo detrás de la cabecera o en las costuras?"),
    ])
    assert any(f.startswith("pregunta_repetida") for f in checks.repreguntas(res))


def test_chequeo_repregunta_de_direccion_ya_dicha():
    res = _res([
        (["vivo en portales en 03300 calle vertiz 2200 alcaldia benito juarez, tengo chinches"], "¡Hola! ¿Desde cuándo las notas?"),
        (["desde hace una semana"], "Para registrar la visita, ¿me das tu dirección completa?"),
    ])
    assert any("repregunta_dato_dicho" in f and "calle" in f for f in checks.repreguntas(res))


def test_chequeo_repregunta_de_muebles_ya_dichos():
    res = _res([
        (["tengo 2 colchones y 2 sillones"], "Perfecto. ¿Cuántos colchones hay en total en la casa?"),
    ])
    assert any("colchones" in f for f in checks.repreguntas(res))


def test_chequeo_no_acusa_si_pide_solo_lo_que_falta():
    res = _res([
        (["calle vertiz 2200, colonia portales, alcaldia benito juarez"], "¡Hola! ¿Qué bicho has visto?"),
        (["chinches"], "Para registrar la visita me falta una referencia para llegar. ¿Entre qué calles queda?"),
    ])
    assert checks.repreguntas(res) == []


def test_escenarios_nuevos_estan_registrados_sin_ids_repetidos():
    ids = [e.id for e in ESCENARIOS]
    assert len(ids) == len(set(ids))
    for clave in ("chinches_todo_en_el_primer_mensaje", "chinches_contesta_donde_las_ve", "cucarachas_sin_pistas"):
        assert clave in POR_ID
    assert POR_ID["chinches"].espera["precio"] == 1750
