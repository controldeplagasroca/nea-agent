"""Los HECHOS del vertical de plagas: cobertura, diagnóstico y precios.

Los números de aquí salen de la especificación del negocio («Nea —
Especificación de comportamiento», secciones 4 a 7), no del catálogo: si
alguien cambia un precio o una zona por error, esto se pone rojo.
"""
from __future__ import annotations

import pytest

from app.plagas import catalogo, cobertura, diagnostico, precios

# ---------------------------------------------------------------- cobertura ---


@pytest.mark.parametrize(
    "zona, cp",
    [
        ("Tepito", ""),
        ("Jardines de Morelos, Ecatepec", ""),
        ("Gustavo A. Madero", ""),
        ("colonia Lindavista, GAM", ""),
        ("Lindavista", "07300"),  # GAM por código postal, sin nombrarla
        ("", "55120"),  # Ecatepec por código postal
    ],
)
def test_zonas_excluidas_nunca_se_atienden(zona, cp):
    assert cobertura.verificar(zona, cp).estado == "fuera_de_zona"


def test_gam_no_se_dispara_con_una_coincidencia_casual():
    # «gamma», «programa»: no es la alcaldía.
    assert cobertura.verificar("colonia Programa Gamma", "03100").estado == "dentro_de_zona"


@pytest.mark.parametrize("zona", ["Lerma", "Toluca centro", "soy de toluca"])
def test_lerma_y_toluca_solo_en_miercoles(zona):
    res = cobertura.verificar(zona)
    assert res.estado == "dentro_de_zona"
    assert (res.dia_restringido, res.dia_nombre) == (2, "miércoles")


def test_la_colonia_sola_no_basta():
    res = cobertura.verificar("Del Valle")
    assert res.estado == "requiere_mas_datos"


def test_con_codigo_postal_se_resuelve():
    assert cobertura.verificar("Del Valle", "03100").estado == "dentro_de_zona"
    # El CP también puede venir dentro del texto de la zona.
    assert cobertura.verificar("Del Valle 03100").estado == "dentro_de_zona"
    assert cobertura.verificar("Monterrey", "64000").estado == "fuera_de_zona"


# --------------------------------------------------------------- diagnóstico ---

LEAD = ["tengo cucarachas", "son chiquitas, café claro", "salen detrás del refri"]


def _senal(clave, cita):
    return {"senal": clave, "cita": cita}


def test_cucaracha_alemana_necesita_tamano_y_ubicacion():
    d = diagnostico.evaluar(
        "cucaracha",
        [_senal("tamano_chica", "son chiquitas, café claro"),
         _senal("ubicacion_cocina", "salen detrás del refri")],
        mensajes_lead=LEAD,
    )
    assert (d.estado, d.plaga) == ("confirmada", "cucaracha_alemana")


def test_un_solo_dato_nunca_confirma():
    d = diagnostico.evaluar(
        "cucaracha", [_senal("tamano_chica", "son chiquitas")], mensajes_lead=LEAD
    )
    assert d.estado == "faltan_senales"
    assert "cocina" in d.pregunta  # lo siguiente es preguntar la ubicación
    assert not d.atasco


def test_una_senal_que_el_lead_no_escribio_se_rechaza():
    # El modelo «completa» el diagnóstico con algo que nadie dijo.
    d = diagnostico.evaluar(
        "cucaracha",
        [_senal("tamano_chica", "son chiquitas"),
         _senal("ubicacion_cocina", "las veo en la cocina junto a la estufa")],
        mensajes_lead=["tengo cucarachas", "son chiquitas"],
    )
    assert d.estado == "faltan_senales"
    assert [r["senal"] for r in d.rechazadas] == ["ubicacion_cocina"]


def test_rasgos_de_las_dos_especies_no_confirman_ninguna():
    # Chica (alemana) + coladera (americana): se atasca → tarjeta comparativa.
    d = diagnostico.evaluar(
        "cucaracha",
        [_senal("tamano_chica", "chiquitas"), _senal("ubicacion_drenaje", "salen de la coladera")],
        mensajes_lead=["son chiquitas y salen de la coladera"],
    )
    assert d.estado == "faltan_senales"
    assert d.atasco


def test_el_bano_no_distingue_la_especie():
    d = diagnostico.evaluar(
        "cucaracha",
        [_senal("tamano_grande", "son grandes"), _senal("ubicacion_bano", "en el baño")],
        preguntadas=["tamano", "ubicacion"],
        mensajes_lead=["son grandes y salen en el baño"],
    )
    assert d.estado == "faltan_senales"
    assert "además del baño" in d.pregunta


def test_la_eleccion_de_la_tarjeta_solo_vale_si_se_envio():
    propuesta = [_senal("eligio_americana", "se parece a la americana")]
    lead = ["se parece a la americana, la grande"]
    sin = diagnostico.evaluar("cucaracha", propuesta, mensajes_lead=lead)
    assert sin.rechazadas and not sin.senales
    con = diagnostico.evaluar(
        "cucaracha", propuesta + [_senal("tamano_grande", "la grande")],
        mensajes_lead=lead, tarjeta_enviada=True,
    )
    assert (con.estado, con.plaga) == ("confirmada", "cucaracha_americana")


def test_un_si_cuenta_como_cita_si_fue_lo_ultimo_que_dijo():
    d = diagnostico.evaluar(
        "pulgas",
        [_senal("mascotas", "tengo un perro"), _senal("saltan", "sí")],
        mensajes_lead=["tengo un perro y nos pican", "sí"],
        ultimo_bot="¿Has visto que los bichitos saltan?",
    )
    assert d.estado == "confirmada"


@pytest.mark.parametrize("plaga", [p for p, i in catalogo.PLAGAS.items() if "senales" in i])
def test_toda_plaga_identificable_tiene_al_menos_dos_senales(plaga):
    assert len(catalogo.PLAGAS[plaga]["senales"]) >= diagnostico.MIN_SENALES
    for senal in catalogo.PLAGAS[plaga]["senales"].values():
        assert senal["pregunta"].count("?") == 1  # una sola pregunta por mensaje


def test_plagas_que_siempre_van_con_el_dueno():
    assert diagnostico.evaluar("moscas_mosquitos", []).estado == "siempre_dueno"
    assert diagnostico.evaluar("termita_subterranea", []).estado == "siempre_dueno"
    assert diagnostico.evaluar("garrapatas", []).estado == "fuera_de_catalogo"
    assert diagnostico.evaluar("otra", []).estado == "fuera_de_catalogo"


# ------------------------------------------------------------------ precios ---


@pytest.mark.parametrize(
    "plaga, variables, precio",
    [
        ("cucaracha_alemana", {"tipo_inmueble": "casa"}, 1200),
        ("cucaracha_alemana", {"tipo_inmueble": "depto"}, 1100),
        ("cucaracha_alemana", {"tipo_inmueble": "local comercial", "refrigeradores": 4}, 1500),
        ("hormiga", {"tipo_inmueble": "casa", "m2": 120}, 1700),
        ("hormiga", {"tipo_inmueble": "casa", "m2": 200}, 1700),
        ("hormiga", {"tipo_inmueble": "casa", "m2": 201}, 2000),
        ("hormiga", {"tipo_inmueble": "departamento", "m2": 50}, 1300),
        ("hormiga", {"tipo_inmueble": "departamento", "m2": 250}, 2200),
        ("alacran", {"tipo_inmueble": "casa", "m2": 150}, 1800),
        ("alacran", {"tipo_inmueble": "departamento", "m2": 300}, 2500),
        ("arana", {"m2": 100}, 1800),
        ("arana", {"m2": 101}, 2500),
        ("tijerilla", {"m2": 60}, 1000),
    ],
)
def test_precios_del_catalogo(plaga, variables, precio):
    cot = precios.cotizar(plaga, variables)
    assert (cot.estado, cot.precio) == ("ok", precio)
    assert "por visita" in cot.linea_precio
    assert f"${precio:,} MXN" in cot.linea_precio


@pytest.mark.parametrize(
    "plaga, variables",
    [
        ("cucaracha_alemana", {"tipo_inmueble": "local_comercial", "refrigeradores": 5}),
        ("hormiga", {"tipo_inmueble": "casa", "m2": 90}),  # bajo el rango de casa
        ("hormiga", {"tipo_inmueble": "departamento", "m2": 300}),
        ("alacran", {"tipo_inmueble": "casa", "m2": 350}),
        ("arana", {"m2": 250}),
        ("tijerilla", {"m2": 120}),
        ("termita_madera_seca", {}),
        ("termita_subterranea", {}),
        ("moscas_mosquitos", {}),
    ],
)
def test_fuera_de_rango_o_inspeccion_lo_cotiza_el_dueno(plaga, variables):
    cot = precios.cotizar(plaga, variables)
    assert cot.estado == "requiere_dueno"
    assert cot.precio is None and cot.motivo


def test_se_pregunta_un_dato_a_la_vez():
    cot = precios.cotizar("hormiga", {})
    assert (cot.estado, cot.falta) == ("falta", "tipo_inmueble")
    cot = precios.cotizar("hormiga", {"tipo_inmueble": "casa"})
    assert (cot.estado, cot.falta) == ("falta", "m2")
    assert cot.pregunta.count("?") == 1


def test_la_alemana_no_pide_metros():
    # Se cobra por tipo de inmueble: preguntar m² es hacerle perder tiempo al lead.
    assert precios.cotizar("cucaracha_alemana", {"tipo_inmueble": "casa"}).estado == "ok"


def test_local_comercial_pregunta_refrigeradores():
    cot = precios.cotizar("cucaracha_alemana", {"tipo_inmueble": "restaurante"})
    assert (cot.estado, cot.falta) == ("falta", "refrigeradores")


def test_chinches_pregunta_colchones_totales():
    cot = precios.cotizar("chinches", {})
    assert cot.falta == "colchones"
    assert "total" in cot.pregunta.lower() and "toda la casa" in cot.pregunta.lower()


def test_sin_formula_en_el_catalogo_no_se_inventa_precio():
    # Mientras el negocio no dé la fórmula (PENDIENTES), cotiza una persona.
    for plaga, variables in [
        ("cucaracha_americana", {"tipo_inmueble": "casa", "registros": 2, "sanitarios": 4}),
        ("roedores", {"m2": 80}),
        ("chinches", {"colchones": 3, "sillones": 1, "sillas_comedor": 4}),
        ("pulgas", {"colchones": 2, "sillones": 1, "sillas_comedor": 0}),
    ]:
        cot = precios.cotizar(plaga, variables)
        assert cot.estado == "requiere_dueno", plaga
        assert cot.precio is None


def test_americana_cobra_el_cuarto_sanitario_cuando_haya_tarifa_base(monkeypatch):
    regla = catalogo.PLAGAS["cucaracha_americana"]["precio"]
    monkeypatch.setitem(regla, "base", {"casa": 1500, "departamento": 1400, "edificio": 3000})
    tres = precios.cotizar("cucaracha_americana", {"tipo_inmueble": "casa", "registros": 2, "sanitarios": 3})
    cinco = precios.cotizar("cucaracha_americana", {"tipo_inmueble": "casa", "registros": 2, "sanitarios": 5})
    assert tres.precio == 1500
    assert cinco.precio == 1700  # 2 sanitarios adicionales × $100, en cada visita
    assert "en cada visita" in cinco.extras[0]


def test_roedores_las_cajas_las_calcula_el_sistema():
    assert "caja" not in precios.cotizar("roedores", {}).pregunta.lower()
    assert precios.limpiar_variables({"largo": 10, "ancho": 8}) == {"m2": 80}


def test_el_bloque_de_cierre_va_por_visita_y_no_suma():
    cot = precios.cotizar("alacran", {"tipo_inmueble": "casa", "m2": 150})
    bloque = precios.bloque_de_cierre(cot)
    lineas = bloque.splitlines()
    assert lineas[0].startswith("📋")
    assert "Alacrán" in lineas[1]
    assert lineas[2].startswith("🛠️ Tratamiento:")
    assert lineas[3] == "💵 $1,800 MXN por visita (de 100 a 200 m²)"
    assert any("2x1" in l for l in lineas)  # la promo viene del catálogo
    assert "total" not in bloque.lower()
    assert "Se liquida al término de cada visita." in bloque


def test_elegir_en_la_tarjeta_confirma_si_nada_lo_contradice():
    d = diagnostico.evaluar(
        "cucaracha", [_senal("eligio_alemana", "se parece a la alemana")],
        mensajes_lead=["se parece a la alemana"], tarjeta_enviada=True,
    )
    assert (d.estado, d.plaga) == ("confirmada", "cucaracha_alemana")
    # Si lo que ya dijo apunta a la otra especie, la elección sola no alcanza.
    d = diagnostico.evaluar(
        "cucaracha",
        [_senal("tamano_grande", "son grandes"), _senal("ubicacion_drenaje", "salen de la coladera"),
         _senal("eligio_alemana", "se parece a la alemana")],
        mensajes_lead=["son grandes y salen de la coladera", "se parece a la alemana"],
        tarjeta_enviada=True,
    )
    assert d.estado == "faltan_senales"


def test_una_cita_real_que_no_dice_esa_senal_no_cuenta():
    # El caso de la autoprueba: palabras que el lead sí escribió, etiquetadas
    # como algo que no dicen. Así se inventaba un diagnóstico «con citas».
    d = diagnostico.evaluar(
        "cucaracha",
        [_senal("tamano_chica", "pues normales, no sé"),
         _senal("ubicacion_cocina", "pues por todo el depa")],
        mensajes_lead=["pues normales, no sé", "pues por todo el depa"],
    )
    assert d.estado == "faltan_senales" and d.plaga == "cucaracha"
    assert {r["senal"] for r in d.rechazadas} == {"tamano_chica", "ubicacion_cocina"}


@pytest.mark.parametrize(
    "plaga, senal, cita",
    [
        ("cucaracha", "ubicacion_cocina", "en la cocinita"),
        ("roedores", "empaques_roidos", "me mordieron una bolsa de arroz"),
        ("alacran", "escondites", "lo vi en el patio"),
    ],
)
def test_formas_reales_de_decirlo_si_cuentan(plaga, senal, cita):
    d = diagnostico.evaluar(plaga, [_senal(senal, cita)], mensajes_lead=[cita])
    assert senal in d.senales and not d.rechazadas
