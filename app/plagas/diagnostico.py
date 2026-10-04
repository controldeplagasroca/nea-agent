"""¿Qué plaga es? Nunca con un solo dato suelto (especificación, sección 4).

El modelo propone señales; aquí se decide si alcanzan. Cada señal trae la
CITA de lo que escribió el lead, y la cita se busca en sus mensajes: una señal
que el lead nunca dijo no cuenta. Así el modelo no puede «completar» el
diagnóstico de su cabeza.

- Cucarachas: tamaño/color Y ubicación apuntando a la MISMA especie.
- Resto: mínimo dos señales distintas del catálogo de esa plaga.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.plagas import catalogo
from app.plagas.texto import es_afirmacion, normalizar, palabras

MIN_SENALES = 2
RESPALDO_MINIMO = 0.6  # fracción de palabras de la cita que el lead sí escribió

ALEMANA, AMERICANA = "cucaracha_alemana", "cucaracha_americana"


@dataclass
class Diagnostico:
    # confirmada | faltan_senales | sin_preguntas | siempre_dueno | fuera_de_catalogo
    estado: str
    plaga: str | None = None  # clave confirmada (o candidata)
    senales: dict[str, str] = field(default_factory=dict)  # válidas acumuladas
    rechazadas: list[dict[str, str]] = field(default_factory=list)
    nuevas: int = 0
    pregunta: str = ""  # la siguiente pregunta, ya redactada
    senal_preguntada: str = ""
    atasco: bool = False  # cucarachas: la comparación simple no avanzó
    # Cucarachas: el lead describió LAS DOS especies (chicas en un lado, grandes en
    # otro). No se le pide que elija una ni una foto: tiene las dos.
    ambas: bool = False
    avisos: list[str] = field(default_factory=list)


def cita_respaldada(cita: str, mensajes_lead: list[str], hay_imagen: bool = False) -> bool:
    """¿El lead escribió de verdad lo que el modelo dice que escribió?"""
    plana = normalizar(cita)
    if not plana:
        return False
    if hay_imagen and plana.startswith(("foto", "imagen")):
        return True
    tokens = palabras(cita)
    if not tokens:
        # Un «sí» pelón: solo vale si eso fue lo último que contestó.
        return bool(mensajes_lead) and es_afirmacion(mensajes_lead[-1])
    dichas: set[str] = set()
    for m in mensajes_lead:
        dichas.update(palabras(m))
    hallados = sum(1 for t in tokens if t in dichas)
    return hallados / len(tokens) >= RESPALDO_MINIMO


# «Ni chicas ni grandes», «no son chiquitas», «no las veo en la cocina»: la
# palabra está, pero NEGADA. En la autoprueba «se me hacen normales, ni chicas
# ni grandes» contó como «chica» y como «grande», y con un «cocina» después
# quedó confirmada la alemana. («No sé, son chiquitas» sí afirma: el «no» es
# de «no sé» y la coma corta su alcance.)
_NEGADA = re.compile(r"\b(ni|no(?! se\b)|nada|tampoco|sin|nunca)\b[\w ]{0,20}$")
# Y la negación que va después: «en la cocina nunca», «en la cocina no».
_NEGADA_DESPUES = re.compile(r"^\w*\s+(nunca|jamas|tampoco|no(?! se\b))\b")


def _afirma(clave: str, donde: str) -> bool:
    """¿El texto dice esa palabra afirmándola (no «ni chicas», «no son grandes»)?"""
    for m in re.finditer(re.escape(clave), donde):
        if _NEGADA.search(donde[max(0, m.start() - 26):m.start()]):
            continue
        if _NEGADA_DESPUES.search(donde[m.end():m.end() + 16]):
            continue
        return True
    return False


def _tiene_clave(
    senal: dict[str, Any], cita: str, mensajes_lead: list[str], ultimo_bot: str
) -> bool:
    """Auditoría blanda: ¿la cita (o la pregunta que contestó) habla de esa señal?"""
    claves = [normalizar(c) for c in senal.get("claves", [])]
    donde = normalizar(cita)
    if any(_afirma(c, donde) for c in claves):
        return True
    # Contestó «sí» a una pregunta de Nea sobre esa señal.
    if es_afirmacion(cita) or (mensajes_lead and es_afirmacion(mensajes_lead[-1])):
        bot = normalizar(ultimo_bot)
        return any(c in bot for c in claves)
    return False


def _validar(
    catalogo_senales: dict[str, dict[str, Any]],
    propuestas: list[dict[str, Any]],
    previas: dict[str, str],
    mensajes_lead: list[str],
    ultimo_bot: str,
    hay_imagen: bool,
    d: Diagnostico,
    vetadas: frozenset[str] = frozenset(),
) -> None:
    d.senales = {k: v for k, v in previas.items() if k in catalogo_senales}
    for item in propuestas:
        clave = str((item or {}).get("senal") or "").strip()
        cita = str((item or {}).get("cita") or "").strip()
        if clave not in catalogo_senales:
            d.rechazadas.append({"senal": clave, "motivo": "esa señal no es de esta plaga"})
            continue
        if clave in vetadas:
            d.rechazadas.append(
                {"senal": clave, "motivo": "todavía no le has mostrado la comparación"}
            )
            continue
        if not cita_respaldada(cita, mensajes_lead, hay_imagen):
            d.rechazadas.append(
                {
                    "senal": clave,
                    "motivo": "el lead no escribió eso: pregúntaselo en vez de asumirlo",
                }
            )
            continue
        es_foto = hay_imagen and normalizar(cita).startswith(("foto", "imagen"))
        if not es_foto and not _tiene_clave(catalogo_senales[clave], cita, mensajes_lead, ultimo_bot):
            # Las palabras sí las escribió, pero no dicen eso. En la autoprueba:
            # «pues normales, no sé» etiquetado como «chiquitas» y «por todo el
            # depa» como «en la cocina» — un diagnóstico inventado con citas reales.
            d.avisos.append(f"{clave}: la cita «{cita[:60]}» no dice eso")
            d.rechazadas.append(
                {
                    "senal": clave,
                    "motivo": "lo que citaste no dice eso: pregúntaselo en vez de deducirlo",
                }
            )
            continue
        if clave not in d.senales:
            d.nuevas += 1
        d.senales[clave] = cita[:160]


# Dónde las ve, dicho con sus palabras («de la cocina», «salen de la coladera»). El
# baño no se detecta aquí: no distingue la especie.
_LUGARES_CUCARACHA = {
    "ubicacion_cocina": r"\bcocina\b",
    "ubicacion_drenaje": (
        r"\b(coladeras?|drenajes?|alcantarill\w*|registros?|patios?|sotanos?|"
        r"estacionamientos?|cisternas?)\b"
    ),
}


def _detectar_lugar_de_cucaracha(mensajes_lead: list[str], d: Diagnostico) -> None:
    """El lugar que el lead YA dijo, sin depender de que el modelo lo etiquete.

    Caso real (4 oct): «tengo cucaracha de la cocina, de las chiquitas» y el bot
    siguió preguntando en qué parte las ve. Ya lo había dicho.
    """
    for clave, patron in _LUGARES_CUCARACHA.items():
        if clave in d.senales:
            continue
        for mensaje in mensajes_lead:
            plano = normalizar(mensaje)
            hallado = next(
                (
                    m for m in re.finditer(patron, plano)
                    if not _NEGADA.search(plano[max(0, m.start() - 26):m.start()])
                    and not _NEGADA_DESPUES.search(plano[m.end():m.end() + 16])
                ),
                None,
            )
            if hallado is not None:
                d.senales[clave] = mensaje.strip()[:160]
                d.nuevas += 1
                break


def _detectar(
    catalogo_senales: dict[str, dict[str, Any]], mensajes_lead: list[str], d: Diagnostico
) -> None:
    """Indicios que el lead YA dijo, reconocidos por el servidor.

    No se depende de cómo los etiquete el modelo: en la prueba de chinches el
    cliente contó manchas y piquetes y, aun así, el bot le siguió preguntando
    porque una de las dos etiquetas no pasó. Solo cuentan señales con `detecta`
    (un patrón sobre lo que el lead escribió) y no negadas («no he visto chinches»).
    """
    for clave, senal in catalogo_senales.items():
        patron = senal.get("detecta")
        if not patron or clave in d.senales:
            continue
        for mensaje in mensajes_lead:
            plano = normalizar(mensaje)
            hallado = next(
                (
                    m for m in re.finditer(patron, plano)
                    if not _NEGADA.search(plano[max(0, m.start() - 26):m.start()])
                ),
                None,
            )
            if hallado is not None:
                d.senales[clave] = mensaje.strip()[:160]
                d.nuevas += 1
                break


def _cucaracha(d: Diagnostico, preguntadas: list[str]) -> Diagnostico:
    cat = catalogo.CUCARACHA_SENALES
    # Dijo que las hay chicas Y grandes y en dos lugares distintos («en la cocina
    # chiquita y en el baño grandes»): son las dos especies. Antes esto no
    # confirmaba ninguna, se le mostraba la comparación, se le pedía una foto y
    # la conversación terminaba pasada a una persona sin resolver nada.
    ubicaciones = {k for k in d.senales if cat[k]["tipo"] == "ubicacion"}
    if "tamano_chica" in d.senales and "tamano_grande" in d.senales and len(ubicaciones) >= 2:
        d.estado, d.plaga, d.ambas = "confirmada", ALEMANA, True
        return d
    tipos: dict[str, set[str]] = {ALEMANA: set(), AMERICANA: set()}
    hay_tamano = hay_ubicacion = False
    for clave in d.senales:
        info = cat[clave]
        hay_tamano |= info["tipo"] == "tamano"
        hay_ubicacion |= info["tipo"] == "ubicacion" and info["especie"] is not None
        if info["especie"]:
            tipos[info["especie"]].add(info["tipo"])
            if info["tipo"] == "eleccion":
                # Elegir en la tarjeta es reconocer a la vez el tamaño/color y
                # el lugar que la tarjeta describe juntos: vale por dos señales,
                # salvo que lo que ya dijo apunte a la otra especie.
                tipos[info["especie"]].add("descripcion_de_la_tarjeta")
    a, b = len(tipos[ALEMANA]), len(tipos[AMERICANA])
    # Rasgos de las dos especies no confirman ninguna por mayoría: «chiquitas,
    # en la cocina… y también en el patio» puede ser las dos. Solo la elección
    # en la tarjeta desempata (el lead ya vio las dos descritas y escogió).
    # El comportamiento («vuelan», «se esconden y hay muchas juntas») también
    # desempata, cuando solo una de las dos lo tiene a su favor.
    for propia, otra, n, m in ((ALEMANA, AMERICANA, a, b), (AMERICANA, ALEMANA, b, a)):
        desempata = (
            "eleccion" in tipos[propia]
            or ("comportamiento" in tipos[propia] and "comportamiento" not in tipos[otra])
        )
        if n >= MIN_SENALES and n > m and (m == 0 or desempata):
            d.estado, d.plaga = "confirmada", propia
            return d

    d.estado, d.plaga = "faltan_senales", "cucaracha"
    # La comparación simple: primero tamaño, luego ubicación; cada una se
    # pregunta UNA vez. El baño no distingue, así que tiene su repregunta.
    if not hay_tamano and "tamano" not in preguntadas:
        d.pregunta, d.senal_preguntada = catalogo.PREGUNTA_CUCARACHA_TAMANO, "tamano"
    elif not hay_ubicacion and "ubicacion" not in preguntadas:
        d.pregunta, d.senal_preguntada = catalogo.PREGUNTA_CUCARACHA_UBICACION, "ubicacion"
    elif (
        not hay_ubicacion
        and "ubicacion_bano" in d.senales
        and "ubicacion_extra" not in preguntadas
    ):
        d.pregunta = (
            "Ya casi lo tengo, solo me falta un dato: además del baño, "
            "¿las has visto en la cocina o cerca de coladeras o el patio?"
        )
        d.senal_preguntada = "ubicacion_extra"
    else:
        # Tamaño y lugar no cierran en una especie (no supo contestar, o los datos
        # apuntan a las dos): se sigue por COMPORTAMIENTO, no por foto (muchas salen
        # borrosas y ni un experto puede decidir con ellas).
        for clave, pregunta in catalogo.PREGUNTAS_CUCARACHA_COMPORTAMIENTO:
            if clave not in preguntadas:
                d.pregunta, d.senal_preguntada = pregunta, clave
                return d
        # Ya se preguntó todo: toca la tarjeta comparativa, que la garantiza el servidor.
        d.atasco = True
    return d


def evaluar(
    plaga: str,
    propuestas: list[dict[str, Any]] | None,
    *,
    previas: dict[str, str] | None = None,
    preguntadas: list[str] | None = None,
    mensajes_lead: list[str] | None = None,
    ultimo_bot: str = "",
    hay_imagen: bool = False,
    tarjeta_enviada: bool = False,
) -> Diagnostico:
    plaga = normalizar(plaga).replace(" ", "_")
    propuestas = [p for p in (propuestas or []) if isinstance(p, dict)]
    previas = dict(previas or {})
    preguntadas = list(preguntadas or [])
    mensajes_lead = list(mensajes_lead or [])
    d = Diagnostico(estado="faltan_senales")

    if plaga.startswith("cucaracha"):
        vetadas = (
            frozenset()
            if tarjeta_enviada
            else frozenset({"eligio_alemana", "eligio_americana"})
        )
        _validar(
            catalogo.CUCARACHA_SENALES, propuestas, previas, mensajes_lead,
            ultimo_bot, hay_imagen, d, vetadas,
        )
        _detectar_lugar_de_cucaracha(mensajes_lead, d)
        return _cucaracha(d, preguntadas)

    info = catalogo.PLAGAS.get(plaga)
    if info is None:
        d.estado = "fuera_de_catalogo"
        return d
    d.plaga = plaga
    if info.get("siempre_dueno"):
        d.estado = "siempre_dueno"
        return d

    senales = info["senales"]
    _validar(senales, propuestas, previas, mensajes_lead, ultimo_bot, hay_imagen, d)
    _detectar(senales, mensajes_lead, d)
    if len(d.senales) >= MIN_SENALES:
        d.estado = "confirmada"
        return d
    for clave, s in senales.items():
        if s.get("no_preguntar"):
            continue  # cuenta si el lead la dice solo, pero no se le pregunta
        if clave not in d.senales and clave not in preguntadas:
            d.pregunta, d.senal_preguntada = s["pregunta"], clave
            return d
    d.estado = "sin_preguntas"
    return d
