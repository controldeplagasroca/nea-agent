"""Lo que el dueño contó en sus audios del 1 de octubre, vuelto prueba.

Dos audios: cómo fallaba su bot anterior («no lleva de la mano», «dice que
manda la cotización y nunca la manda», «a mí nunca me avisa») y qué quiere que
el agente sepa contestar («¿es tóxico?», «¿cuándo puedo volver a entrar?»).
"""
from __future__ import annotations

from typing import Any

import pytest

from app.llm import LlmReply, ToolCall
from app.plagas import candados, catalogo, diagnostico
from app.plagas.aviso import texto_del_aviso
from app.plagas.caso import Caso
from app.plagas.herramientas import bloque_de_tratamiento
from app.state import AppContext, InboundMessage, MemoryStore
from app.turn import run_turn
from selftest.roca.crm_falso import CrmFalso
from tests.conftest import FakeLLM, make_settings

LEAD = "5215511112222"
DUENO = "5215599990000"

ALEMANA = [
    {"senal": "tamano_chica", "cita": "son chiquitas"},
    {"senal": "ubicacion_cocina", "cita": "en la cocina"},
]


def _ctx(llm: FakeLLM, *, agenda: bool = True, crm: dict[str, Any] | None = None, **settings: Any) -> AppContext:
    falso = CrmFalso(identidad=LEAD, perfil={"profile": {"name": "Nea"}, "kb": None},
                     agenda=agenda, **(crm or {}))
    ctx = AppContext(
        settings=make_settings(vertical="plagas", history_window=24, **settings),
        store=MemoryStore(), crm=falso, llm=llm,
    )
    ctx.agenda_enabled = agenda
    return ctx


def _llama(nombre: str, **args: Any) -> LlmReply:
    return LlmReply(content=None, tool_calls=[ToolCall(id=f"c_{nombre}", name=nombre, arguments=args)])


def _dice(texto: str) -> LlmReply:
    return LlmReply(content=texto)


async def _turno(ctx: AppContext, texto: str, n: int = 0, quien: str = LEAD) -> str | None:
    antes = len(ctx.crm.enviados)
    await run_turn(ctx, quien, [InboundMessage(wa_message_id=f"w{n}{texto[:8]}", identity=quien, type="text", text=texto)])
    nuevos = ctx.crm.enviados[antes:]
    return nuevos[-1] if nuevos else None


async def _hasta_plaga_confirmada(llm: FakeLLM, ctx: AppContext) -> str | None:
    llm.replies += [
        _llama("verificar_cobertura", zona="Del Valle", codigo_postal="03100"),
        _llama("identificar_plaga", plaga="cucaracha", senales=ALEMANA),
        _dice("Por lo que me cuentas, es cucaracha alemana."),
    ]
    return await _turno(ctx, "tengo cucarachas, son chiquitas y salen en la cocina. Del Valle 03100", 1)


# ------------------------------------------------ llevar de la mano ---


def test_el_ejemplo_del_dueno_chiquitas_en_la_cocina_y_tambien_en_el_bano():
    """«Son chiquitas, en la cocina… y también en el sanitario»: ya es alemana.

    El baño lo comparten las dos especies: ni la descarta ni obliga a otra
    pregunta cuando el tamaño y la cocina ya apuntan a la misma.
    """
    mensajes = ["no conozco de cucarachas pero las que he visto son chiquitas",
                "detrás del refri y abajo de la licuadora, también en el sanitario"]
    d = diagnostico.evaluar(
        "cucaracha",
        [
            {"senal": "tamano_chica", "cita": "las que he visto son chiquitas"},
            {"senal": "ubicacion_cocina", "cita": "detrás del refri y abajo de la licuadora"},
            {"senal": "ubicacion_bano", "cita": "también en el sanitario"},
        ],
        mensajes_lead=mensajes,
    )
    assert (d.estado, d.plaga) == ("confirmada", "cucaracha_alemana")
    assert d.pregunta == ""


@pytest.mark.parametrize(
    "senal, cita",
    [
        ("tamano_grande", "son de esas voladoras"),
        ("tamano_grande", "las patinadoras, rojizas"),
        ("ubicacion_cocina", "atrás de la licuadora"),
        ("ubicacion_drenaje", "salen de la calle"),
    ],
)
def test_el_vocabulario_del_dueno_cuenta_como_senal(senal, cita):
    d = diagnostico.evaluar("cucaracha", [{"senal": senal, "cita": cita}], mensajes_lead=[cita])
    assert senal in d.senales and d.rechazadas == []


def test_con_un_solo_dato_pregunta_el_otro_dando_las_dos_opciones():
    d = diagnostico.evaluar(
        "cucaracha", [{"senal": "tamano_chica", "cita": "son chiquitas"}],
        mensajes_lead=["son chiquitas"],
    )
    assert d.estado == "faltan_senales"
    # La pregunta ya trae la orientación (cocina vs. coladeras): no es «¿dónde?» a secas.
    assert "cocina" in d.pregunta and "coladeras" in d.pregunta
    assert d.pregunta.count("?") == 1


def test_al_confirmar_la_alemana_primero_va_la_tranquilidad():
    bloque = bloque_de_tratamiento("cucaracha_alemana")
    lineas = bloque.splitlines()
    assert lineas[0].startswith("💚") and "no es por falta de higiene" in lineas[0]
    assert lineas[1].startswith("🛠️") and lineas[2].startswith("🗓️ 2 visitas")
    # Las plagas a las que el dueño no les ha dado esa frase no la inventan.
    assert "💚" not in bloque_de_tratamiento("hormiga")


async def test_el_mensaje_de_confirmacion_conserva_lo_que_dijo_el_lead():
    llm = FakeLLM([
        _llama("verificar_cobertura", zona="Del Valle", codigo_postal="03100"),
        _llama("identificar_plaga", plaga="cucaracha", senales=ALEMANA),
        _dice("Por lo que me cuentas —chiquitas y en la cocina— es cucaracha alemana 🪳 Vamos a resolverlo."),
    ])
    ctx = _ctx(llm)
    texto = await _turno(ctx, "son chiquitas y salen en la cocina, Del Valle 03100", 1)
    assert texto is not None
    # Con la tranquilidad el bloque es más largo: la frase del modelo no se recorta por eso.
    assert texto.startswith("Por lo que me cuentas —chiquitas y en la cocina— es cucaracha alemana 🪳")
    assert "💚" in texto and "🛠️" in texto and texto.count("?") == 1


# ------------------------------------------------- promesas vacías ---


@pytest.mark.parametrize(
    "texto",
    [
        "Sí, voy a revisar y la cotización te la mando.",
        "Claro, en un momento te paso el precio 🙌",
        "Nosotros te avisamos cuando tengamos disponibilidad.",
        "Perfecto, te confirmo en breve el horario.",
        "Déjame checarlo con el equipo.",
        "Permíteme un momento mientras te comunico con un técnico especializado.",
        "Un técnico especializado se comunicará contigo.",
        "Te mando la cotización. ¿Algo más en lo que te pueda ayudar?",
    ],
)
def test_prometer_para_despues_sin_pasar_la_conversacion_es_promesa_vacia(texto):
    assert candados.promesa_vacia(texto)
    faltas = candados.revisar(
        texto, montos_validos=set(), horas_validas=set(), cita_registrada=False,
        se_paso_al_dueno=False,
    )
    assert [(f.clave, f.grave) for f in faltas] == [("promesa_vacia", True)]
    # Con el pase al dueño hecho en este turno, la misma frase es verdad.
    assert candados.revisar(
        texto, montos_validos=set(), horas_validas=set(), cita_registrada=False,
        se_paso_al_dueno=True,
    ) == []


@pytest.mark.parametrize(
    "texto",
    [
        "Te aviso de una vez: por ahora no damos servicio en Ecatepec 😔",
        "Te aviso con gusto: sí damos servicio en la Narvarte ✅",
        "Si prefieres, te comunico con un técnico especializado. ¿Quieres?",
        "Si hubo un problema con algún servicio, dímelo y con gusto te comunico con un técnico especializado.",
        "¿Quieres que te pase el costo del servicio?",
        "Te paso el precio en cuanto me digas el inmueble. ¿Es casa o departamento?",
        "En cuanto cerremos tu cita, te paso con un técnico especializado para que la confirme.",
        "Claro, cuando gustes me avisas 🙌",
    ],
)
def test_avisar_ahora_ofrecer_o_preguntar_no_es_promesa_vacia(texto):
    assert candados.promesa_vacia(texto) == ""


async def test_si_promete_mandar_la_cotizacion_despues_no_sale_y_va_la_pregunta_que_falta():
    llm = FakeLLM()
    ctx = _ctx(llm)
    await _hasta_plaga_confirmada(llm, ctx)
    # Lo que hacía el bot anterior: prometer y no hacer. Reincide en la corrección.
    llm.replies += [
        _dice("¡Claro! Voy a revisar y la cotización te la mando 🙌"),
        _dice("Listo, en un momento te paso el precio."),
    ]
    texto = await _turno(ctx, "sí, han aumentado mucho", 2)
    assert texto is not None
    assert "te la mando" not in texto and "en un momento" not in texto
    assert texto.rstrip().endswith("?")  # el lead siempre se queda con algo que contestar
    assert ctx.crm.handoffs == []
    correccion = next(
        m["content"] for m in llm.calls[-1]["messages"]
        if m["role"] == "system" and "NO se le envió" in str(m["content"])
    )
    assert "prometiste algo para después" in correccion


async def test_te_comunico_con_el_dueno_solo_sale_si_el_pase_ocurre():
    llm = FakeLLM()
    ctx = _ctx(llm)
    await _hasta_plaga_confirmada(llm, ctx)
    llm.replies += [
        _llama("handoff", reason="modelo", nota="Pregunta por el contrato anual para su edificio"),
        _dice("Permíteme un momento mientras te comunico con un técnico especializado 🙌"),
    ]
    texto = await _turno(ctx, "oigan y manejan contratos anuales para todo el edificio?", 2)
    assert texto == "Permíteme un momento mientras te comunico con un técnico especializado 🙌"
    assert ctx.crm.handoffs == ["modelo"]


# ------------------------------------------------ dudas del servicio ---


def test_las_dudas_aprobadas_viajan_en_el_prompt():
    from app.plagas.prompt import chasis
    from app.profile import BusinessProfile

    texto = chasis(BusinessProfile(agent_name="Nea"))
    for clave in ("seguridad", "reingreso", "eficacia"):
        assert catalogo.DUDAS[clave] in texto
    assert "15 a 20 minutos" in texto
    assert "NUNCA DEJES AL LEAD ESPERANDO" in texto


@pytest.mark.parametrize(
    "texto, hallado",
    [
        ("Puedes volver a entrar a las 2 horas.", ["2 horas"]),
        ("Hay que ventilar y regresar hasta después de 4 a 6 horas.", ["4-6 horas"]),
        ("Lo ideal es salir de casa un par de horas.", ["un par de horas"]),
        ("Tranquilo, el producto es orgánico y no huele.", ["organic", "no huele"]),
        ("No es tóxico, es 100% seguro para mascotas.", ["no es toxic", "100% segur"]),
        ("Es seguro para tus perritos y para los niños.", ["seguro para tus perritos"]),
    ],
)
def test_seguridad_o_tiempos_que_el_negocio_no_aprobo(texto, hallado):
    encontrados = candados.seguridad_inventada(texto)
    assert all(any(h in e for e in encontrados) for h in hallado), encontrados
    assert "seguridad_inventada" in [
        f.clave for f in candados.revisar(
            texto, montos_validos=set(), horas_validas=set(), cita_registrada=False
        )
    ]


@pytest.mark.parametrize(
    "texto",
    [
        "Los productos que usamos no ponen en riesgo la salud de tu familia, y pueden volver a entrar en 15 a 20 minutos 🙌",
        "Sí es efectivo: son 2 visitas, entre 8 y 10 días entre una y otra.",
        "La 2ª visita va de 8 a 10 días después de la primera.",
        "Para confirmarte al 100% si llegamos, ¿me pasas tu código postal?",
        "Reingresan a los 20 minutos de la aplicación.",
    ],
)
def test_lo_aprobado_y_los_plazos_del_tratamiento_no_se_confunden(texto):
    assert candados.seguridad_inventada(texto) == []


@pytest.mark.parametrize(
    "texto, plaga, inventada",
    [
        ("Claro, el servicio incluye garantía de 6 meses.", "cucaracha_alemana", True),
        ("Sí, todos nuestros trabajos están garantizados.", "hormiga", True),
        ("La garantía la define un técnico especializado; si quieres te comunico con él.", "hormiga", False),
        ("Ese punto no lo manejo por aquí: no te puedo prometer una garantía.", "hormiga", False),
        ("¿Preguntas por la garantía de un servicio que ya te hicimos?", None, False),
        ("Permíteme un momento mientras te comunico con un técnico especializado para que revise tu garantía.", None, False),
        ("Incluye garantía de 3 años.", "termita_madera_seca", False),  # esa sí es del catálogo
        ("Cuento todos los colchones porque no se puede dar garantía de uno que no se trató.", "chinches", False),
    ],
)
def test_garantia_solo_la_del_catalogo(texto, plaga, inventada):
    assert candados.garantia_inventada(texto, plaga) is inventada


# --------------------------------------------------- aviso al dueño ---


def test_el_aviso_lleva_lo_que_el_dueno_necesita_para_aprobar():
    caso = Caso(
        cobertura={"estado": "dentro_de_zona", "zona": "Del Valle", "cp": "03100"},
        plaga="cucaracha_alemana", variables={"tipo_inmueble": "casa"},
        cotizacion={"linea": "$1,200 MXN por visita (casa)"},
        direccion={"calle": "Heriberto Frías", "numero_exterior": "1125", "colonia": "Del Valle",
                   "alcaldia_municipio": "Benito Juárez", "referencia": "portón negro"},
        cita={"label": "sábado 3 de octubre, 09:00"}, escalado="Solicitud de visita: sábado 3",
    )
    texto = texto_del_aviso(caso, "cliente", "Ana", "525511112222")
    assert "Ana · 525511112222" in texto
    assert "Pide visita: sábado 3 de octubre, 09:00 — pendiente de que la confirmes" in texto
    assert "Cucaracha alemana" in texto and "$1,200 MXN por visita (casa)" in texto
    assert "Heriberto Frías 1125" in texto and "tipo_inmueble: casa" in texto


async def test_la_cotizacion_manual_le_llega_al_dueno_con_los_datos():
    llm = FakeLLM([
        _llama("verificar_cobertura", zona="Condesa", codigo_postal="06140"),
        _llama("identificar_plaga", plaga="cucaracha", senales=ALEMANA),
        _dice("Es cucaracha alemana."),
    ])
    ctx = _ctx(llm, crm={"dueno": "525599990000"}, aviso_dueno_wa=DUENO)
    await _turno(ctx, "restaurante en la condesa 06140, son chiquitas y salen en la cocina", 1)
    llm.replies += [_llama("cotizar", tipo_inmueble="local_comercial", refrigeradores=6), _dice("…")]
    texto = await _turno(ctx, "cuánto cuesta? es un restaurante con 6 refrigeradores", 2)
    # Al lead: que ya se le pasaron sus datos al dueño (y es verdad).
    assert texto is not None and "Ya le pasé tus datos" in texto
    assert ctx.crm.handoffs == ["modelo"]
    # Al dueño: un mensaje con qué es, qué datos dio y por qué no se cotizó por chat.
    assert len(ctx.crm.avisos) == 1
    aviso = ctx.crm.avisos[0]
    assert "Nea te pasó una conversación" in aviso
    assert "Cotización manual — Cucaracha alemana" in aviso
    assert "refrigeradores: 6" in aviso and "Condesa" in aviso


async def test_sin_ventana_abierta_el_aviso_no_sale_y_el_turno_no_se_entera():
    llm = FakeLLM([_llama("handoff", reason="cliente"), _dice("Permíteme un momento mientras te comunico con un técnico especializado.")])
    ctx = _ctx(llm, crm={"dueno": "525599990000", "ventana_dueno": False}, aviso_dueno_wa=DUENO)
    texto = await _turno(ctx, "quiero hablar con una persona por favor", 1)
    assert texto is not None and ctx.crm.handoffs == ["cliente"]
    assert ctx.crm.avisos == []


async def test_sin_aviso_configurado_no_se_le_escribe_a_nadie_mas():
    llm = FakeLLM([_llama("handoff", reason="cliente"), _dice("Permíteme un momento mientras te comunico con un técnico especializado.")])
    ctx = _ctx(llm, crm={"dueno": "525599990000"})
    await _turno(ctx, "quiero hablar con una persona por favor", 1)
    assert ctx.crm.handoffs == ["cliente"] and ctx.crm.avisos == []


async def test_al_dueno_no_se_le_atiende_como_a_un_lead():
    llm = FakeLLM([_dice("¡Hola! ¿En qué colonia estás?")])
    ctx = _ctx(llm, crm={"dueno": "525599990000"}, aviso_dueno_wa=DUENO)
    assert await _turno(ctx, "hola", 1, quien=DUENO) is None
    assert llm.calls == []


# ------------------------------- lo que salió al leer los transcripts ---


@pytest.mark.parametrize(
    "texto",
    [
        "Tranquilo, no pone en riesgo tu salud. ¿Qué tamaño tienen más o menos, como 1 a 2 cm o de 4 a 5 cm?",
        "Claro. ¿De qué color son?",
        "Entiendo. ¿Dónde las has visto más?",
        "Va. ¿En qué parte las ves más: en la cocina o cerca de coladeras, drenajes o el patio?",
    ],
)
def test_con_la_plaga_confirmada_no_se_vuelve_a_preguntar_como_es(texto):
    assert candados.repregunta_identificacion(texto, "cucaracha_alemana")
    claves = [f.clave for f in candados.revisar(
        texto, montos_validos=set(), horas_validas=set(), cita_registrada=False,
        plaga="cucaracha_alemana",
    )]
    assert "repregunta_identificacion" in claves
    # Si en este turno la herramienta pidió otra pregunta (describe OTRA plaga), sí toca.
    assert "repregunta_identificacion" not in [f.clave for f in candados.revisar(
        texto, montos_validos=set(), horas_validas=set(), cita_registrada=False,
        plaga="cucaracha_alemana", identificacion_abierta=True,
    )]


@pytest.mark.parametrize(
    "texto",
    [
        "¿Has notado si han aumentado estos días?",
        "¿Es casa, departamento o local comercial?",
        "¿Quieres que te diga cuánto costaría el tratamiento?",
        "¿Te gustaría que agendemos tu primera visita?",
    ],
)
def test_las_preguntas_que_si_tocan_despues_de_confirmar(texto):
    assert candados.repregunta_identificacion(texto, "cucaracha_alemana") == ""


def test_no_se_presenta_dos_veces():
    previos = ["¡Hola! Soy Nea, el agente de IA de Control de Plagas ROCA 👋 ¿En qué colonia estás?"]
    texto = "¡Hola! Soy Nea, el agente de IA de Control de Plagas ROCA 👋 Claro que te ayudo: no ponen en riesgo tu salud."
    assert candados.sin_resaludo(texto, previos) == "Claro que te ayudo: no ponen en riesgo tu salud."
    assert candados.sin_resaludo(texto, []) == texto  # el primer mensaje sí saluda
    sigue = "Hola de nuevo por aquí, claro que te ayudo con eso."
    assert candados.sin_resaludo(sigue, previos) == sigue


@pytest.mark.parametrize(
    "texto, pide",
    [
        ("cuánto cuesta?", True),
        ("y en cuánto sale", True),
        ("a cómo la fumigada", True),
        ("qué precio tiene", True),
        ("y el servicio tiene garantía? de cuánto tiempo?", False),
        ("cuánto tarda la visita?", False),
        ("sale de la coladera", False),
        ("vale, gracias", False),
    ],
)
def test_pedir_precio_no_es_cualquier_cuanto(texto, pide):
    assert candados.pide_precio(texto) is pide


async def test_verificar_otra_vez_la_misma_zona_no_reinicia_la_conversacion():
    llm = FakeLLM()
    ctx = _ctx(llm)
    await _hasta_plaga_confirmada(llm, ctx)
    llm.replies += [
        _llama("verificar_cobertura", zona="Del Valle", codigo_postal="03100"),
        _dice("Los productos no ponen en riesgo la salud de quienes viven ahí 🙌 ¿Quieres que te diga cuánto costaría?"),
    ]
    texto = await _turno(ctx, "oye y eso no es tóxico?", 2)
    assert texto is not None and texto.startswith("Los productos no ponen en riesgo")
    resultado = next(
        str(m["content"]) for m in reversed(llm.calls[-1]["messages"]) if m["role"] == "tool"
    )
    assert "ya_verificada" in resultado and "NO se lo repitas" in resultado


async def test_casa_dicha_al_empezar_una_frase_si_cuenta_para_el_precio():
    llm = FakeLLM([
        _llama("verificar_cobertura", zona="Del Valle", codigo_postal="03100"),
        _llama("identificar_plaga", plaga="cucaracha", senales=ALEMANA),
        _dice("Es cucaracha alemana."),
    ])
    ctx = _ctx(llm)
    await _turno(ctx, "son chiquitas y salen en la cocina, detrás del refri. Casa en la del valle, cp 03100", 1)
    llm.replies += [_llama("cotizar", tipo_inmueble="casa"), _dice("…")]
    texto = await _turno(ctx, "cuánto cuesta?", 2)
    assert texto is not None and "$1,200 MXN por visita (casa)" in texto


async def test_la_frase_del_modelo_no_repite_la_tranquilidad_ni_adorna():
    llm = FakeLLM([
        _llama("verificar_cobertura", zona="Del Valle", codigo_postal="03100"),
        _llama("identificar_plaga", plaga="cucaracha", senales=ALEMANA),
        _dice("Por lo que me cuentas —chiquitas y en la cocina— es cucaracha alemana 🪳 No te preocupes, es de las más comunes y se atiende muy bien."),
    ])
    ctx = _ctx(llm)
    texto = await _turno(ctx, "son chiquitas y salen en la cocina, Del Valle 03100", 1)
    assert texto is not None
    assert texto.count("No te preocupes") == 1  # la del servidor
    assert "más comunes" not in texto
    assert texto.startswith("Por lo que me cuentas —chiquitas y en la cocina— es cucaracha alemana 🪳")


async def test_los_metros_que_el_lead_ya_dijo_no_se_vuelven_a_preguntar():
    llm = FakeLLM([
        _llama("verificar_cobertura", zona="Roma Norte", codigo_postal="06700"),
        _llama("identificar_plaga", plaga="hormiga", senales=[
            {"senal": "fila_visible", "cita": "hormigas en fila"},
            {"senal": "constancia", "cita": "todos los días"},
        ]),
        _dice("Es hormiga común."),
    ])
    ctx = _ctx(llm)
    await _turno(ctx, "tengo hormigas en fila en la cocina todos los días, vivo en un depa de 70 metros en la roma norte, cp 06700", 1)
    # El modelo llama cotizar SIN datos: el servidor usa lo que el lead escribió.
    llm.replies += [_llama("cotizar"), _dice("…")]
    texto = await _turno(ctx, "sí, dime el costo", 2)
    assert texto is not None and "$1,300 MXN por visita (departamento de 50 a 100 m²)" in texto


@pytest.mark.parametrize(
    "mensajes, esperado",
    [
        (["vivo en un depa de 70 metros"], 70.0),
        (["son como 150 m2"], 150.0),
        (["unos 90 mts"], 90.0),
        (["el área es de 10 metros de largo por 8 de ancho"], None),  # medidas: no se adivina
        (["mide 10x8"], None),
        (["estoy a 50 metros del metro Xola"], None),  # distancia
        (["la casa es de 200 metros", "pero el patio son 60 metros"], None),  # dos cifras
        (["tengo hormigas"], None),
    ],
)
def test_m2_dicho(mensajes, esperado):
    from app.plagas.herramientas import RuntimeDePlagas

    runtime = RuntimeDePlagas.__new__(RuntimeDePlagas)
    runtime._mensajes_lead = mensajes
    assert runtime.m2_dicho() == esperado


def test_la_frase_de_confirmacion_no_se_corta_en_una_abreviatura():
    assert candados.sin_caracteres_raros("El　Ing. Leopoldo") == "El Ing. Leopoldo"
    assert candados._trozos("Te comunico con el Ing. Leopoldo para que revise tu garantía.") == [
        "Te comunico con el Ing Leopoldo para que revise tu garantía"
    ]


# ------------------------------ una palabra negada no es una señal ---


@pytest.mark.parametrize(
    "senal, cita, cuenta",
    [
        ("tamano_chica", "se me hacen normales, ni chicas ni grandes", False),
        ("tamano_grande", "se me hacen normales, ni chicas ni grandes", False),
        ("tamano_chica", "no son chiquitas", False),
        ("ubicacion_cocina", "no las veo en la cocina", False),
        ("ubicacion_cocina", "en la cocina nunca, solo en el patio", False),
        ("ubicacion_drenaje", "en la cocina nunca, solo en el patio", True),
        ("tamano_chica", "no sé, son chiquitas", True),
        ("tamano_chica", "no sé pero son chiquitas", True),
        ("ubicacion_cocina", "no conozco de cucarachas pero salen en la cocina", True),
    ],
)
def test_una_palabra_negada_no_cuenta_como_senal(senal, cita, cuenta):
    d = diagnostico.evaluar("cucaracha", [{"senal": senal, "cita": cita}], mensajes_lead=[cita])
    assert (senal in d.senales) is cuenta


def test_ni_chicas_ni_grandes_mas_cocina_no_confirma_nada():
    """El caso que salió en la autoprueba: terminó confirmando la alemana."""
    mensajes = ["no sé la verdad, se me hacen normales, ni chicas ni grandes",
                "por todo el depa, cocina, baño, recamara"]
    d = diagnostico.evaluar(
        "cucaracha",
        [
            {"senal": "tamano_chica", "cita": "se me hacen normales, ni chicas ni grandes"},
            {"senal": "tamano_grande", "cita": "se me hacen normales, ni chicas ni grandes"},
            {"senal": "ubicacion_cocina", "cita": "por todo el depa, cocina"},
        ],
        preguntadas=["tamano", "ubicacion", "comportamiento_1", "comportamiento_2"],
        mensajes_lead=mensajes,
    )
    assert d.estado == "faltan_senales" and d.atasco  # toca la tarjeta comparativa
    assert list(d.senales) == ["ubicacion_cocina"]


def test_rasgos_de_las_dos_especies_no_confirman_por_mayoria():
    mensajes = ["son chiquitas, salen en la cocina y también en el patio"]
    senales = [
        {"senal": "tamano_chica", "cita": "son chiquitas"},
        {"senal": "ubicacion_cocina", "cita": "salen en la cocina"},
        {"senal": "ubicacion_drenaje", "cita": "también en el patio"},
    ]
    d = diagnostico.evaluar("cucaracha", senales, mensajes_lead=mensajes)
    assert d.estado == "faltan_senales"
    # Tras la tarjeta, lo que el lead elige sí desempata.
    mensajes.append("se parece a la alemana, la chica")
    d = diagnostico.evaluar(
        "cucaracha", senales + [{"senal": "eligio_alemana", "cita": "se parece a la alemana, la chica"}],
        mensajes_lead=mensajes, tarjeta_enviada=True,
    )
    assert (d.estado, d.plaga) == ("confirmada", "cucaracha_alemana")


# ------------------ antes del respaldo: quitar solo la frase que miente ---


async def test_si_reincide_se_le_quita_la_frase_mala_y_lo_demas_si_sale():
    """«$2,400 en total… ¿y no dan garantía?»: se va el total, se queda lo de la garantía."""
    llm = FakeLLM()
    ctx = _ctx(llm)
    await _hasta_plaga_confirmada(llm, ctx)
    llm.replies += [_llama("cotizar", tipo_inmueble="casa"), _dice("…")]
    await _turno(ctx, "cuánto cuesta? es una casa", 2)
    llm.replies += [
        _dice("Sí, serían $2,400 en total por las dos visitas. La garantía la define un técnico especializado."),
        _dice(
            "Entiendo que $2,400 suena fuerte. Son $1,200 MXN por visita y se liquida al "
            "término de cada una. Lo de la garantía lo define un técnico especializado: si quieres, "
            "te comunico con él."
        ),
    ]
    texto = await _turno(ctx, "mm, $2,400 en total... no me dan ninguna garantia por si regresan?", 3)
    assert texto is not None
    assert "2,400" not in texto
    assert "$1,200 MXN por visita" in texto
    assert "garantía lo define un técnico especializado" in texto  # no se perdió la respuesta


async def test_si_al_podar_no_queda_nada_util_va_el_respaldo():
    llm = FakeLLM()
    ctx = _ctx(llm)
    await _hasta_plaga_confirmada(llm, ctx)
    llm.replies += [_llama("cotizar", tipo_inmueble="casa"), _dice("…")]
    await _turno(ctx, "cuánto cuesta? es una casa", 2)
    llm.replies += [_dice("Serían $2,400 en total 😊"), _dice("En total $2,400.")]
    texto = await _turno(ctx, "y en total cuánto sería?", 3)
    assert texto is not None and "2,400" not in texto
    assert texto.startswith("Te lo confirmo: $1,200 MXN por visita (casa).")


# --------------------------- lo que salió en la pasada completa final ---


@pytest.mark.parametrize(
    "texto, plaga, ajeno",
    [
        ("Para darte el precio exacto, ¿es casa o departamento, y de más o menos cuántos metros?", "cucaracha_alemana", "m2"),
        ("¿Cuántos colchones hay en la casa?", "cucaracha_alemana", "colchones"),
        ("¿Cuántos baños tiene tu casa?", "hormiga", "sanitarios"),
        ("¿Es casa, departamento o local comercial?", "cucaracha_alemana", ""),
        ("¿Cuántos refrigeradores o congeladores hay en el local?", "cucaracha_alemana", ""),
        ("¿Cuántos metros cuadrados son, más o menos, los que hay que tratar?", "hormiga", ""),
        ("¿Cuántos colchones hay en total en toda la casa?", "chinches", ""),
        ("El depa de 70 metros ya me sirve. ¿Quieres que te diga cuánto costaría?", "cucaracha_alemana", ""),
    ],
)
def test_no_se_pregunta_un_dato_que_el_precio_de_esa_plaga_no_usa(texto, plaga, ajeno):
    assert candados.pregunta_dato_ajeno(texto, plaga) == ajeno


@pytest.mark.parametrize(
    "texto, ajeno",
    [
        ("oye de pasada, me das una receta rápida de pozole rojo?", True),
        ("escríbeme un poema para mi novia", True),
        ("me ayudas con mi tarea de mate?", True),
        ("hay alguna receta casera para las cucarachas?", False),
        ("te cuento, el problema es en la cocina", False),
        ("me das un resumen de la cotización?", False),
        ("cómo se hace el tratamiento?", False),
    ],
)
def test_encargo_ajeno(texto, ajeno):
    assert candados.encargo_ajeno(texto) is ajeno


async def test_si_cumple_una_receta_no_sale_y_el_turno_lleva_la_alerta():
    receta = (
        "Ahí te va rápido 😄: cueces el maíz, cueces el cerdo con ajo y cebolla, mueles chile "
        "guajillo y ancho con especias, lo cuelas a la olla, añades el maíz, dejas que hierva "
        "20 minutos y listo, con lechuga, orégano, chile piquín y un limón al servir.\n\n"
        "Ahora, volviendo al negocio 😅: ¿qué problema de plagas tienes en tu casa o local?"
    )
    llm = FakeLLM([_dice("¡Hola! Soy Nea. ¿Qué problema tienes?"), _dice(receta), _dice(receta)])
    ctx = _ctx(llm)
    await _turno(ctx, "hola", 1)
    texto = await _turno(ctx, "oye de pasada, me das una receta rápida de pozole rojo?", 2)
    assert texto is not None and "guajillo" not in texto and texto.rstrip().endswith("?")
    alertas = [m["content"] for m in llm.calls[1]["messages"] if m["role"] == "system"]
    assert any("no es del negocio" in str(a) for a in alertas)


async def test_si_la_frase_que_se_poda_era_la_pregunta_va_la_del_dato_que_falta():
    llm = FakeLLM()
    ctx = _ctx(llm)
    await _hasta_plaga_confirmada(llm, ctx)
    pide_metros = "¡Va! Ya tengo tu plaga clara: cucaracha alemana, en 2 visitas. ¿Es casa o departamento, y de cuántos metros?"
    llm.replies += [_dice(pide_metros), _dice(pide_metros)]
    texto = await _turno(ctx, "sí, han aumentado", 2)
    assert texto is not None and "metros" not in texto
    assert texto.startswith("¡Va! Ya tengo tu plaga clara")
    assert texto.rstrip().endswith("¿Es casa, departamento o local comercial?")
