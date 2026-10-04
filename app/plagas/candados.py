"""Candados: lo que se revisa del texto del modelo ANTES de que salga a WhatsApp.

La experiencia del negocio (especificación, sección 15): una regla de prompt
(«nunca digas un precio que no venga de cotizar») se cumple casi siempre, y el
«casi» es dinero mal comunicado. Aquí cada regla que importa se verifica con
código sobre el texto ya escrito.

Tres niveles, del más barato al más caro:
1. REPARAR sin preguntarle a nadie lo que tiene arreglo mecánico (dos signos
   de interrogación, un párrafo que ya se le había enviado al lead).
2. Pedirle al modelo UNA corrección, diciéndole qué regla rompió.
3. Si la corrección tampoco pasa y la falta es grave, sale un texto seguro
   armado por el servidor (app/plagas/turno.py).

También viven aquí los detectores deterministas de lo que el modelo cuenta
mal entre turnos: cliente recurrente y sondeo de «qué modelo eres».
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.plagas import catalogo
from app.plagas.texto import normalizar, palabras

MAX_CARACTERES = 480  # ≈ 3-4 líneas de WhatsApp (el tope del negocio es ~400)
MAX_LINEAS = 7  # con texto; una lista de 3 horarios + saludo + pregunta cabe


@dataclass(frozen=True)
class Falta:
    clave: str
    grave: bool
    correccion: str  # lo que se le dice al modelo para que lo arregle
    detalle: str = ""  # qué se encontró (para la bitácora de la autoprueba)


# --------------------------------------------------- caracteres e idioma ---

# GLM a veces suelta caracteres chinos a media frase («dan mucho可达tic»).
_RAROS = re.compile(r"[　-ヿ㐀-鿿가-힯＀-￯]+")
_INGLES = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|january|february|"
    r"march|april|june|july|august|september|october|november|december)\b",
    re.I,
)


def sin_caracteres_raros(texto: str) -> str:
    """Quita los caracteres de otros alfabetos que el modelo cuela por error."""
    # El espacio ancho (U+3000) es un espacio: quitarlo pegaba «El Ing.» en «ElIng.».
    texto = (texto or "").replace("　", " ")
    return re.sub(r"[ \t]{2,}", " ", _RAROS.sub("", texto))


# ------------------------------------------------------------------ dinero ---

_MONTO = re.compile(
    r"\$\s?(\d{1,3}(?:[,.]\d{3})+|\d+)"  # $1,200 · $ 1200
    r"|(\d{1,3}(?:[,.]\d{3})+|\d{3,6})\s*(?:pesos|mxn|varos)\b"  # 1,200 pesos
    r"|\b(\d{1,3}[,.]\d{3})\b(?=[^\n]{0,24}\bvisita)",  # 1,200 por visita
    re.I,
)


def montos(texto: str) -> set[int]:
    """Las cantidades de dinero que aparecen en un texto."""
    out: set[int] = set()
    for m in _MONTO.finditer(texto or ""):
        crudo = next(g for g in m.groups() if g)
        try:
            out.add(int(re.sub(r"[,.]", "", crudo)))
        except ValueError:
            continue
    return out


# ------------------------------------------------------------------- horas ---

_HORA = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


def horas(texto: str) -> set[tuple[int, int]]:
    """Las horas de un texto como (hora en reloj de 12, minutos).

    En reloj de 12 a propósito: el modelo escribe «9:00», «09:00», «4:00 pm» o
    «16:00» para el mismo horario, y todas son la hora que se ofreció.
    """
    return {(int(m.group(1)) % 12, int(m.group(2))) for m in _HORA.finditer(texto or "")}


# ------------------------------------------------------- frases prohibidas ---

_CALL_CENTER = re.compile(
    r"entiendo su consulta|proceder[eé] a|estimad[oa] cliente|"
    r"con gusto le atiendo|su solicitud ha sido|le informo que",
    re.I,
)
_ORTOGRAFIA = re.compile(r"\besque\b|\bhechad[oa]s?\b", re.I)
_JUZGA_RESPUESTA = re.compile(
    r"\bambigu[oa]s?\b|no (es|fue|me queda) (muy )?clar[oa]|respuesta (poco|no) clara",
    re.I,
)
_TECNICO = re.compile(
    r"\btranscrip|\bmarcadores?\b|\badjunto\b|\bherramientas?\b|\bfunci[oó]n\b|"
    r"\bsistema\b|\bexpediente\b|\bbase de datos\b|\bprompt\b|"
    r"verificar_cobertura|identificar_plaga|\bcotizar\(|propose_slots|book_session|handoff",
    re.I,
)
_PROVEEDOR = re.compile(
    r"\bopenai\b|\bchatgpt\b|\bgpt[- ]?\d|\bclaude\b|\banthropic\b|\bgemini\b|"
    r"\bglm\b|\bzhipu\b|\bz\.ai\b|\bdeepseek\b|\bopenrouter\b|modelo de lenguaje",
    re.I,
)
# Mientras la visita esté pendiente de aprobación, jamás «ya quedó». Con
# acento a propósito: «agendé» es un hecho; «¿quieres que te agende?» no.
_CITA_HECHA = re.compile(
    r"(cita|visita|servicio|fumigaci[oó]n)[^.\n?¿]{0,40}\b(qued[oó]|est[aá]|ha quedado)\s+"
    r"(agendad|confirmad|reservad|programad|apartad)|"
    r"\b(agendé|reservé|aparté|programé)\b|"
    r"\bya (te|la|lo) (agend[eé]|reserv[eé]|apart[eé]|program[eé])\b|"
    r"\b(qued[oó]|queda|ha quedado) (agendad|confirmad|reservad|programad|separad|apartad)",
    re.I,
)

# -------------------------------------------------------------- tratamiento ---

# Palabras que nombran un MÉTODO. Si el modelo usa una que no está en el
# tratamiento de la plaga confirmada, le está atribuyendo el de otra (en la
# autoprueba: «gel y cebo» para la cucaracha alemana, que lleva polvo).
_METODOS = {
    "polvo": r"\bpolvos?\b",
    "gel": r"\bgel\b",
    "cebo": r"\bcebos?\b",
    "vapor": r"\bvapor\b",
    "calor": r"\bcalor\b",
    "nebulización": r"\bnebuliz",
    "aspersión": r"\baspersi|\brocia",
    "bomba neumática": r"\bbomba neumatica",
    "trampas": r"\btrampas?\b",
    "adhesivos": r"\badhesiv",
    "cajas cebadero": r"\bcebader",
    "barrera": r"\bbarreras?\b",
}
_HABLA_DE_VISITAS = re.compile(r"visita|aplicaci|sesi[oó]n|intervalo|separad", re.I)
_VISITAS = re.compile(
    r"\b(\d+|una|un|dos|tres|cuatro|cinco)\s+(?:sola\s+)?(?:visitas?|aplicaci(?:o|ó)n(?:es)?|sesi(?:o|ó)n(?:es)?)\b",
    re.I,
)
_DIAS = re.compile(r"\b(\d{1,2})(?:\s*(?:a|o|-|y)\s*(\d{1,2}))?\s+d[ií]as\b", re.I)
_NUMERO = {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5}


def _texto_del_tratamiento(plaga: str) -> str:
    info = catalogo.PLAGAS.get(plaga) or {}
    return normalizar(" ".join(
        str(info.get(k) or "") for k in ("procedimiento", "visitas", "contencion", "expectativa")
    ))


def _numeros_de_visitas(texto: str) -> set[int]:
    out = set()
    for m in _VISITAS.finditer(texto):
        crudo = m.group(1).lower()
        out.add(_NUMERO.get(crudo) or int(crudo))
    return out


def tratamiento_ajeno(texto: str, plaga: str | None, dicho_por_el_lead: str = "") -> list[str]:
    """Lo que el texto dice del tratamiento y NO está en el catálogo de esa plaga.

    Lo que el lead mismo dijo no cuenta («salen más desde que empezó el
    calor»): repetirle sus palabras no es atribuirle un método al servicio.
    """
    if not plaga or plaga not in catalogo.PLAGAS:
        return []
    aprobado = _texto_del_tratamiento(plaga)
    plano = normalizar(texto)
    del_lead = normalizar(dicho_por_el_lead)
    ajenos = [
        nombre
        for nombre, patron in _METODOS.items()
        if re.search(patron, plano)
        and not re.search(patron, aprobado)
        and not re.search(patron, del_lead)
    ]
    # Número de visitas e intervalo: solo los que el catálogo trae. Ojo:
    # normalizar convierte «1ª» en «1a».
    permitidas = _numeros_de_visitas(aprobado) | {
        int(n) for n in re.findall(r"\b(\d)a\b", aprobado)
    }
    for n in sorted(_numeros_de_visitas(texto) - permitidas):
        if permitidas:
            ajenos.append(f"{n} visitas")
    # El plazo entre visitas, solo en las frases que hablan de visitas («llevan
    # 5 días saliendo» es del lead, no del tratamiento).
    dias_ok = {int(x) for par in _DIAS.findall(aprobado) for x in par if x}
    for frase in re.split(r"[.!?;\n]", plano):
        if not _HABLA_DE_VISITAS.search(frase):
            continue
        for par in _DIAS.findall(frase):
            for x in par:
                if x and int(x) not in dias_ok:
                    ajenos.append(f"{x} días")
    return ajenos


# Primera persona de alguien con vida propia: en la autoprueba el bot soltó
# «Vivo cerca 😊» al pedir el código postal. Nea es un agente de IA: no vive
# en ningún lado, no tiene casa ni familia (sección 3.1).
_FINGE_HUMANO = re.compile(
    # «vivo cerca» como frase propia; «un color vivo en la fachada» no.
    r"(^|[.!¡?]\s*|\byo |\btambien )(vivo|naci|creci) (cerca|en|por|a)\b|\bsoy (tu )?vecin|"
    r"\bmi (casa|esposa|esposo|familia|hij[oa]s?|mama|papa|perro|gato)\b|"
    r"\byo tambien (tengo|tuve|vivo|vi)\b|\ben mi experiencia personal\b"
)


def finge_humano(texto: str) -> bool:
    return bool(_FINGE_HUMANO.search(normalizar(texto)))


_ATIENDE = re.compile(
    r"\b(s[ií] )?(atendemos|fumigamos|tratamos|manejamos|combatimos|eliminamos|quitamos|"
    r"controlamos|nos encargamos|te ayudo con|te ayudamos con|te podemos ayudar|"
    r"podemos (ayudarte|atender|tratar))\b"
)


def promete_plaga_fuera(texto: str) -> str:
    """La plaga fuera de catálogo que el texto dice atender, o "".

    Frase por frase: «atendemos» y la plaga en la misma frase, sin negación.
    """
    for frase in re.split(r"[.!?;\n]", normalizar(texto)):
        if not _ATIENDE.search(frase) or re.search(r"\bno\b|\bni\b", frase):
            continue
        m = re.search(r"\b(" + catalogo.FUERA_DE_CATALOGO + r")\w*", frase)
        if m:
            return m.group(0)
    return ""


_ABREVIATURA = re.compile(r"\b(Ing|Sr|Sra|Dr|Dra|Lic|Arq|Col|Av)\.", re.I)


def _trozos(texto: str, cortes: str = r"[.!;\n]+") -> list[str]:
    """El texto partido en frases, sin normalizar (para poder ver sus «¿?»).

    «el Ing. Leopoldo» no parte la frase: en la autoprueba «te comunico con el
    Ing. Leopoldo para que revise tu garantía» se leía como dos frases, y la
    segunda parecía prometer una garantía.
    """
    return [t for t in re.split(cortes, _ABREVIATURA.sub(r"\1", texto or "")) if t.strip()]


def _frases(texto: str) -> list[str]:
    """El texto partido en frases, ya normalizadas (normalizar se come los saltos)."""
    return [n for n in (normalizar(f) for f in _trozos(texto, r"[.!?;\n]+")) if n]


# ------------------------------------------- nunca nombrar al dueño ---

# «El dueño», «el jefe», «Leopoldo», «el ingeniero»: el cliente no debe saber quién
# es ni cómo se llama. «Dueño de la casa/del depa» (del cliente) no cuenta.
_DUENO = re.compile(
    r"\bleopoldo\b|\bingeniero\b|\bing\.\s|\bel jefe\b|\bmi jefe\b|\bpropietari[oa]s? del negocio\b|"
    r"\bduen[oa]\b(?!\s+(?:del|de la|de el|de los|de las|de tu|de su|de ese|de esa)\b)"
)


# Pedir foto: «¿me puedes mandar una foto?», «mándame una foto». «Gracias por la
# foto que enviaste» (la mandó él) no cuenta.
_PIDE_FOTO = re.compile(
    r"\b(puedes|podrias|podria|quieres|te animas|manda(me)?|envia(me)?|pasa(me)?|"
    r"comparte(me)?|toma|tomale|saca(le)?|adjunta)\b[^.?!]{0,35}\b(foto|fotos|fotografia|imagen|video)\b"
)


def pide_foto(texto: str) -> str:
    """La frase con la que el texto le pide una foto al cliente, o ""."""
    m = _PIDE_FOTO.search(normalizar(texto or ""))
    return m.group(0).strip() if m else ""


def menciona_al_dueno(texto: str) -> str:
    """La frase que nombra al dueño (o su nombre) ante el cliente, o ""."""
    m = _DUENO.search(normalizar(texto or ""))
    return m.group(0).strip() if m else ""


# ------------------------------------------------------- promesas vacías ---

# Lo que el dueño contó de su bot anterior (audio del 1 de octubre): «dice "sí,
# voy a revisar, la cotización te la mando" y nunca manda nada», «"nosotros te
# avisamos cuando tengamos disponibilidad", pero nunca me avisa a mí». Nea no
# puede hacer nada «después»: o lo resuelve en este turno con su herramienta, o
# pasa la conversación. Prometerlo sin pasarla es dejar al lead esperando.
#
# Dos clases. Las de CONTACTO dicen que alguien le va a escribir o que ya lo
# pasaron: sin handoff son falsas siempre. Las DIFERIDAS («te la mando», «voy a
# revisar») solo dejan al lead colgado si el mensaje no le pregunta nada: «te
# paso el precio en cuanto me digas si es casa o depa. ¿Cuál es?» sí avanza.
_PROMESA_DE_CONTACTO = re.compile(
    # «Te aviso de una vez: no damos servicio ahí» es avisar AHORA, no después.
    r"\bte (aviso|avisamos|avisare|avisaremos)\b(?! (de una vez|que\b|desde))(?![^:]{0,25}:)|"
    r"\bte (confirmo|confirmamos|confirmare|confirmaremos) "
    r"(en breve|en un momento|mas tarde|luego|despues|pronto|a la brevedad|en cuanto|cuando)\b|"
    r"\b(en breve|en un momento|en unos minutos|mas tarde|a la brevedad|pronto|al rato) te "
    r"(confirmo|aviso|escribo|contacto|comunico|busco|llamo|marco)\b|"
    r"\bte (contacto|contactamos|contactaremos|llamo|llamamos|llamaremos|marco|marcamos|"
    r"buscamos|escribimos|escribire|escribiremos)\b|"
    r"\bnos (comunicamos|comunicaremos|ponemos en contacto|pondremos en contacto)\b|"
    r"\bse (comunicara|comunica|pondra en contacto|pone en contacto) contigo\b|"
    r"\bte (comunico|paso|canalizo|transfiero) con\b|"
    r"\bcuando (tengamos|haya|tenga) (disponibilidad|espacio|lugar)\b|"
    # Dar por hecho un pase que no ocurrió («ya he enviado tus datos al Ing.»,
    # «ya le pasé tu solicitud») y prometer lo que hará el dueño («te dará el
    # precio exacto pronto»). Caso real del 3 oct: el bot dijo eso y nunca avisó.
    r"\b(ya )?(le |se los |se lo )?(he |hemos )?(enviado|pasado|mandado|compartido|enviamos|"
    r"pasamos|mandamos|compartimos|pase|mande|envie|comparti) (tus|los|sus|tu|la) "
    r"(datos|solicitud|informacion|conversacion|cotizacion)\b|"
    r"\bte (dara|dira|confirmara|escribira|contactara|llamara|enviara|mandara|pasara|"
    r"respondera|atendera)\b"
)
_PROMESA_DIFERIDA = re.compile(
    r"\bte (la|lo|las|los) (mando|envio|mandamos|enviamos|hago llegar|comparto|paso)\b|"
    r"\bte (mando|envio|mandamos|enviamos|hago llegar|comparto|paso) (la|tu|el|una|un) "
    r"(cotizacion|presupuesto|precio|costo|propuesta|informacion)\b|"
    r"\b(en breve|en un momento|en unos minutos|mas tarde|a la brevedad|pronto|al rato|"
    r"ahorita|enseguida|en seguida) te (digo|mando|envio|paso|tengo|doy)\b|"
    r"\b(voy a|vamos a|dejame|permiteme|deja) (revisar|checar|consultar)(lo|la|los|las)?\b"
)
# «Si prefieres, te comunico con el Ing.» es un ofrecimiento, no una promesa.
# Tampoco lo que depende de algo que el LEAD todavía va a hacer («en cuanto
# me des tu dirección te paso con…»): eso sí avanza cuando conteste.
_OFRECE = re.compile(
    r"\bsi (quieres|prefieres|gustas|lo prefieres|deseas|te parece|necesitas|hubo|tuviste|algo)\b|"
    r"\b(dime|dimelo|me dices|cuentame|avisame|solo dime)\b|\bcon gusto te\b|"
    r"\b(en cuanto|cuando|una vez que|ya que) (me |nos )?(des|digas|pases|confirmes|elijas|"
    r"compartas|mandes|envies|cerremos|agendemos)\b"
)
# Preguntas de cortesía: no le dan al lead nada que contestar para avanzar.
_PREGUNTA_DE_RELLENO = re.compile(
    r"algo mas|alguna (otra )?duda|te puedo ayudar|te ayudo en|te parece|esta bien|de acuerdo"
)


def promesa_vacia(texto: str) -> str:
    """La frase que promete algo «para después» (o un pase que no ocurrió), o ""."""
    pregunta_de_verdad = any(
        not _PREGUNTA_DE_RELLENO.search(normalizar(p)) for p in _PREGUNTA.findall(texto or "")
    )
    for trozo in _trozos(texto):
        if "?" in trozo or "¿" in trozo:
            continue  # preguntarle si quiere algo no es prometérselo
        frase = normalizar(trozo)
        if _OFRECE.search(frase):
            continue
        m = _PROMESA_DE_CONTACTO.search(frase)
        if not m and not pregunta_de_verdad:
            m = _PROMESA_DIFERIDA.search(frase)
        if m:
            return m.group(0)
    return ""


# ---------------------------------------------------- garantía y seguridad ---

_GARANTIA = re.compile(r"\bgarantias?\b|\bgarantizad[oa]s?\b|\bgarantizamos\b")
# Remitirla al dueño o negarla no es prometerla.
_GARANTIA_REMITIDA = re.compile(
    r"\bno\b|\bconfirma|\bdefine|\bdepende|\brevis|\bchec|\batiende|\bresuelve|\bcomunic|"
    # «Tu garantía», «eso de la garantía»: habla de la que el lead mencionó.
    r"\b(tu|su) garantia\b|\b(eso|lo) de (la|tu|su) garantia\b|\bve directamente|"
    r"\bsi (quieres|prefieres|gustas)\b"
)


def garantia_inventada(texto: str, plaga: str | None, conocimiento: str = "") -> bool:
    """¿Promete una garantía que el negocio no aprobó para esta plaga?

    La única garantía del catálogo es la de la termita de madera seca. El
    dueño contó que su bot anterior alucinaba justo aquí.
    """
    regla = (catalogo.PLAGAS.get(plaga or "") or {}).get("precio") or {}
    # Las preguntas de precio de esa plaga también son texto aprobado (la de
    # chinches dice «no se puede garantizar un colchón que no se trató»).
    preguntas = " ".join(
        catalogo.VARIABLES[v]["pregunta"]
        for v in regla.get("variables", []) if v in catalogo.VARIABLES
    )
    aprobado = " ".join(
        (_texto_del_tratamiento(plaga or ""), normalizar(preguntas), normalizar(conocimiento))
    )
    if "garant" in aprobado:
        return False
    for trozo in _trozos(texto):
        if "?" in trozo or "¿" in trozo:
            continue
        frase = normalizar(trozo)
        if _GARANTIA.search(frase) and not _GARANTIA_REMITIDA.search(frase):
            return True
    return False


# Solo frases que hablan de ENTRAR u ocupar el lugar: «la 2ª visita va de 8 a
# 10 días después» también trae un plazo, y ese es del tratamiento.
_HABLA_DE_REINGRESO = re.compile(
    r"reingres|\bentrar\b|\bingresar\b|\bocupar\b|ventila|fuera de (tu |la )?casa|"
    r"salir(se)? de (tu |la )?casa|desocupar|desaloj"
)
_DURACION = re.compile(
    r"\b(\d{1,3})(?:\s*(?:a|o|-|y)\s*(\d{1,3}))?\s*(minutos?|min\b|horas?|hrs?\b|dias?)"
)
_DURACION_EN_PALABRAS = re.compile(
    r"\b(una|dos|tres|cuatro|cinco|seis|media|un par de|algunas|varias|unas) horas?\b|"
    r"\b(un|dos|tres) dias?\b|\btodo el dia\b"
)
# Afirmaciones de inocuidad que el negocio NO aprobó. Lo aprobado es
# catalogo.DUDAS["seguridad"]; «no es tóxico» o «seguro para mascotas» son otra
# cosa, y dichas por un negocio de plaguicidas son una responsabilidad.
_INOCUO = re.compile(
    r"\borganic|\bbiodegrad|\binodor|\bsin olor\b|\bno huele|\bcofepris|\bcertificad|"
    r"\bgrado alimenticio|\binofensiv|\bno (es|son) (nada )?toxic|\becologic|"
    # «Para confirmarte al 100% si llegamos» no promete nada del producto.
    r"\b100 ?% (segur|efectiv|garantiz|libre|natural|inofensiv)|"
    r"\b(segur\w+|efectiv\w+|elimina\w*|erradica\w*|acaba\w*) (al |en un |el )?100 ?%|"
    r"\bpet friendly|\bsegur[oa]s? (para|con) (tus |las |los |el |la |tu )?"
    r"(mascotas?|ninos?|bebes?|perr\w+|gat\w+|embaraz\w+|animal\w*)"
)


_DE_INMEDIATO = re.compile(r"\bde inmediato\b|\binmediatamente\b|\bal instante\b|\bluego luego\b")


def seguridad_inventada(texto: str) -> list[str]:
    """Lo que el texto afirma de seguridad o de tiempos y el negocio no aprobó."""
    hallado: list[str] = []
    minutos_ok = set(catalogo.REINGRESO_MINUTOS)
    for frase in _frases(texto):
        hallado += [m.group(0).strip() for m in _INOCUO.finditer(frase)]
        if not _HABLA_DE_REINGRESO.search(frase):
            continue
        # «Pueden entrar de inmediato: en 15 a 20 minutos» se contradice solo.
        hallado += [m.group(0) for m in _DE_INMEDIATO.finditer(frase)]
        for a, b, unidad in _DURACION.findall(frase):
            numeros = {int(x) for x in (a, b) if x}
            if not unidad.startswith("min") or not numeros <= minutos_ok:
                hallado.append(f"{a}{'-' + b if b else ''} {unidad}")
        m = _DURACION_EN_PALABRAS.search(frase)
        if m:
            hallado.append(m.group(0))
    return hallado


# ----------------------------------------- volver a preguntar lo ya dicho ---

# Lo que más desesperaba a los clientes del bot anterior (audio del dueño):
# «ya le dijo que es chiquita y está en la cocina, y vuelve a preguntar de qué
# color es y dónde la ha visto». Con la plaga CONFIRMADA no se pregunta nada
# de identificación: ni con las preguntas del catálogo ni con variantes.
_REPREGUNTA_CUCARACHA = re.compile(
    r"\b(1 a 2|4 a 5) ?cm\b|\b(de )?que (tamano|color)\b|\b(chicas|chiquitas|pequenas) o grand|"
    r"\bdonde las (ves|has visto|encuentras|viste)\b|\ben que parte las\b"
)


_REPREGUNTA_CHINCHES = re.compile(
    r"\b(piquetes?|picaduras?|ronchas?|manchas?|manchitas?|sabanas?|puntos? negros?|"
    r"puntitos?|cabecera|costuras?|viaje|mueble usado)\b"
)


def _preguntas_de_identificacion(plaga: str) -> list[str]:
    if plaga.startswith("cucaracha"):
        return [catalogo.PREGUNTA_CUCARACHA_TAMANO, catalogo.PREGUNTA_CUCARACHA_UBICACION]
    senales = (catalogo.PLAGAS.get(plaga) or {}).get("senales") or {}
    return [s["pregunta"] for s in senales.values() if s.get("pregunta")]


def repregunta_identificacion(texto: str, plaga: str | None) -> str:
    """La pregunta de identificación que el texto hace con la plaga ya confirmada, o ""."""
    if not plaga or plaga not in catalogo.PLAGAS:
        return ""
    del_catalogo = [set(palabras(q)) for q in _preguntas_de_identificacion(plaga)]
    for cuerpo in _PREGUNTA.findall(texto or ""):
        plano = normalizar(cuerpo)
        if plaga.startswith("cucaracha") and _REPREGUNTA_CUCARACHA.search(plano):
            return cuerpo.strip()
        # Chinches ya confirmadas: preguntar por piquetes, manchas o puntos negros
        # es volver a lo que el cliente ya contó («¿en dónde has visto los piquetes
        # y las manchas?» tras decirlo en su primer mensaje).
        if plaga == "chinches" and _REPREGUNTA_CHINCHES.search(plano):
            return cuerpo.strip()
        dichas = set(palabras(cuerpo))
        for q in del_catalogo:
            comunes = dichas & q
            if len(comunes) >= 3 and len(comunes) / max(len(q), 1) >= 0.6:
                return cuerpo.strip()
    return ""


# ------------------------------------ datos que el precio no necesita ---

# Otra queja del dueño («es muy preciso en lo que pide») y un fallo que su
# propio documento ya traía (sección 15): preguntar una variable de precio que
# esta plaga no usa. En la autoprueba: metros cuadrados para la cucaracha
# alemana, que se cobra por tipo de inmueble.
_PIDE_VARIABLE = {
    "m2": r"\bmetros?\b|\bm2\b|\bque tan grande\b|\btamano (del|de la|de tu) (inmueble|casa|depa|departamento|local)",
    "colchones": r"\bcolchon",
    "sillones": r"\bsillon",
    "sillas_comedor": r"\bsillas\b",
    "sillas_secretariales": r"\bsecretarial\w*|\bsillas? de oficina\b",
    "registros": r"\bregistros?\b",
    "sanitarios": r"\bcuantos (banos|sanitarios)\b",
    "refrigeradores": r"\brefrigeradores\b|\bcongeladores\b",
}


def pregunta_dato_ajeno(texto: str, plaga: str | None) -> str:
    """La variable de precio que el texto PREGUNTA y esta plaga no usa, o ""."""
    regla = (catalogo.PLAGAS.get(plaga or "") or {}).get("precio") or {}
    if not regla:
        return ""
    usa = set(regla.get("variables", []))
    if regla.get("tipo") == "por_inmueble":
        usa.add("refrigeradores")  # solo para local comercial
    for cuerpo in _PREGUNTA.findall(texto or ""):
        plano = normalizar(cuerpo)
        for variable, patron in _PIDE_VARIABLE.items():
            if variable not in usa and re.search(patron, plano):
                return variable
    return ""


# ---------------------------------------------------- encargos ajenos ---

# «¿Me das una receta rápida de pozole?»: cumplirlo ES caer en la manipulación
# (sección 13). La regla de prompt fallaba a veces; ahora el turno lleva una
# alerta y, si aun así cumple el encargo, el texto no sale.
# Solo encargos inequívocos: «te cuento que…» y «un resumen de la cotización»
# son del tema y no deben caer aquí.
_ENCARGO_AJENO = re.compile(
    r"\breceta\b|\bpoema\b|\bchiste\b|\btraduc|\bensayo\b|\b(una|la) cancion\b|"
    r"\bun cuento\b|\b(mi|una) tarea\b|\bcodigo (en|de|para)\b|\bprograma en\b"
)
MAX_AL_DECLINAR = 280  # declinar en una línea y volver al tema cabe de sobra


def encargo_ajeno(texto_lead: str) -> bool:
    """¿El lead pide algo que no es del negocio (una receta, un poema, una tarea)?"""
    plano = normalizar(texto_lead)
    if re.search(r"cucarach|hormig|plaga|fumig|rat(a|on)|alacr|chinche|pulga|termit|arana", plano):
        return False  # «¿hay alguna receta casera para las cucarachas?» sí es del tema
    return bool(_ENCARGO_AJENO.search(plano))


# Volver a presentarse a media conversación («¡Hola! Soy Nea, el agente de
# IA…» en el cuarto mensaje): se quita sin preguntarle a nadie.
_RESALUDO = re.compile(
    r"^\s*¡?\s*hola\s*[!.,]+\s*(?:👋|🙌|😊|🙂)?\s*"
    r"(?:soy\s+\w+,?\s+(?:el |la |tu )?agente de ia[^.!?\n]*?(?:[.!]+|👋|🙌|😊|🙂|\n)\s*(?:👋|🙌|😊|🙂)?\s*)?",
    re.I,
)


def sin_resaludo(texto: str, previos: list[str]) -> str:
    """Quita el saludo de presentación si la conversación ya estaba empezada."""
    if not previos:
        return texto
    resto = _RESALUDO.sub("", texto or "", count=1).lstrip()
    if resto == (texto or "").lstrip() or len(resto) < 20:
        return texto  # no saludó, o era casi todo saludo: se queda como está
    return resto[:1].upper() + resto[1:]


# ------------------------------------------------------ reparaciones ---

_COLETILLA = re.compile(
    r",?\s*¿\s*(no|ok|okay|va|verdad|sale|cierto|vale|s[ií]|te parece|te late|"
    r"de acuerdo|est[aá] bien)\s*\?",
    re.I,
)
_PREGUNTA = re.compile(r"¿([^¿?]*)\?")
_OFRECIMIENTO = re.compile(
    r"(quieres|te gustaria|te parece|te late|te interesa|te ayudo|te cuento|te digo|"
    r"le seguimos|seguimos|va)\b"
)
# Al fundir dos preguntas, la segunda va en minúscula solo si empieza con una
# palabra común; un nombre propio («Benito Juárez») se queda como está.
_MINUSCULA = frozenset(
    "en el la los las un una unos unas o y de del con por para a al es son "
    "qué que cuál cual dónde donde cuándo cuando cómo como cuántos cuántas "
    "rincones closets zapatos excremento ruidos casa departamento".split()
)


def _preguntas(texto: str) -> int:
    return max(texto.count("?"), texto.count("¿"))


def una_sola_pregunta(texto: str) -> str:
    """Deja UNA pregunta sin pedírselo otra vez al modelo.

    «Qué fastidio, ¿no? … ¿Han aumentado?» → se va la coletilla.
    «¿Dónde las ves más? ¿En la cocina o el patio?» → «¿Dónde las ves más: en
    la cocina o el patio?». Si quedan preguntas separadas por texto, las
    primeras se vuelven afirmación y se conserva la última, que es la que
    hace avanzar la conversación.
    """
    if _preguntas(texto) <= 1:
        return texto

    def sin_coletilla(m: re.Match[str]) -> str:
        # «…mientras tanto, ¿ok?» al final de una frase deja su punto.
        resto = m.string[m.end():]
        return "." if not resto.strip() or resto.lstrip(" ").startswith("\n") else ""

    s = _COLETILLA.sub(sin_coletilla, texto)
    if _preguntas(s) <= 1:
        return s

    def fundir(m: re.Match[str]) -> str:
        a, b = m.group(1).strip(), m.group(2).strip()
        primera = b.split(" ", 1)[0].lower()
        if primera in _MINUSCULA:
            b = b[:1].lower() + b[1:]
        return f"¿{a}: {b}?"

    anterior = None
    while anterior != s and _preguntas(s) > 1:
        anterior = s
        s = re.sub(r"¿([^¿?]*)\?\s*\(?\s*¿([^¿?]*)\?\)?", fundir, s, count=1)
    if _preguntas(s) <= 1:
        return s
    # Todavía hay varias, con texto en medio: se conserva la última. Las de
    # antes que solo ofrecen algo («¿quieres que te diga el precio?») se van;
    # las demás se vuelven afirmación.
    trozos = list(_PREGUNTA.finditer(s))
    if len(trozos) < 2:
        return s  # signos sueltos sin pareja: no se toca
    for m in reversed(trozos[:-1]):
        cuerpo = m.group(1).strip()
        if _OFRECIMIENTO.match(normalizar(cuerpo)):
            s = (s[: m.start()].rstrip(" ") + " " + s[m.end():].lstrip(" ")).strip()
        else:
            s = s[: m.start()] + cuerpo[:1].upper() + cuerpo[1:] + "." + s[m.end():]
    return s


def _parrafos(texto: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]


def sin_parrafos_repetidos(texto: str, previos: list[str]) -> str:
    """Quita los párrafos que el lead ya recibió, palabra por palabra.

    En la autoprueba el modelo volvía a mandar la explicación entera del
    tratamiento dos turnos después, cambiándole solo la última línea: el
    candado de «mensaje repetido» del chasis no lo veía (no era idéntico).
    """
    ya = {" ".join(p.split()) for previo in previos for p in _parrafos(previo)}
    conservar = [
        p for p in _parrafos(texto) if len(p) < 60 or " ".join(p.split()) not in ya
    ]
    if not conservar or len(conservar) == len(_parrafos(texto)):
        return texto
    return "\n\n".join(conservar)


# ------------------------------------------------------------------ revisar ---


def revisar(
    texto: str,
    *,
    montos_validos: set[int],
    horas_validas: set[tuple[int, int]],
    cita_registrada: bool,
    plaga: str | None = None,
    linea_de_precio: str = "",
    texto_lead: str = "",
    se_paso_al_dueno: bool = True,
    conocimiento: str = "",
    identificacion_abierta: bool = False,
) -> list[Falta]:
    """Las faltas del texto, de la más grave a la menos.

    `se_paso_al_dueno`: ¿en este turno (o antes) la conversación ya se le pasó
    al dueño? Solo entonces «te comunico con…» o «te lo confirma» son verdad.
    `identificacion_abierta`: en este turno identificar_plaga pidió otra
    pregunta (el lead describe OTRA plaga): ahí preguntar sí toca.
    """
    faltas: list[Falta] = []
    if not texto or not texto.strip():
        return faltas

    ajenos = montos(texto) - montos_validos
    if ajenos:
        cifras = ", ".join(f"${n:,}" for n in sorted(ajenos))
        if linea_de_precio:
            arreglo = (
                f"la única cifra válida es «{linea_de_precio}». No sumes visitas "
                "ni calcules totales ni descuentos: el precio es por visita y se "
                "liquida al término de cada una. Dilo así, sin explicaciones nuevas"
            )
        else:
            arreglo = (
                "quita toda cifra en pesos: di de qué depende el precio y "
                "pregunta el dato que falta según el PASO ACTUAL"
            )
        faltas.append(Falta(
            "precio_no_cotizado", True,
            f"mencionaste {cifras}, una cifra que NO salió de la cotización; {arreglo}",
            detalle=cifras,
        ))
    if _PROVEEDOR.search(texto):
        faltas.append(Falta(
            "revela_modelo", True,
            "hablaste de qué modelo o proveedor te ejecuta. Eso no se dice: eres "
            "el agente de IA de este negocio, punto, y vuelves al tema de su plaga",
        ))
    if not cita_registrada and _CITA_HECHA.search(texto):
        faltas.append(Falta(
            "cita_inventada", True,
            "diste a entender que la visita ya quedó agendada o confirmada, y no "
            "es así: ninguna visita queda firme hasta que la confirma el dueño. "
            "Quita esa afirmación",
        ))
    if horas(texto) - horas_validas:
        dichas = ", ".join(m.group(0) for m in _HORA.finditer(texto))
        faltas.append(Falta(
            "horario_inventado", True,
            f"mencionaste un horario ({dichas}) que no viene de propose_slots. No "
            "inventes horarios: si toca agendar, llama propose_slots y ofrece sus "
            "etiquetas tal cual; si no, no hables de horas",
        ))
    if finge_humano(texto):
        faltas.append(Falta(
            "finge_humano", True,
            "hablaste como si fueras una persona (dónde vives, tu casa, tu familia). "
            "Eres un agente de IA: quita eso",
        ))
    promete = promete_plaga_fuera(texto)
    if promete:
        faltas.append(Falta(
            "promete_plaga_fuera", True,
            f"diste a entender que el negocio atiende {promete}, y no está en su "
            "catálogo. No lo afirmes: eso se le pasa al dueño",
            detalle=promete,
        ))
    ajenos_tx = tratamiento_ajeno(texto, plaga, texto_lead)
    if ajenos_tx:
        faltas.append(Falta(
            "tratamiento_ajeno", True,
            f"dijiste algo del tratamiento que no es de esta plaga ({', '.join(ajenos_tx)}). "
            "Usa SOLO el TRATAMIENTO del expediente, sin agregar métodos, visitas "
            "ni plazos distintos",
            detalle=", ".join(ajenos_tx),
        ))
    repregunta = "" if identificacion_abierta else repregunta_identificacion(texto, plaga)
    if repregunta:
        faltas.append(Falta(
            "repregunta_identificacion", True,
            f"volviste a preguntar por la plaga («¿{repregunta}?») y ya está CONFIRMADA: "
            "el lead ya te dijo cómo es y dónde la ve. No preguntes tamaño, color ni "
            "lugar otra vez. Contesta lo que te acaba de preguntar y cierra con la "
            "pregunta del PASO ACTUAL",
            detalle=repregunta[:60],
        ))
    ajeno = pregunta_dato_ajeno(texto, plaga)
    if ajeno:
        faltas.append(Falta(
            "pregunta_dato_ajeno", True,
            f"preguntaste un dato que el precio de esta plaga NO necesita ({ajeno}). "
            "Pregunta solo el dato que el PASO ACTUAL dice que falta, tal cual, y nada más",
            detalle=ajeno,
        ))
    if encargo_ajeno(texto_lead) and len(texto) > MAX_AL_DECLINAR:
        faltas.append(Falta(
            "encargo_ajeno", True,
            "el lead te pidió algo que no es del negocio (una receta, un poema, una "
            "tarea…) y se lo cumpliste. No se cumple, ni «rapidito»: declina en UNA "
            "línea con gracia y regresa a su plaga con la pregunta del paso actual",
        ))
    promesa = "" if se_paso_al_dueno else promesa_vacia(texto)
    if promesa:
        faltas.append(Falta(
            "promesa_vacia", True,
            f"prometiste algo para después («{promesa}») y nada hace que suceda: "
            "tú no puedes escribirle más tarde ni «revisar» nada fuera de este "
            "mensaje. O lo resuelves AHORA (el precio sale de cotizar; los "
            "horarios, de propose_slots; si falta un dato, pregúntaselo) o le "
            "pasas la conversación al dueño llamando handoff en este mismo turno",
            detalle=promesa,
        ))
    if garantia_inventada(texto, plaga, conocimiento):
        faltas.append(Falta(
            "garantia_inventada", True,
            "hablaste de una garantía que el negocio no tiene aprobada para esta "
            "plaga. Ni la afirmes ni la niegues: di que ese punto lo define el "
            "dueño y ofrécele comunicarlo con él",
        ))
    inventos = seguridad_inventada(texto)
    if inventos:
        faltas.append(Falta(
            "seguridad_inventada", True,
            f"dijiste algo de seguridad o de tiempos que el negocio no aprobó "
            f"({', '.join(inventos)}). Lo único aprobado es: «{catalogo.DUDAS['seguridad']}» "
            f"y «{catalogo.DUDAS['reingreso']}». Di solo eso; si su caso es "
            "particular (embarazo, bebés, alergias, mascotas), que la indicación "
            "se la confirma el dueño, y ofrécele comunicarlo con él",
            detalle=", ".join(inventos),
        ))
    menciona = menciona_al_dueno(texto)
    if menciona:
        faltas.append(Falta(
            "menciona_al_dueno", True,
            f"nombraste al dueño o a su nombre («{menciona}»). Al cliente NUNCA se le "
            "dice «el dueño», «el jefe», «el ingeniero» ni «Leopoldo»: cuando haya "
            "que pasarlo con alguien, es «un técnico especializado»",
            detalle=menciona,
        ))
    foto = pide_foto(texto)
    if foto:
        faltas.append(Falta(
            "pide_foto", True,
            f"le pediste una foto o imagen («{foto}»). No se piden fotos: muchas salen "
            "borrosas y ni un experto puede identificar con ellas. Sigue identificando "
            "con la pregunta de comportamiento o lugar del PASO ACTUAL (si el cliente "
            "manda una foto por su cuenta, sí la usas)",
            detalle=foto,
        ))
    if _INGLES.search(texto):
        faltas.append(Falta(
            "ingles", False,
            "escribiste fechas en inglés. Todo va en español, con la etiqueta del "
            "horario tal cual te la dio propose_slots",
        ))
    if _TECNICO.search(texto):
        faltas.append(Falta(
            "jerga_tecnica", False,
            "usaste palabras internas (sistema, herramienta, expediente, función, "
            "transcripción…). El lead solo ve una conversación normal: quítalas",
        ))
    if _preguntas(texto) > 1:
        faltas.append(Falta(
            "varias_preguntas", False,
            f"tu mensaje lleva {_preguntas(texto)} preguntas. Deja UN solo signo "
            "de interrogación: la pregunta que hace avanzar el paso actual",
        ))
    lineas = [linea for linea in texto.splitlines() if linea.strip()]
    if len(texto) > MAX_CARACTERES or len(lineas) > MAX_LINEAS:
        faltas.append(Falta(
            "muy_largo", False,
            f"el mensaje es muy largo ({len(texto)} caracteres). Máximo 3 o 4 "
            "líneas de WhatsApp: di lo esencial y cierra con tu pregunta",
        ))
    if _CALL_CENTER.search(texto):
        faltas.append(Falta(
            "call_center", False,
            "sonaste a call center («entiendo su consulta», «procederé a»…). "
            "Háblale de tú, natural: «Claro, para ayudarte mejor…»",
        ))
    if _JUZGA_RESPUESTA.search(texto):
        faltas.append(Falta(
            "juzga_respuesta", False,
            "le dijiste al lead que su respuesta es ambigua o poco clara. No "
            "califiques su respuesta: di «ya casi lo tengo, solo me falta un dato»",
        ))
    if _ORTOGRAFIA.search(texto):
        faltas.append(Falta(
            "ortografia", False,
            "revisa la ortografía: se escribe «es que» (separado) y «echado» (sin h)",
        ))
    return faltas


def correccion(faltas: list[Falta]) -> str:
    puntos = "\n".join(f"- {f.correccion}." for f in faltas)
    return (
        "Ese texto NO se le envió al lead porque rompe reglas del negocio:\n"
        f"{puntos}\n"
        "Escribe de nuevo el mensaje de WhatsApp para el lead, corregido: "
        "responde a SU último mensaje, sigue el PASO ACTUAL, corto y con una "
        "sola pregunta. No expliques la corrección ni cambies de tema."
    )


# ----------------------------------------------------- cliente recurrente ---

# Solo señales FUERTES de que ya compró (sección 10.1). «Confirmar» o
# «programar» sueltos también los dice un lead nuevo: esos los decide el
# modelo con una pregunta, no este detector.
_RECURRENTE = re.compile(
    r"\bmi (fumigacion|servicio|cita|visita|garantia|recibo|comprobante|factura|tecnico)\b|"
    r"\bya soy cliente\b|\bsoy cliente\b|\bya (han|habian|me han) venido\b|"
    r"\bya (me|nos) (fumigaron|atendieron|hicieron el servicio)\b|"
    r"\b(mi|la) (segunda|siguiente|proxima|nueva) visita\b|"
    r"\b(vuelvan|vuelva|volver) a (hacer|realizar)\b|\bvienen hoy\b|"
    r"\bla visita del (lunes|martes|miercoles|jueves|viernes|sabado|domingo|dia)\b|"
    r"\bel comprobante\b|\breprogramar\b|"
    r"\bhola,? (ing(eniero)?\.? )?leopoldo\b|\bbuen(os|as) (dias|tardes|noches),? (ing(eniero)?\.? )?leopoldo\b",
)
ETAPAS_DE_CLIENTE = ("cliente", "ganado", "recurrente")


def parece_recurrente(texto: str) -> bool:
    return bool(_RECURRENTE.search(normalizar(texto)))


# ---------------------------------------------------- sondeo del modelo ---

_SONDA = re.compile(
    r"\bque (modelo|ia|inteligencia artificial|llm) (eres|usas|utilizas|te ejecuta)\b|"
    r"\b(eres|usas|utilizas|corres en|estas hecho con|te hicieron con) "
    r"(chatgpt|gpt|claude|gemini|openai|llama|deepseek|glm)\b|"
    r"\b(system|sistema) prompt\b|\btus instrucciones\b|\bignora (tus|las|todas)\b|"
    r"\binstrucciones (anteriores|previas|del sistema)\b|"
    r"\b(que|cual) (proveedor|empresa) (de ia )?te\b|\bmodo (desarrollador|developer|debug)\b|"
    r"\bnot_available\b|\bprueba de compatibilidad\b|\bcompatibility test\b|"
    r"\b(model|provider):",
)


def es_sonda(texto: str) -> bool:
    return bool(_SONDA.search(normalizar(texto)))


# ------------------------------------------------- intención de precio ---

# «¿De cuánto tiempo es la garantía?» y «¿cuánto tarda?» no piden precio: en
# la autoprueba forzaban la cotización y la duda se quedaba sin contestar. Y
# «sale» o «vale» sueltos tampoco («sale de la coladera», «vale, gracias»).
_PIDE_PRECIO = re.compile(
    r"\bcuanto\b(?! (tiempo|tarda|tardan|dura|duran|falta|hay que|se tarda))|\bprecio|\bcosto|"
    r"\bcuesta|\bcobran|\ba como\b|\bcotiza|\bpresupuesto|\btarifa"
)


def pide_precio(texto: str) -> bool:
    return bool(_PIDE_PRECIO.search(normalizar(texto)))


_PIDE_PERSONA = re.compile(
    r"\b(hablar|comunicar|pasame|pasenme|contactar)\w*\b.{0,30}\b(persona|alguien|humano|"
    r"asesor|dueno|ingeniero|encargado|gerente|leopoldo)\b|\bno quiero (hablar con )?(un )?(bot|robot|maquina|ia)\b|"
    r"\b(un|una) (humano|persona real|asesor)\b",
)


def pide_persona(texto: str) -> bool:
    return bool(_PIDE_PERSONA.search(normalizar(texto)))

