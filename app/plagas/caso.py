"""El expediente de una conversación y el PASO ACTUAL.

El modelo de lenguaje pierde el hilo en conversaciones largas: vuelve a
preguntar lo que ya le dijeron, se salta pasos o se adelanta al precio. Aquí
el servidor lleva la cuenta de qué se sabe ya (cobertura, plaga, cotización,
dirección, cita) y, con eso, le dice al modelo en cada turno QUÉ PASO TOCA y
qué está prohibido en ese paso. El modelo redacta; el orden lo pone el código.

El expediente se guarda como JSON en `bot_conversation.caso` (migración 009).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any

from app.plagas import catalogo, precios

DIRECCION_CAMPOS = (
    "calle", "numero_exterior", "numero_interior", "colonia",
    "alcaldia_municipio", "referencia",
)
DIRECCION_NOMBRES = {
    "calle": "calle",
    "numero_exterior": "número exterior",
    "numero_interior": "número interior o de departamento",
    "colonia": "colonia",
    "alcaldia_municipio": "alcaldía o municipio",
    "referencia": "una referencia para llegar (entre qué calles, color de la fachada…)",
}


@dataclass
class Caso:
    turno: int = 0
    # Resultado de verificar_cobertura (Cobertura.como_dict()), o vacío.
    cobertura: dict[str, Any] = field(default_factory=dict)
    turno_cobertura: int = 0  # en qué turno se verificó
    plaga: str | None = None  # clave del catálogo, ya CONFIRMADA
    turno_plaga: int = 0
    candidata: str = ""
    senales: dict[str, str] = field(default_factory=dict)
    preguntadas: list[str] = field(default_factory=list)
    atascos: int = 0  # cucarachas: comparaciones simples que no cerraron
    tarjetas: int = 0
    turno_tarjeta: int = 0  # en qué turno salió la última tarjeta comparativa
    foto_pedida: bool = False
    variables: dict[str, Any] = field(default_factory=dict)
    cotizacion: dict[str, Any] | None = None  # {precio, linea, bloque, turno}
    aceptada: bool = False
    direccion: dict[str, str] = field(default_factory=dict)
    cita: dict[str, Any] | None = None  # {label, start_utc, estado}
    recurrente: bool = False
    sondas: int = 0  # intentos de sonsacar modelo/instrucciones
    otras: int = 0  # veces que el modelo dijo «otra plaga» sin nombrarla
    escalado: str = ""  # por qué se le pasó al dueño, si ya pasó
    # Cucaracha alemana Y americana a la vez (chicas en un lado, grandes en otro).
    # `plaga` queda en la alemana; el precio de las dos lo define un técnico.
    ambas: bool = False
    # Cambio de día/hora de una visita ya registrada, esperando al técnico:
    # {label, start_utc, folio}. La visita de antes sigue en pie hasta que se apruebe.
    cambio: dict[str, Any] | None = None
    # Ya se le preguntó por qué cancela (una sola vez; después sí se cancela).
    cancelacion_preguntada: bool = False
    # El técnico sugirió OTRO horario y el cliente tiene que contestar:
    # {folio, label, start_utc, kind}. No hay nada agendado hasta que acepte.
    contrapropuesta: dict[str, Any] | None = None

    @classmethod
    def desde(cls, crudo: Any) -> "Caso":
        if not isinstance(crudo, dict):
            return cls()
        validos = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in crudo.items() if k in validos})

    def a_dict(self) -> dict[str, Any]:
        return asdict(self)

    # ---------------------------------------------------------- lecturas ---

    @property
    def estado_cobertura(self) -> str:
        return str(self.cobertura.get("estado") or "")

    @property
    def dentro(self) -> bool:
        return self.estado_cobertura == "dentro_de_zona"

    def direccion_faltante(self) -> list[str]:
        """Campos de la dirección que todavía no se tienen (sección 9.2)."""
        obligatorios = ["calle", "numero_exterior", "colonia", "alcaldia_municipio", "referencia"]
        if self.variables.get("tipo_inmueble") in ("departamento", "edificio"):
            obligatorios.insert(2, "numero_interior")
        return [c for c in obligatorios if not str(self.direccion.get(c) or "").strip()]

    def direccion_texto(self) -> str:
        d = self.direccion
        partes = [
            " ".join(p for p in (d.get("calle"), d.get("numero_exterior")) if p),
            f"int. {d['numero_interior']}" if d.get("numero_interior") else "",
            d.get("colonia") or "",
            d.get("alcaldia_municipio") or "",
        ]
        texto = ", ".join(p for p in partes if p)
        if d.get("referencia"):
            texto += f" (ref.: {d['referencia']})"
        return texto


@dataclass(frozen=True)
class Paso:
    nombre: str
    toca: str
    prohibido: str = ""


def paso_actual(caso: Caso, *, agenda: bool = True) -> Paso:
    """Qué toca hacer en ESTE turno. Determinista: depende solo del expediente."""
    dueno = catalogo.NEGOCIO["dueno"]

    if caso.recurrente:
        return Paso(
            "cliente_recurrente",
            "Esta persona YA ES CLIENTE del negocio. No la trates como desconocida: "
            "salúdala por su nombre si lo tienes y averigua en UNA pregunta qué "
            "necesita. Una duda de pago, factura, garantía u horario se contesta "
            "directo SOLO si la respuesta está en el conocimiento del negocio. Si "
            "quiere agendar un mantenimiento, pregunta por un servicio en curso, o "
            f"quiere hablar con {dueno}: dile «permíteme un momento mientras te "
            f"comunico con {dueno}» y llama handoff con motivo \"cliente\" en ESTE turno.",
            "Pedir código postal, confirmar la plaga, explicar el tratamiento desde "
            "cero o cotizar: jamás se vuelve a cotizar lo que ya pagó.",
        )

    if caso.contrapropuesta is not None:
        sugerido = caso.contrapropuesta.get("label")
        return Paso(
            "contrapropuesta",
            f"El horario que pidió ya no estaba disponible y se le sugirió el {sugerido}; "
            "espera su respuesta. Si lo ACEPTA (sí, va, ok, me queda bien…): llama "
            "responder_horario_sugerido con acepta=true. Si no puede o propone otro día u "
            "hora: llama responder_horario_sugerido con acepta=false y, con lo que te "
            "devuelva, sigue (propose_slots, o cambiar_visita si ya tenía una visita "
            f"confirmada). Si no queda claro, pregúntale en una línea si le queda bien el "
            f"{sugerido}.",
            "Decir que ya quedó agendada, ofrecer otros horarios por tu cuenta o "
            "pasarlo con alguien antes de llamar responder_horario_sugerido.",
        )

    if caso.cambio is not None and caso.cita is not None:
        return Paso(
            "cambio_solicitado",
            f"Pidió mover su visita a {caso.cambio.get('label')}: ese horario SÍ está "
            "disponible, el cliente ya lo sabe y falta confirmarlo con el técnico "
            f"designado ({dueno} lo aprueba por mensaje). Mientras tanto su visita "
            f"de antes ({caso.cita.get('label')}) sigue en pie. Si pregunta, díselo "
            "con calidez; se le avisa por aquí en cuanto quede confirmado. Si quiere "
            "otra hora distinta, llama cambiar_visita otra vez.",
            "Pasarlo con alguien, decir «solicitud» o que ya quedó movida, o "
            "ofrecer horarios por tu cuenta.",
        )

    if caso.cita is not None and caso.cita.get("estado") == "confirmada":
        return Paso(
            "visita_confirmada",
            f"La visita está AGENDADA y CONFIRMADA ({caso.cita.get('label')}) y el "
            "cliente ya lo sabe. Si pregunta, díselo así y contesta sus dudas del "
            "servicio; cuando se designe a su técnico se le enviará un mensaje por aquí. "
            "Si quiere CAMBIAR el día u hora: llama cambiar_visita con accion "
            "\"reagendar\" (el sistema revisa el calendario y avisa al técnico). Si "
            "quiere CANCELAR: llama cambiar_visita con accion \"cancelar\"; el "
            "sistema le pregunta por qué con amabilidad y le ofrece reagendar. Cuando "
            "ya contestó y sigue queriendo cancelar, llámala otra vez con su motivo y "
            "confirmado=true. Si responde «Enterado» (al recordatorio), agradécele en una línea y no preguntes nada. Si pide un cambio, siempre se le pregunta el motivo antes. Si dice que va a verificar su fecha, respétalo («sin "
            "problema, aquí estaré») y no insistas.",
            "Decir «solicitud», «pendiente» o que alguien tiene que autorizarla. Pasarlo "
            "con alguien por un cambio o cancelación (se hace con cambiar_visita). "
            "Volver a cotizar, ofrecer otros horarios por tu cuenta o agendar otra visita.",
        )

    if caso.cita is not None:
        return Paso(
            "visita_solicitada",
            f"El horario ({caso.cita.get('label')}) SÍ está disponible y el cliente "
            f"ya lo sabe; falta confirmarlo con el técnico designado y {dueno} lo "
            "aprueba por mensaje. Si el lead pregunta, dile eso con calidez: que se le "
            "avisa por aquí en cuanto quede confirmado. Si quiere otro día u hora, o "
            "cancelar, llama cambiar_visita (accion «reagendar» o «cancelar»).",
            "Decir que la cita «ya quedó agendada» o «confirmada», decir «solicitud» o "
            "pedirle que espere a que le contesten. Volver a cotizar.",
        )

    if caso.escalado:
        return Paso(
            "con_el_dueno",
            f"Esta conversación ya se le pasó a {dueno} ({caso.escalado}). Si el lead "
            "escribe, dile con calidez que ya le avisaste y que le contesta por aquí.",
            "Cotizar, agendar o prometer tiempos de respuesta.",
        )

    estado = caso.estado_cobertura
    if not estado:
        return Paso(
            "cobertura",
            "Lo primero es saber si se atiende su zona. Si ya te contó su problema, "
            "reconócelo en UNA frase (con empatía, sin juzgar) y pregunta en qué "
            "colonia o zona está. En cuanto mencione su zona o un código postal, "
            "llama verificar_cobertura EN ESE MISMO TURNO, antes de decir nada "
            "sobre si hay servicio.",
            "Afirmar de memoria si hay o no cobertura. Hablar de tratamiento o de precio.",
        )
    if estado == "requiere_mas_datos":
        return Paso(
            "cobertura",
            "El nombre de la colonia no basta (hay colonias con el mismo nombre en "
            "distintas alcaldías). Pide su código postal —solo eso— y, cuando lo "
            "dé, vuelve a llamar verificar_cobertura con la zona y el código postal.",
            "Decir que sí o que no hay servicio antes de tener el código postal. "
            "Hablar de tratamiento o de precio.",
        )
    if estado == "fuera_de_zona":
        return Paso(
            "fuera_de_zona",
            "Su zona no se atiende por ahora. Avísale con amabilidad, sin rodeos, y "
            "despídete dejando la puerta abierta. Si menciona OTRO domicilio, "
            "verifica esa nueva zona con verificar_cobertura.",
            "Cotizar, explicar tratamientos u ofrecer horarios.",
        )

    restriccion = ""
    if caso.cobertura.get("dia_nombre"):
        restriccion = (
            f" OJO: en su zona solo se da servicio los {caso.cobertura['dia_nombre']}; "
            "díselo cuando hablen de fechas."
        )

    if caso.plaga is None:
        return Paso(
            "identificacion",
            "Identifica QUÉ plaga es, como un técnico que orienta a alguien que no "
            "sabe de plagas. Llama identificar_plaga con la plaga que describe y "
            "SOLO con las señales que el lead haya ESCRITO (cada una con su cita "
            "textual). La herramienta te dice si ya alcanza o cuál es la siguiente "
            "pregunta: hazle ESA pregunta, con tus palabras y una sola.",
            "Dar por confirmada la plaga antes de que la herramienta lo diga. "
            "Preguntar tipo de inmueble, metros, colchones, sillones, baños o "
            "registros: son datos de precio, no de identificación. Hablar de "
            "tratamiento o de precio. Decirle que su respuesta «no es clara».",
        )

    if caso.cotizacion is None:
        recien = caso.turno_plaga == caso.turno
        if recien:
            toca = (
                "Acabas de confirmar la plaga. Tu parte del mensaje son una o dos "
                "frases: qué plaga es, mencionando el dato que él te dio, y una "
                "frase de empatía. El tratamiento y la pregunta los agrega el "
                "sistema debajo."
            )
            prohibido = (
                "Dar precio o cualquier cifra en pesos. Preguntar datos de precio "
                "(tipo de inmueble, metros, colchones…). Proponer horarios."
            )
        else:
            # Qué dato falta lo dice el catálogo, no el modelo: dejarlo a su
            # criterio acababa en preguntas que el precio no necesita (pedía
            # metros cuadrados para una plaga que se cobra por tipo de inmueble).
            cot = precios.cotizar(caso.plaga, caso.variables)
            if cot.estado == "falta":
                dato = (
                    f"Para el precio de esta plaga falta UN dato: «{cot.falta}». Si "
                    "el lead ya lo dijo en la conversación, llama cotizar con él. "
                    f"Si no, pregúntale exactamente eso: «{cot.pregunta}» — y con su "
                    "respuesta llama cotizar. No preguntes ningún otro dato del "
                    "inmueble (metros, cuartos, pisos…) salvo que cotizar te lo pida."
                )
            else:
                dato = (
                    "Ya tienes todos los datos para el precio: llama cotizar YA, "
                    "sin preguntar nada más."
                )
            toca = (
                "La plaga ya está confirmada y el tratamiento ya se explicó: no lo "
                "repitas. Si el lead pregunta el precio, la disponibilidad o dice "
                "que sí le interesa → " + dato + " Si solo contestó tu pregunta "
                "(p. ej. si han aumentado) y no ha pedido precio, reconoce lo que "
                "dijo en una frase y ofrécele el costo con UNA pregunta («¿quieres "
                "que te diga cuánto costaría?»). Si duda del tratamiento, "
                "resuélvelo con el expediente, en corto."
            )
            prohibido = (
                "Decir cualquier cifra en pesos que no te haya devuelto cotizar en "
                "esta conversación (ni «aproximado», ni «desde»). Proponer horarios "
                "antes de que acepte el presupuesto. Pedirle al lead que calcule "
                "cuántas cajas o cuánto producto lleva."
            )
        return Paso("procedimiento" if recien else "cotizacion", toca + restriccion, prohibido)

    if not caso.aceptada:
        if agenda:
            cuando = "llama propose_slots para ver los horarios reales."
        else:
            cuando = (
                "este negocio no agenda por aquí: pídele en UN mensaje su dirección "
                "completa y qué día y horario prefiere; cuando te los dé, avísale "
                f"que {dueno} le confirma la visita y llama handoff con motivo "
                "\"cliente\" (en la nota, la dirección y su preferencia)."
            )
        return Paso(
            "aceptacion",
            "Ya tiene su cotización (está en el expediente). Espera un SÍ explícito "
            "antes de agendar. Si pregunta algo, respóndelo con el expediente; si "
            "pide que le repitas el precio, usa la línea de precio TAL CUAL. Cuando "
            "diga claramente que sí quiere agendar, " + cuando + restriccion,
            "Proponer horarios antes de que acepte. Cambiar, redondear o sumar el "
            "precio. Insistir o presionar: una invitación limpia basta.",
        )

    faltan = caso.direccion_faltante()
    falta_txt = ", ".join(DIRECCION_NOMBRES[c] for c in faltan)
    return Paso(
        "agendamiento",
        "Aceptó el presupuesto. Ofrécele máximo 3 horarios de los que te dio "
        "propose_slots, con su etiqueta tal cual. Cuando elija un día y hora "
        "concretos, pide en UN solo mensaje la dirección completa"
        + (f" (falta: {falta_txt})" if faltan else " (ya la tienes completa)")
        + ". Con día, hora y lo que haya dado de la dirección llama book_session: "
        "te dice qué falta. Un pin de ubicación NO sustituye la dirección "
        "escrita: agradécelo y pídela igual. No le preguntes al lead su alcaldía "
        "si ya la escribió, ni la deduzcas tú."
        + restriccion,
        "Inventar un horario. Decir tú que la cita «ya quedó agendada» o «confirmada»: "
        "eso lo dice el sistema en cuanto la registra. Preguntar otra vez lo que ya aceptó.",
    )


def expediente(caso: Caso, *, agenda: bool = True) -> str:
    """El bloque que ve el modelo: lo que ya se sabe + el paso que toca."""
    lineas = [
        "EXPEDIENTE DEL LEAD (lo lleva el sistema y es la verdad: no lo "
        "contradigas ni vuelvas a preguntar lo que ya está aquí):"
    ]
    cob = caso.cobertura
    if not cob:
        lineas.append("- Cobertura: sin verificar.")
    else:
        zona = " ".join(p for p in (cob.get("zona"), f"CP {cob['cp']}" if cob.get("cp") else "") if p)
        estado = {
            "dentro_de_zona": "SÍ se atiende",
            "fuera_de_zona": "NO se atiende",
            "requiere_mas_datos": "falta el código postal para saberlo",
        }.get(caso.estado_cobertura, caso.estado_cobertura)
        extra = f" — {cob['motivo']}" if cob.get("motivo") else ""
        lineas.append(f"- Cobertura: {estado} ({zona or 'zona sin nombre'}){extra}.")

    if caso.plaga:
        info = catalogo.PLAGAS[caso.plaga]
        senales = "; ".join(f"«{c}»" for c in caso.senales.values())
        lineas.append(f"- Plaga CONFIRMADA: {info['nombre']}. Lo que dijo el lead: {senales}.")
        lineas.append(
            f"- TRATAMIENTO aprobado ({info['expectativa']}): {info['visitas']}. "
            f"{info['procedimiento']}"
        )
        if info.get("contencion"):
            lineas.append(f"- Indicación para el lead: {info['contencion']}")
        if info.get("tranquilidad_peligrosa"):
            lineas.append(
                f"- Si nombra una araña peligrosa (violinista, viuda negra): {info['tranquilidad_peligrosa']}"
            )
            # En la autoprueba, a «¿es peligrosa? ¿qué me pasa si me pica?» el
            # modelo callaba (no puede diagnosticar) y, a la segunda, pasaba la
            # conversación al dueño y se perdía la cotización.
            lineas.append(
                "- Si pregunta si es violinista o viuda negra, o qué pasa si pica: NO es "
                "motivo para pasar la conversación ni puedes identificarla ni dar "
                "diagnósticos de picaduras o de salud. Contéstale con la tranquilidad de "
                "arriba, con tus palabras y sin alarmar, y luego sigue con el paso actual."
            )
    elif caso.candidata or caso.senales:
        senales = "; ".join(f"«{c}»" for c in caso.senales.values()) or "ninguna todavía"
        lineas.append(
            f"- Plaga: SIN CONFIRMAR (el lead habla de {caso.candidata or 'algo aún sin nombre'}). "
            f"Señales que ya dio: {senales}."
        )
    else:
        lineas.append("- Plaga: aún no se sabe.")

    if caso.variables:
        datos = ", ".join(f"{k}={v}" for k, v in caso.variables.items())
        lineas.append(f"- Datos del inmueble que ya dio: {datos}.")
    if caso.cotizacion:
        lineas.append(
            f"- COTIZACIÓN ya entregada (única cifra válida): {caso.cotizacion['linea']}. "
            f"{catalogo.NEGOCIO['pago']} El precio es por visita y NO se suma en un total."
        )
        lineas.append(
            "- Presupuesto aceptado: " + ("sí." if caso.aceptada else "todavía no ha dicho que sí.")
        )
    if any(caso.direccion.values()):
        lineas.append(f"- Dirección que lleva dada: {caso.direccion_texto()}.")
    if caso.contrapropuesta:
        lineas.append(
            f"- Se le sugirió {caso.contrapropuesta.get('label')} y falta que conteste."
        )
    if caso.cambio:
        lineas.append(
            f"- Pidió mover la visita a {caso.cambio.get('label')} (pendiente del técnico)."
        )
    if caso.cita:
        if caso.cita.get("estado") == "confirmada":
            lineas.append(f"- Visita AGENDADA y confirmada: {caso.cita.get('label')}.")
        else:
            lineas.append(f"- Horario disponible, pendiente de confirmar con el técnico: {caso.cita.get('label')}.")

    paso = paso_actual(caso, agenda=agenda)
    lineas.append("")
    lineas.append(f"PASO ACTUAL → {paso.nombre.upper().replace('_', ' ')}")
    lineas.append(f"Qué toca: {paso.toca}")
    if paso.prohibido:
        lineas.append(f"PROHIBIDO en este paso: {paso.prohibido}")
    return "\n".join(lineas)
