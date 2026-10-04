from app.plagas.muebles import muebles_dichos


def test_mensaje_real_de_ethel():
    d = muebles_dichos(["tengo chinche de cama, quiero agendar, tengo 2 colchones, 2 sillon 1 silla secretaria"])
    assert d == {"colchones": 2, "sillones": 2, "sillas_secretariales": 1}


def test_silla_secretarial_completa_y_palabras():
    d = muebles_dichos(["dos colchones, un sillon y 1 silla secretarial"])
    assert d == {"colchones": 2, "sillones": 1, "sillas_secretariales": 1}


def test_ninguna_es_cero_y_lo_ultimo_manda():
    assert muebles_dichos(["ninguna silla de comedor"]) == {"sillas_comedor": 0}
    assert muebles_dichos(["1 colchon", "perdon, son 2 colchones"]) == {"colchones": 2}


def test_numero_suelto_no_se_adivina():
    assert muebles_dichos(["vivo en el 2200", "tengo 3"]) == {}
