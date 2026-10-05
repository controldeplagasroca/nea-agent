"""Las herramientas que ve el modelo en el vertical de plagas, con sus compuertas.

El modelo decide CUÁNDO llamar; aquí se decide si PROCEDE y qué es verdad:

- `verificar_cobertura` → app/plagas/cobertura.py
- `identificar_plaga`   → app/plagas/diagnostico.py (mínimo 2 señales con cita)
- `cotizar`             → app/plagas/precios.py (la única fuente de una cifra)
- `propose_slots`       → la agenda real del CRM (solo tras aceptar el precio)
- `book_session`        → SOLICITUD de visita, con dirección completa; queda
                          pendiente de que el dueño la confirme
- `handoff`             → pasa la conversación al dueño

Una llamada fuera de orden no se ignora ni revienta: regresa un error que dice
qué toca hacer primero. Y cuando el resultado es un texto que NO puede variar
(el resumen de la cotización, la tarjeta comparativa, la solicitud de visita),
el servidor lo deja en `texto_garantizado` y ese es el que sale, escriba lo que
escriba el modelo.

La ficha del CRM la escribe el servidor desde aquí: cuando dependía de que el
modelo llamara `update_ficha`, 166 de 167 contactos quedaron con la ficha vacía.
"""
from __future__ import annotations

import difflib
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

from app import hostility

from app.approvals import (
    _hora_24,
    confirmar_en_linea,
    construir_description_evento,
    enviar_solicitud_aprobacion,
    next_reminder,
)
from app.crm import CrmError
from app.gcal import SERVICE_RULES, SERVICIO_DE_PLAGA, CalendarError, CalendarSlotTaken
from app.horarios import _coincide, analizar_horas
from app.plagas import candados, catalogo, cobertura, diagnostico, precios
from app.plagas.aviso import _enviar_al_dueno, avisar_cita_agendada
from app.plagas.caso import DIRECCION_CAMPOS, DIRECCION_NOMBRES, Caso
from app.plagas.fechas import fecha_pedida
from app.plagas.muebles import muebles_dichos
from app.plagas.texto import normalizar
from app.state import OfferedSlot
from app.tools import (
    TOOL_SCHEMAS,
    ToolRuntime,
    _slots_for_llm,
    _slots_from_payload,
    _zona_del_negocio,
)

logger = logging.getLogger("nea.plagas")

# Lo que puede escribir el modelo al confirmar la plaga (saludo, qué plaga es,
# empatía). El tratamiento y la pregunta van debajo, del servidor.
MAX_FRASE_DE_CONFIRMACION = 190
# El mensaje que confirma la plaga es el único del modelo que puede pasar del
# tope normal: lleva debajo la tranquilidad, el tratamiento y las visitas, y el
# dueño pidió que ese momento se explique completo («yo sí lo doy a detalle»).
TOPE_DE_CONFIRMACION = 640

# Cucarachas: tras las preguntas de tamaño, lugar y comportamiento, primer atasco:
# tarjeta comparativa (repetirla era un bucle — sección 15 de la especificación).
# Segundo atasco: lo ve una persona. Ya NO se pide foto: muchas salen borrosas y ni
# un experto puede decidir con ellas (si el cliente la manda sola, se usa).
ATASCOS_PARA_DUENO = 2

_SENALES_GUIA = "id de la señal, tal cual aparece en la GUÍA DE IDENTIFICACIÓN"

ESQUEMAS_PROPIOS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "verificar_cobertura",
            "description": (
                "Dice si el negocio da servicio en la zona del lead. Llámala EN EL "
                "MISMO TURNO en que el lead mencione su colonia, alcaldía, "
                "municipio o código postal — antes de decirle nada sobre "
                "cobertura. Nunca respondas de memoria: hay colonias con el mismo "
                "nombre en zonas distintas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "zona": {
                        "type": "string",
                        "description": "Colonia, alcaldía o municipio, como lo escribió el lead",
                    },
                    "codigo_postal": {
                        "type": "string",
                        "description": "Código postal de 5 dígitos, si el lead lo dio",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "identificar_plaga",
            "description": (
                "Registra lo que el lead ha dicho de su plaga y dice si YA alcanza "
                "para confirmarla (mínimo dos señales) o cuál es la siguiente "
                "pregunta. Llámala cada vez que el lead describa su plaga o "
                "conteste una pregunta de identificación. Manda SOLO señales que "
                "el lead escribió, cada una con su cita textual: una señal sin "
                "cita real se rechaza."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plaga": {"type": "string", "enum": catalogo.PLAGAS_PARA_MODELO},
                    "senales": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "senal": {"type": "string", "description": _SENALES_GUIA},
                                "cita": {
                                    "type": "string",
                                    "description": (
                                        "Las palabras exactas del lead que lo dicen "
                                        "(o \"foto\" si se ve en la imagen que mandó)"
                                    ),
                                },
                            },
                            "required": ["senal", "cita"],
                        },
                    },
                    "descripcion": {
                        "type": "string",
                        "description": "Solo si plaga=otra: cómo la llamó el lead",
                    },
                },
                "required": ["plaga"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cotizar",
            "description": (
                "Calcula el precio REAL de la plaga ya confirmada, con el catálogo "
                "del negocio. Es la ÚNICA fuente de una cifra. Llámala cuando el "
                "lead pida precio o muestre interés, con los datos que ya dio; si "
                "falta alguno, te dice cuál preguntar. Manda solo lo que el lead "
                "haya dicho: no supongas ni rellenes datos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo_inmueble": {
                        "type": "string",
                        "description": "casa | departamento | local_comercial | edificio",
                    },
                    "m2": {"type": "number", "description": "Metros cuadrados a tratar"},
                    "largo": {"type": "number", "description": "Largo del área en metros"},
                    "ancho": {"type": "number", "description": "Ancho del área en metros"},
                    "refrigeradores": {
                        "type": "integer",
                        "description": "Refrigeradores o congeladores (local comercial)",
                    },
                    "registros": {"type": "integer", "description": "Registros o coladeras a tratar"},
                    "sanitarios": {"type": "integer", "description": "Baños totales del inmueble"},
                    "colchones": {"type": "integer", "description": "Colchones TOTALES de la casa"},
                    "sillones": {"type": "integer", "description": "Sillones totales"},
                    "sillas_comedor": {"type": "integer", "description": "Sillas de comedor totales"},
                    "sillas_secretariales": {"type": "integer", "description": "Sillas secretariales o de oficina totales"},
                },
            },
        },
    },
]

CAMBIAR_VISITA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "cambiar_visita",
        "description": (
            "El cliente ya tiene una visita registrada y quiere CAMBIAR su día u hora "
            "(accion=reagendar) o CANCELARLA (accion=cancelar). El sistema revisa el "
            "calendario, avisa al técnico y le escribe al cliente: no agregues nada "
            "después. Para cancelar, la primera llamada solo pregunta el motivo; cuando "
            "el cliente ya contestó y confirma que cancela, llámala otra vez con "
            "motivo y confirmado=true."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "accion": {"type": "string", "enum": ["reagendar", "cancelar"]},
                "fecha": {"type": "string", "description": "AAAA-MM-DD del día nuevo (reagendar)"},
                "hora": {"type": "string", "description": "HH:MM en 24 h de la hora nueva (reagendar)"},
                "motivo": {"type": "string", "description": "Por qué cambia o cancela, con sus palabras"},
                "confirmado": {"type": "boolean", "description": "true solo si dijo claramente que quiere cancelar"},
            },
            "required": ["accion"],
        },
    },
}

RESPONDER_HORARIO_SUGERIDO: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "responder_horario_sugerido",
        "description": (
            "Al cliente se le sugirió otro horario porque el que pidió ya no estaba "
            "disponible. Llámala con su respuesta: acepta=true si lo acepta (el sistema "
            "agenda y le confirma), acepta=false si no puede o propone otro (el sistema "
            "libera la sugerencia y tú sigues con propose_slots o cambiar_visita)."
        ),
        "parameters": {
            "type": "object",
            "properties": {"acepta": {"type": "boolean"}},
            "required": ["acepta"],
        },
    },
}

_DIRECCION_PROPS = {
    "calle": {"type": "string"},
    "numero_exterior": {"type": "string"},
    "numero_interior": {"type": "string", "description": "Interior o departamento, si aplica"},
    "colonia": {"type": "string"},
    "alcaldia_municipio": {"type": "string"},
    "referencia": {"type": "string", "description": "Referencia para llegar"},
}


def _esquema(nombre: str) -> dict[str, Any]:
    import copy

    return copy.deepcopy(
        next(t for t in TOOL_SCHEMAS if t["function"]["name"] == nombre)
    )


def esquemas(agenda: bool, aprobacion: bool) -> list[dict[str, Any]]:
    """El catálogo de herramientas de ESTE turno (sin agenda, sin las de agendar)."""
    out = list(ESQUEMAS_PROPIOS)
    if agenda:
        propose = _esquema("propose_slots")
        propose["function"]["description"] = (
            "Consulta los horarios REALES para la visita. Llámala SOLO cuando el "
            "lead ya recibió su cotización y dijo que sí quiere agendar. "
            + propose["function"]["description"]
        )
        book = _esquema("book_session")
        book["function"]["description"] = (
            (
                "Registra la SOLICITUD de visita en uno de los horarios ofrecidos; "
                "queda pendiente de que el dueño la confirme. "
                if aprobacion
                else "Reserva la visita en uno de los horarios ofrecidos. "
            )
            + "Necesita el start_utc EXACTO de un horario ofrecido, lo que el lead "
            "escribió para aceptar ese día, y la dirección COMPLETA por escrito "
            "(un pin de ubicación no basta). Manda los campos de dirección que el "
            "lead ya haya dado: si falta alguno, te dice cuál pedir."
        )
        book["function"]["parameters"]["properties"].update(_DIRECCION_PROPS)
        out += [propose, book, CAMBIAR_VISITA, RESPONDER_HORARIO_SUGERIDO]
    handoff = _esquema("handoff")
    handoff["function"]["parameters"]["properties"] = {
        "reason": {
            "type": "string",
            "enum": ["cliente", "modelo", "hostilidad"],
            "description": (
                "cliente = pidió hablar con una persona, o ya es cliente y necesita "
                "al dueño · modelo = duda fuera de lo que sabes, o insiste en saber "
                "qué IA eres · hostilidad = tercer mensaje hostil seguido"
            ),
        },
        "nota": {
            "type": "string",
            "description": "Una línea para el dueño: qué necesita esta persona",
        },
    }
    handoff["function"]["parameters"]["required"] = ["reason"]
    out.append(handoff)
    return out


class RuntimeDePlagas(ToolRuntime):
    """`ToolRuntime` con el expediente y las compuertas del negocio."""

    def __init__(
        self,
        *args: Any,
        caso: Caso,
        mensajes_lead: list[str],
        ultimo_bot: str = "",
        hay_imagen: bool = False,
        nombre_lead: str = "",
        racha_hostil: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.caso = caso
        self._mensajes_lead = mensajes_lead
        self._ultimo_bot = ultimo_bot
        self._hay_imagen = hay_imagen
        self._nombre_lead = nombre_lead.strip()
        self._racha_hostil = racha_hostil
        # El texto que SALE, escriba lo que escriba el modelo.
        self.texto_garantizado: str | None = None
        # Al confirmar la plaga: el tratamiento lo escribe el servidor y el
        # modelo solo pone la frase de confirmación y la empatía.
        self.confirmacion: str | None = None
        self.cotizado = False
        # En este turno identificar_plaga dejó una pregunta pendiente (aunque
        # ya hubiera una plaga confirmada: el lead describe otra).
        self.identificacion_abierta = False
        self._cotizaciones = 0  # llamadas a cotizar en ESTE turno
        self.llamadas: list[str] = []

    @property
    def _texto_lead(self) -> str:
        return self._mensajes_lead[-1] if self._mensajes_lead else ""

    def _servicio_agenda(self) -> str | None:
        return SERVICIO_DE_PLAGA.get(self.caso.plaga or "")

    @property
    def _aprobacion(self) -> bool:
        return getattr(self._ctx.settings, "agenda_modo", "aprobacion") != "directa"

    # ------------------------------------------------------------ entrada ---

    async def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.llamadas.append(name)
        try:
            if name == "verificar_cobertura":
                return await self._verificar_cobertura(args)
            if name == "identificar_plaga":
                return await self._identificar_plaga(args)
            if name == "cotizar":
                return await self._cotizar(args)
            if name == "handoff":
                return await self._handoff_del_modelo(args)
            if name == "cambiar_visita":
                return await self._cambiar_visita(args)
            if name == "responder_horario_sugerido":
                return await self._responder_horario_sugerido(args)
            if name in ("update_ficha", "route_out"):
                # No se le enseñan al modelo en este vertical; si las inventa,
                # se le dice qué sí existe en vez de fingir que funcionaron.
                return {"ok": False, "error": "herramienta_no_disponible"}
        except CrmError as exc:
            logger.warning("plagas: %s falló contra el CRM: %s", name, exc)
            return {"ok": False, "error": "crm_error"}
        return await super().execute(name, args)

    def finalize_reply(self, text: str) -> str:
        if self.texto_garantizado:
            return self.texto_garantizado
        if self.confirmacion:
            return f"{self._frase_de_confirmacion(text)}\n\n{self.confirmacion}"
        return super().finalize_reply(text)

    def _frase_de_confirmacion(self, text: str) -> str:
        """Lo que el modelo escribió al confirmar, si respeta su parte.

        Su parte es corta: decir qué plaga es con lo que le contó el lead y una
        frase de empatía. Si se puso a explicar el tratamiento, a cotizar o a
        preguntar, se usa una frase neutra: el tratamiento y la pregunta ya
        los pone el servidor, sin errores.
        """
        caso = self.caso
        info = catalogo.PLAGAS.get(caso.plaga or "") or {}
        texto = candados.sin_caracteres_raros((text or "").strip())

        # Si el servidor ya pone la tranquilidad («no te preocupes: no es por
        # falta de higiene…»), la del modelo sobra y la repetiría.
        repite = r"\bno te preocupes\b|\btranquil" if info.get("tranquilidad") else r"(?!)"

        def cumple(frase: str) -> bool:
            return (
                "?" not in frase
                # Adornos de su cosecha: «es de las más comunes», «muy común».
                and not re.search(r"\bm[aá]s com[uú]n|\bmuy com[uú]n|\bcomun[ií]sim", frase, re.I)
                and not re.search(repite, normalizar(frase))
                and not candados.montos(frase)
                and not candados.tratamiento_ajeno(frase, caso.plaga)
                and not candados._PROVEEDOR.search(frase)
                and not re.search(
                    r"\bvisitas?\b|\btratamiento\b|\bse aplica|\bprocedimiento|\bprecio|\bcosto",
                    frase, re.I,
                )
            )

        # Frase por frase: lo que cumple su parte se queda (saludo, qué plaga
        # es, empatía); lo que se adelanta al tratamiento o al precio se va.
        conservadas: list[str] = []
        largo = 0
        # Lo que cabe depende de lo que ya ocupa el bloque del servidor (con
        # la precaución de la araña es más largo): el total no pasa del tope.
        cabe = min(
            MAX_FRASE_DE_CONFIRMACION,
            TOPE_DE_CONFIRMACION - 10 - len(self.confirmacion or ""),
        )
        # Un emoji seguido de mayúscula también cierra frase («…alemana 🪳 No te
        # preocupes…»): si no, una frase que sobra tiraba también la buena.
        # «el Ing. Leopoldo» no cierra frase: se protege el punto de la abreviatura
        # (en la autoprueba salió «ese punto lo define directamente el Ing.»).
        protegido = candados._ABREVIATURA.sub("\\1\u2024", texto)
        for frase in re.split(
            r"(?<=[.!…])\s+|\n+|(?<=[\U0001F300-\U0001FAFF☀-➿])\s+(?=[A-ZÁÉÍÓÚÑ¡¿])", protegido
        ):
            frase = frase.replace("\u2024", ".").strip()
            if not frase or not cumple(frase):
                continue
            if largo + len(frase) > cabe:
                break
            conservadas.append(frase)
            largo += len(frase) + 1
        nombre = normalizar(info.get("nombre", "")).split()
        if conservadas and nombre and nombre[0] in normalizar(" ".join(conservadas)):
            return " ".join(conservadas)
        logger.info("plagas: la frase de confirmación no nombra la plaga — agrego la neutra")
        neutra = f"Por lo que me cuentas, es {info.get('nombre', 'esa plaga').lower()} {info.get('emoji', '')}".rstrip() + "."
        # Lo que sí cumplía (el saludo, la zona confirmada) se conserva.
        if conservadas and largo + len(neutra) <= cabe:
            return " ".join(conservadas) + " " + neutra
        if not getattr(self._conv, "greeted", True):
            return f"¡Hola! Soy {self._profile.agent_name}, el agente de IA de {catalogo.NEGOCIO['nombre']} 👋 {neutra}"
        return neutra

    async def _handoff_del_modelo(self, args: dict[str, Any]) -> dict[str, Any]:
        """El modelo quiere pasar la conversación al dueño. ¿Procede?"""
        if self.handoff_reason is not None:
            # El servidor ya la pasó (con su motivo y su mensaje): no se pisa.
            return {"ok": True, "nota": "La conversación ya se le pasó al dueño."}
        razon = str(args.get("reason") or "").strip().lower()
        texto = self._texto_lead
        if (
            razon != "hostilidad"
            and hostility.is_hostile(texto)
            and self._racha_hostil < 3
            and not candados.pide_persona(texto)
        ):
            # Sección 13.1: una grosería suelta no inmuta; el pase al dueño es
            # al TERCER mensaje hostil seguido, y ese lo garantiza el turno.
            return {
                "ok": False,
                "error": "no_es_motivo_de_handoff",
                "instrucciones": (
                    "Un mensaje grosero suelto no se le pasa al dueño. Contesta con "
                    "dignidad en UNA línea, sin engancharte ni sermonear, y ofrece "
                    "ayuda con su plaga. Si reclama un servicio que ya le hicieron, "
                    "pregúntale qué pasó."
                ),
            }
        nota = str(args.get("nota") or "").strip()
        self.caso.escalado = nota or razon or "handoff"
        await self._ficha({"resultado": "handoff", "notas": nota[:480]})
        return self._handoff(args)

    # ----------------------------------------------------------- utilería ---

    async def _ficha(self, datos: dict[str, Any]) -> None:
        """Escribe en la ficha del CRM. Best-effort: nunca tumba la herramienta."""
        limpios = {k: v for k, v in datos.items() if v not in (None, "", [])}
        if not limpios:
            return
        try:
            await self._ctx.crm.put_ficha(self._crm_conv_id, limpios)
        except Exception as exc:  # la conversación no se cae por la ficha
            logger.warning("plagas: no pude escribir la ficha (%s)", exc)

    async def _escalar(self, razon: str, nota: str, texto: str) -> None:
        """Le pasa la conversación al dueño, con el mensaje que ve el lead."""
        self.handoff_reason = razon
        self.caso.escalado = nota
        self.texto_garantizado = texto
        await self._ficha({"resultado": "handoff", "notas": nota[:480]})

    def _puente(self) -> str:
        return (
            f"Permíteme un momento mientras te comunico con {catalogo.NEGOCIO['dueno']} 🙌"
        )

    @staticmethod
    def _al_dueno() -> str:
        dueno = catalogo.NEGOCIO["dueno"]
        return "al " + dueno[3:] if dueno.startswith("el ") else "a " + dueno

    # ---------------------------------------------------------- cobertura ---

    async def _verificar_cobertura(self, args: dict[str, Any]) -> dict[str, Any]:
        zona = str(args.get("zona") or "").strip()
        cp = str(args.get("codigo_postal") or "").strip()
        # Si antes solo dio la colonia y ahora solo el CP, se juntan.
        previa = self.caso.cobertura
        if not zona and previa.get("estado") == "requiere_mas_datos":
            zona = str(previa.get("zona") or "")
        if not zona and not cp:
            return {
                "ok": False,
                "error": "falta_zona",
                "instrucciones": "Pregúntale en qué colonia o zona está (o su código postal).",
            }
        if (
            previa.get("estado") == "dentro_de_zona"
            and 0 < self.caso.turno_cobertura < self.caso.turno  # se verificó en un turno ANTERIOR
            and self._misma_zona(zona, cp, previa)
        ):
            # En la autoprueba el modelo volvió a verificar la misma zona a
            # media conversación y, con el «confírmaselo», se presentó de nuevo
            # y regresó a preguntas que el lead ya había contestado.
            return {
                "ok": True,
                "estado": "ya_verificada",
                "instrucciones": (
                    "Su zona ya estaba verificada y él ya lo sabe: NO se lo repitas "
                    "ni te vuelvas a presentar. Contesta lo que acaba de decir y "
                    "sigue el PASO ACTUAL."
                ),
            }
        res = cobertura.verificar(zona, cp)
        self.caso.cobertura = res.como_dict()
        self.caso.turno_cobertura = self.caso.turno
        geo = " ".join(p for p in (res.zona, f"CP {res.cp}" if res.cp else "") if p)

        if res.estado == "requiere_mas_datos":
            await self._ficha({"geo": geo})
            return {
                "ok": True,
                "estado": res.estado,
                "instrucciones": (
                    "Todavía NO se sabe si hay servicio. Pídele su código postal "
                    "(solo eso, una pregunta) y espera su respuesta. No digas que "
                    "sí ni que no hay cobertura."
                ),
            }
        if res.estado == "fuera_de_zona":
            self.routed_out = True
            await self._ficha({
                "geo": geo, "calificado": False, "resultado": "dio_diy",
                "notas": f"Fuera de zona: {res.motivo}",
            })
            return {
                "ok": True,
                "estado": res.estado,
                "instrucciones": (
                    "Por ahora NO se da servicio en esa zona. Avísale con "
                    "amabilidad y despídete con la puerta abierta. No ofrezcas "
                    "alternativas que no existen ni sigas con preguntas."
                ),
            }
        await self._ficha({"geo": geo})
        out: dict[str, Any] = {
            "ok": True,
            "estado": res.estado,
            "instrucciones": (
                "SÍ se da servicio en su zona. Confírmaselo en pocas palabras y "
                "sigue con el paso que toca (identificar la plaga, si falta)."
            ),
        }
        if res.dia_nombre:
            out["restriccion"] = (
                f"En esa zona solo se da servicio los {res.dia_nombre}: díselo "
                "cuando hablen de fechas."
            )
        return out

    @staticmethod
    def _misma_zona(zona: str, cp: str, previa: dict[str, Any]) -> bool:
        """¿Es la zona que ya se verificó? (otro domicilio sí se verifica de nuevo)."""
        cp_nuevo = cobertura.extraer_cp(cp) or cobertura.extraer_cp(zona)
        if cp_nuevo and previa.get("cp") and str(cp_nuevo) != str(previa["cp"]):
            return False
        a, b = normalizar(zona), normalizar(str(previa.get("zona") or ""))
        a = re.sub(r"\b\d{5}\b", "", a).strip(" ,")
        return not a or not b or a in b or b in a

    # ------------------------------------------------------ identificación ---

    async def _identificar_plaga(self, args: dict[str, Any]) -> dict[str, Any]:
        caso = self.caso
        if caso.recurrente:
            return {
                "ok": False,
                "error": "cliente_recurrente",
                "instrucciones": "Ya es cliente: no lo diagnostiques de nuevo. Averigua qué necesita o pásalo con el dueño.",
            }
        plaga = str(args.get("plaga") or "").strip()
        descripcion = str(args.get("descripcion") or "").strip()
        senales = args.get("senales") if isinstance(args.get("senales"), list) else []

        # El lead nombra una plaga que NO es del catálogo y ninguna que sí:
        # se le dice con honestidad y pasa al dueño, la haya etiquetado el
        # modelo como la haya etiquetado («garrapatas en el perro» no es pulga).
        if (
            caso.plaga is None
            and re.search(catalogo.FUERA_DE_CATALOGO, normalizar(self._texto_lead))
            and not _alias(self._texto_lead)
        ):
            return await self._fuera_de_catalogo(descripcion or self._texto_lead)

        # «otra» o «no sé» solo valen si de verdad no es del catálogo: una
        # araña con mancha roja es araña, aunque el modelo la sienta «otra».
        if plaga in ("otra", "no_se_sabe", ""):
            alias = _alias(descripcion) or _alias(self._texto_lead)
            if alias:
                plaga = alias
            elif plaga == "otra" and (
                re.search(catalogo.FUERA_DE_CATALOGO, normalizar(descripcion + " " + self._texto_lead))
                or caso.otras >= 1
            ):
                return await self._fuera_de_catalogo(descripcion)
            elif caso.candidata and caso.candidata not in ("otra", "no_se_sabe"):
                plaga = caso.candidata  # sigue con la que se estaba identificando
            else:
                if plaga == "otra":
                    caso.otras += 1
                self.identificacion_abierta = True
                return {
                    "ok": True,
                    "estado": "sin_plaga",
                    "pregunta_siguiente": catalogo.PREGUNTA_QUE_PLAGA,
                    "instrucciones": (
                        "Todavía no se sabe qué plaga es. Hazle la "
                        "`pregunta_siguiente` (una sola), con tus palabras."
                    ),
                }

        # La elección en la tarjeta comparativa solo cuenta si la tarjeta ya la
        # VIO (se mandó en un turno anterior) y la elige en ESTE mensaje: en la
        # autoprueba el modelo citaba un mensaje viejo como «eligió la alemana»
        # en el mismo turno en que salía la tarjeta.
        tarjeta_vista = caso.tarjetas > 0 and caso.turno_tarjeta < caso.turno
        senales = [
            s for s in senales
            if not str((s or {}).get("senal", "")).startswith("eligio_")
            or (tarjeta_vista and diagnostico.cita_respaldada(
                str(s.get("cita") or ""), [self._texto_lead], self._hay_imagen
            ))
        ]
        d = diagnostico.evaluar(
            plaga,
            senales,
            previas=caso.senales if _misma_familia(caso.candidata, plaga) else {},
            preguntadas=caso.preguntadas if _misma_familia(caso.candidata, plaga) else [],
            mensajes_lead=self._mensajes_lead,
            ultimo_bot=self._ultimo_bot,
            hay_imagen=self._hay_imagen,
            tarjeta_enviada=tarjeta_vista,
        )
        for aviso in d.avisos:
            logger.info("plagas: señal dudosa — %s", aviso)

        if d.estado == "fuera_de_catalogo":
            return await self._fuera_de_catalogo(descripcion or plaga)

        if d.estado == "siempre_dueno":
            info = catalogo.PLAGAS[d.plaga or ""]
            await self._ficha({"plaga": info["nombre"]})
            await self._escalar(
                "modelo",
                f"{info['nombre']}: requiere atención del dueño",
                f"{info['nombre']}: {info['siempre_dueno']} " + self._puente(),
            )
            return {"ok": True, "estado": d.estado, "instrucciones": "Ya se le avisó al lead y se le pasó al dueño."}

        if not _misma_familia(caso.candidata, plaga):
            caso.preguntadas = []
            caso.atascos = 0
        caso.candidata = plaga
        caso.senales = d.senales
        if d.senal_preguntada and d.senal_preguntada not in caso.preguntadas:
            caso.preguntadas.append(d.senal_preguntada)

        if d.estado == "confirmada" and caso.plaga == d.plaga and caso.ambas == d.ambas:
            # Ya estaba confirmada: nada cambia y no se vuelve a explicar.
            return {
                "ok": True,
                "estado": "ya_estaba_confirmada",
                "instrucciones": (
                    "Esta plaga ya estaba confirmada y el tratamiento ya se "
                    "explicó: NO lo repitas ni vuelvas a anunciarla. Responde a lo "
                    "que el lead acaba de decir y sigue el PASO ACTUAL."
                ),
            }
        if d.estado == "confirmada" and self.texto_garantizado:
            # En este turno ya sale la tarjeta (o la foto): se confirma cuando
            # conteste, para que el tratamiento llegue después y no se pierda.
            return {
                "ok": True,
                "estado": "sin_confirmar",
                "instrucciones": "Ya se le mandó la comparación; espera su respuesta.",
            }
        if d.estado == "confirmada":
            assert d.plaga is not None
            if caso.plaga != d.plaga or caso.ambas != d.ambas:
                # Otra plaga = otra cotización. Lo del inmueble se conserva.
                caso.cotizacion, caso.aceptada = None, False
            caso.plaga, caso.turno_plaga, caso.atascos = d.plaga, caso.turno, 0
            caso.ambas = d.ambas
            if d.ambas:
                # Tiene las dos cucarachas: el servidor escribe TODO el mensaje (el
                # modelo mezclaba rasgos de una y otra), y no se le pide elegir ni foto.
                await self._ficha({"plaga": "Cucaracha alemana y americana"})
                self.texto_garantizado = bloque_de_dos_cucarachas()
                return {
                    "ok": True,
                    "estado": "confirmada_las_dos",
                    "instrucciones": (
                        "Tiene las DOS cucarachas (alemana y americana). Ya se le "
                        "explicó el tratamiento de cada una. No agregues nada."
                    ),
                }
            await self._ficha({"plaga": catalogo.PLAGAS[d.plaga]["nombre"]})
            # El tratamiento lo escribe el servidor: en la autoprueba el modelo
            # parafraseaba «polvo focalizado» como «gel y cebo» (el de la
            # hormiga) y le añadía causas de su cosecha.
            self.confirmacion = bloque_de_tratamiento(d.plaga, " ".join(self._mensajes_lead))
            return {
                "ok": True,
                "estado": "confirmada",
                "plaga": catalogo.PLAGAS[d.plaga]["nombre"],
                "lo_que_dijo_el_lead": list(d.senales.values()),
                "instrucciones": (
                    "Plaga CONFIRMADA. Tu mensaje es SOLO una o dos frases: dile "
                    "qué plaga es mencionando lo que él te contó («por lo que me "
                    "cuentas —chiquitas y en la cocina— es…») y una frase de "
                    "empatía (sin «no te preocupes» ni «es muy común»: la "
                    "tranquilidad aprobada ya la pone el sistema). Si te preguntó "
                    "algo más en su mensaje, contéstalo "
                    "en corto. NO expliques el tratamiento, NO des precio y NO "
                    "hagas preguntas: el sistema agrega debajo el tratamiento "
                    "aprobado y la pregunta. Describe solo rasgos de ESTA plaga."
                ),
            }

        base: dict[str, Any] = {
            "ok": True,
            "estado": "sin_confirmar",
            "senales_que_ya_cuentan": list(d.senales),
            "senales_rechazadas": d.rechazadas,
        }
        self.identificacion_abierta = True
        if d.estado == "sin_preguntas" or (plaga.startswith("cucaracha") and d.atasco):
            return await self._atasco(d, base)
        await self._ficha({"plaga": f"{plaga} (sin confirmar)"})
        base["pregunta_siguiente"] = d.pregunta
        base["instrucciones"] = (
            "Todavía NO está confirmada: no la nombres como un hecho. Hazle al "
            "lead la `pregunta_siguiente` (adáptala a tu tono; UNA sola pregunta). "
            "No preguntes datos de precio."
        )
        return base

    async def resolver_sin_modelo(self) -> bool:
        """¿Este turno lo resuelve el servidor solo? (True = ya hay texto garantizado).

        Hoy un solo caso: el lead nombra una plaga que NO es del catálogo y
        ninguna que sí, sin haber confirmado otra antes. La especificación es
        clara (sección 4.3): honestidad y pase al dueño. No hay nada que el
        modelo deba decidir, y dejándoselo prometía atenderla.
        """
        caso = self.caso
        if caso.plaga is not None or caso.recurrente or caso.escalado:
            return False
        texto = self._texto_lead
        if not re.search(catalogo.FUERA_DE_CATALOGO, normalizar(texto)) or _alias(texto):
            return False
        await self._fuera_de_catalogo(texto)
        if not getattr(self._conv, "greeted", True) and self.texto_garantizado:
            self.texto_garantizado = (
                f"¡Hola! Soy {self._profile.agent_name}, el agente de IA de "
                f"{catalogo.NEGOCIO['nombre']} 👋 " + self.texto_garantizado
            )
        return True

    async def _fuera_de_catalogo(self, descripcion: str) -> dict[str, Any]:
        # El nombre de la plaga si se reconoce («garrapatas»); si no, las
        # primeras palabras de cómo la describió.
        plano = normalizar(descripcion or self._texto_lead)
        m = re.search(r"\b(" + catalogo.FUERA_DE_CATALOGO + r")\w*", plano)
        nombre = m.group(0) if m else (" ".join(plano.split()[:3]) or "esa plaga")
        await self._escalar(
            "modelo",
            f"Plaga fuera de catálogo: {descripcion or nombre}",
            f"Con toda honestidad, eso que me cuentas ({nombre}) no es de las "
            "plagas que atiendo por aquí, y prefiero no improvisarte un "
            "tratamiento ni un precio. " + self._puente(),
        )
        return {"ok": True, "estado": "fuera_de_catalogo", "instrucciones": "Ya se le avisó al lead y se le pasó al dueño."}

    async def _atasco(self, d: diagnostico.Diagnostico, base: dict[str, Any]) -> dict[str, Any]:
        """Las preguntas no cerraron: tarjeta comparativa → una persona (sin foto)."""
        caso = self.caso
        if self.texto_garantizado:
            # Otra llamada en el MISMO turno: el atasco ya se contó y su texto
            # (la tarjeta) ya va a salir. Contarlo dos veces brincaba de la
            # tarjeta al pase sin que el lead viera la tarjeta.
            base["instrucciones"] = "Ya se le mandó la comparación; espera su respuesta."
            return base
        caso.atascos += 1
        es_cucaracha = (d.plaga or "").startswith("cucaracha")
        if not es_cucaracha or caso.atascos >= ATASCOS_PARA_DUENO:
            await self._escalar(
                "modelo",
                f"No se pudo identificar la plaga por chat ({caso.candidata})",
                "Para no darte un diagnóstico equivocado, prefiero que lo revise "
                f"{catalogo.NEGOCIO['dueno']}. Ya le pasé lo que me contaste para que "
                "te responda por aquí 🙌",
            )
            base["instrucciones"] = "Ya se le avisó al lead y se le pasó a una persona."
            return base
        caso.tarjetas += 1
        caso.turno_tarjeta = caso.turno
        self.texto_garantizado = catalogo.TARJETA_CUCARACHAS
        base["instrucciones"] = (
            "Ya se le envió al lead la tarjeta comparativa de las dos cucarachas. "
            "No agregues nada. Cuando conteste cuál se parece, llama "
            "identificar_plaga con eligio_alemana o eligio_americana y su cita."
        )
        return base

    # ---------------------------------------------------------- cotización ---

    def _plaga_que_dijo_el_lead(self) -> str | None:
        """La última plaga que el lead nombró en la conversación, o None."""
        for mensaje in reversed(self._mensajes_lead):
            clave = _ultima_plaga_nombrada(mensaje)
            if clave is not None:
                return clave
        return None

    async def _cotizar(self, args: dict[str, Any]) -> dict[str, Any]:
        caso = self.caso
        if caso.recurrente:
            return {
                "ok": False,
                "error": "cliente_recurrente",
                "instrucciones": "Ya es cliente: jamás se le vuelve a cotizar lo que ya pagó. Pásalo con el dueño.",
            }
        if not caso.dentro:
            return {
                "ok": False,
                "error": "falta_cobertura",
                "instrucciones": (
                    "Antes de cotizar hay que confirmar que se atiende su zona: "
                    "pregúntale su colonia o código postal y llama verificar_cobertura. "
                    "No digas ninguna cifra."
                ),
            }
        if caso.plaga is None:
            return {
                "ok": False,
                "error": "falta_identificar",
                "instrucciones": (
                    "Todavía no está confirmada la plaga: sigue con identificar_plaga. "
                    "Dile que el precio depende de qué plaga sea y hazle la pregunta "
                    "de identificación que falta. No digas ninguna cifra."
                ),
            }
        nombrada = self._plaga_que_dijo_el_lead()
        if nombrada is not None and not _misma_familia(nombrada, caso.plaga):
            # Lo confirmado es de otra conversación o de antes: el lead ahora
            # habla de otra plaga. Cotizar lo viejo le daría el precio de una
            # plaga que no tiene (caso real: «chinches» cotizadas como cucaracha
            # alemana). Se suelta lo anterior y se vuelve a identificar.
            logger.warning(
                "plagas: el lead habla de %s pero lo confirmado es %s — no se cotiza",
                nombrada, caso.plaga,
            )
            caso.plaga = None
            caso.turno_plaga = 0
            caso.cotizacion = None
            caso.aceptada = False
            return {
                "ok": False,
                "error": "plaga_distinta_a_la_confirmada",
                "instrucciones": (
                    f"El lead habla de {nombrada.replace('_', ' ')}, no de la plaga que "
                    "estaba confirmada antes. No digas ninguna cifra. Llama "
                    f"identificar_plaga con plaga={nombrada!r} y sigue el PASO ACTUAL."
                ),
            }
        if caso.turno_plaga == caso.turno:
            return {
                "ok": False,
                "error": "primero_el_tratamiento",
                "instrucciones": (
                    "Acabas de confirmar la plaga. En ESTE mensaje explica el "
                    "tratamiento y haz la pregunta de urgencia; el precio va en "
                    "cuanto el lead diga que le interesa. No digas ninguna cifra."
                ),
            }

        self._cotizaciones += 1
        if self._cotizaciones > 2 and caso.cotizacion is None:
            # En la autoprueba el modelo llamó cotizar 7 veces seguidas con el
            # mismo dato no dicho y el turno se quedó sin texto.
            pendiente = precios.cotizar(caso.plaga, caso.variables)
            return {
                "ok": False,
                "error": "deja_de_llamar_cotizar",
                "instrucciones": (
                    "No vuelvas a llamar cotizar en este turno. Escríbele al lead y "
                    "pregúntale el dato que falta"
                    + (f": «{pendiente.pregunta}»" if pendiente.estado == "falta" else "")
                    + ". Con su respuesta lo vuelves a intentar."
                ),
            }
        nuevas = precios.limpiar_variables(args)
        # Solo los datos que pide el precio de ESTA plaga (en la autoprueba el
        # modelo mandaba refrigeradores y baños para una araña).
        regla = (catalogo.PLAGAS.get(caso.plaga) or {}).get("precio") or {}
        utiles = set(regla.get("variables", []))
        if regla.get("tipo") == "por_inmueble":
            utiles.add("refrigeradores")  # solo se pregunta si es local comercial
        nuevas = {k: v for k, v in nuevas.items() if k in utiles}
        supuestas = [k for k in nuevas if not self._dato_dicho(k, nuevas[k], args)]
        for clave in supuestas:
            nuevas.pop(clave)  # lo supuso el modelo: el lead nunca lo dijo
        # Al revés también: lo que el lead SÍ dijo y el modelo no mandó. En la
        # autoprueba, a quien abrió con «un depa de 70 metros» se le volvió a
        # preguntar cuántos metros eran.
        if "tipo_inmueble" in utiles and not (nuevas.get("tipo_inmueble") or caso.variables.get("tipo_inmueble")):
            if (inmueble := self.inmueble_dicho()) is not None:
                nuevas["tipo_inmueble"] = inmueble
        if "m2" in utiles and not (nuevas.get("m2") or caso.variables.get("m2")):
            if (m2 := self.m2_dicho()) is not None:
                nuevas["m2"] = m2
        # Colchones, sillones y sillas que el cliente ya dijo con sus palabras (4 oct:
        # los dio en su primer mensaje y el bot los volvió a preguntar).
        for clave, cantidad in muebles_dichos(self._mensajes_lead).items():
            if clave in utiles and clave not in nuevas and clave not in caso.variables:
                nuevas[clave] = cantidad
        caso.variables.update(nuevas)
        cot = precios.cotizar(caso.plaga, caso.variables)
        nombre = catalogo.PLAGAS[caso.plaga]["nombre"]
        datos = ", ".join(f"{k}={v}" for k, v in cot.variables.items())
        await self._ficha({"plaga": nombre, "tipo_inmueble": cot.variables.get("tipo_inmueble")})

        if cot.estado == "falta":
            aviso = ""
            if supuestas:
                aviso = (
                    f" OJO: mandaste {', '.join(supuestas)} sin que el lead lo dijera; "
                    "esos datos los da el lead, no se suponen."
                )
            return {
                "ok": False,
                "estado": "falta_un_dato",
                "falta": cot.falta,
                "pregunta_siguiente": cot.pregunta,
                "instrucciones": (
                    "Falta ese dato para el precio. Si el lead ya lo dijo antes en "
                    "la conversación, vuelve a llamar cotizar incluyéndolo. Si no, "
                    "hazle la `pregunta_siguiente` (UNA sola pregunta) y espera. "
                    "No digas ninguna cifra todavía." + aviso
                ),
            }
        if caso.ambas:
            # Alemana y americana a la vez: el precio de las dos juntas no está
            # en el catálogo, lo define una persona. Ya se tienen los datos del
            # inmueble (la alemana los pide), así que se pasa completo.
            await self._ficha({"datos_cotizacion": datos})
            await self._escalar(
                "modelo",
                f"Cotización manual — cucaracha alemana y americana (tiene las dos). "
                f"Datos: {datos or 'sin datos'}",
                f"Con las dos cucarachas a la vez, el precio lo define "
                f"{catalogo.NEGOCIO['dueno']} según tu caso. Ya le pasé tus datos para "
                "que te lo dé por aquí 🙌",
            )
            return {"ok": True, "estado": "lo_cotiza_el_dueno", "instrucciones": "Ya se le avisó al lead y se le pasó a una persona."}
        if cot.estado == "requiere_dueno":
            await self._ficha({"datos_cotizacion": datos})
            await self._escalar(
                "modelo",
                f"Cotización manual — {nombre}: {cot.motivo}. Datos: {datos or 'sin datos'}",
                f"Para {nombre.lower()}, {cot.motivo}. Ya le pasé tus datos "
                f"{self._al_dueno()} para que te dé el precio exacto por aquí. "
                + self._puente(),
            )
            return {"ok": True, "estado": "lo_cotiza_el_dueno", "instrucciones": "Ya se le avisó al lead y se le pasó al dueño."}

        if caso.cotizacion and caso.cotizacion.get("linea") == cot.linea_precio:
            # Misma cotización que ya tiene: reenviarle el resumen entero en
            # vez de contestar lo que preguntó (en la autoprueba: «¿y si
            # necesito factura?» → el resumen otra vez) es repetirse.
            return {
                "ok": True,
                "estado": "ya_cotizado",
                "precio": cot.linea_precio,
                "instrucciones": (
                    "Ya tiene esta misma cotización: NO se la reenvíes. Contesta lo "
                    "que te preguntó y, si hace falta, repite la línea de precio tal cual."
                ),
            }
        bloque = precios.bloque_de_cierre(cot)
        caso.cotizacion = {
            "precio": cot.precio, "linea": cot.linea_precio, "bloque": bloque,
            "turno": caso.turno,
        }
        caso.aceptada = False
        self.cotizado = True
        pregunta = (
            precios.PREGUNTA_DE_CIERRE if self._ctx.agenda_enabled
            else "¿Te gustaría que coordinemos tu visita?"
        )
        self.texto_garantizado = f"{bloque}\n\n{pregunta}"
        await self._ficha({"cotizacion": cot.linea_precio, "datos_cotizacion": datos, "calificado": True})
        return {
            "ok": True,
            "estado": "cotizado",
            "precio": cot.linea_precio,
            "instrucciones": (
                "El resumen de la cotización ya se le envía al lead tal cual, con "
                "la pregunta de si quiere agendar. No lo reescribas ni agregues nada."
            ),
        }

    # ------------------------------------------------------------- agenda ---

    def _miercoles(self, n: int = 2) -> list[str]:
        """Las próximas `n` fechas del día al que está limitada su zona."""
        dia = self.caso.cobertura.get("dia_restringido")
        hoy = datetime.now(_zona_del_negocio(self._ctx)).date()
        fechas: list[str] = []
        d = hoy + timedelta(days=1)
        while len(fechas) < n:
            if d.weekday() == dia:
                fechas.append(d.isoformat())
            d += timedelta(days=1)
        return fechas

    # ---------------------------------------------- horario que propone el lead ---

    async def _propone_su_horario(self, args: dict[str, Any]) -> bool:
        """¿El lead está PROponiendo su propio día u hora, en vez de elegir uno ofrecido?

        Regla del negocio: si el cliente sugiere un horario, no se agenda ni se
        le contradice: se manda a verificar con el dueño. Si no sugiere ninguno,
        Nea ofrece los suyos (24 h de anticipación, dentro de horario laboral).

        Elegir «el de las 10:00» entre lo ya ofrecido NO es sugerir.
        """
        texto = self._texto_lead
        horas = analizar_horas(texto)
        menciona_dia = bool(_RE_DIA_PROPUESTO.search(normalizar(texto)))
        if not horas and not menciona_dia:
            return False
        ofrecidos = await self._ctx.store.get_offered_slots(self._conv.id)
        if horas and ofrecidos:
            tz = _zona_del_negocio(self._ctx)
            locales = [s.start_utc.astimezone(tz) for s in ofrecidos]
            if all(any(_coincide(h, local) for local in locales) for h in horas):
                return False  # eligió una hora de las ofrecidas
        if not horas and ofrecidos and not args.get("fecha"):
            return False  # «sí, el jueves» sobre una oferta que ya traía jueves
        return True

    async def _pasar_horario_al_dueno(self) -> dict[str, Any]:
        """El lead propuso su horario: se le pasa al dueño con lo que escribió."""
        caso = self.caso
        propuesta = re.sub(r"\s+", " ", self._texto_lead).strip()[:160]
        dueno = catalogo.NEGOCIO["dueno"]
        caso.escalado = f"El cliente propone su propio horario: «{propuesta}»"
        await self._ficha({
            "resultado": "handoff",
            "notas": f"HORARIO PROPUESTO POR EL CLIENTE, verificar: «{propuesta}»"[:480],
        })
        self.handoff_reason = "cliente"
        self.texto_garantizado = (
            f"Anoté el horario que me propones ({propuesta}). "
            f"Se lo paso a {dueno} para verificar que se pueda y te confirma por aquí en breve."
        )
        return {
            "ok": True,
            "estado": "horario_propuesto_en_verificacion",
            "instrucciones": (
                "El lead propuso su propio horario: ya se le pasó al dueño para "
                "verificarlo y el lead ya recibió el aviso. No ofrezcas otros "
                "horarios ni confirmes el suyo. No agregues nada."
            ),
        }

    async def _propose_slots(self, args: dict[str, Any]) -> dict[str, Any]:
        caso = self.caso
        if caso.cotizacion is None:
            return {
                "ok": False,
                "error": "falta_cotizacion",
                "instrucciones": (
                    "No se ofrecen horarios antes de que el lead tenga su "
                    "cotización y la acepte. Sigue el PASO ACTUAL."
                ),
            }
        if caso.cotizacion.get("turno") == caso.turno:
            return {
                "ok": False,
                "error": "espera_su_respuesta",
                "instrucciones": "Acabas de darle el precio: espera a que diga que sí quiere agendar.",
            }
        dia = caso.cobertura.get("dia_restringido")
        # En una zona de un solo día (Toluca, Lerma) el día lo manda la regla de
        # zona, no el dueño: pedir otro día se contesta abajo con «solo ese día».
        con_calendario = self._ctx.calendar is not None
        if dia is None and not con_calendario and await self._propone_su_horario(args):
            return await self._pasar_horario_al_dueno()
        if dia is None and con_calendario and not args.get("fecha"):
            # Con calendario propio la disponibilidad se consulta, no se supone ni
            # se manda a verificar: «¿mañana a las 10?» se contesta mirando ESE día.
            pedida = fecha_pedida(self._texto_lead, datetime.now(_zona_del_negocio(self._ctx)).date())
            if pedida:
                args = {**args, "fecha": pedida}
        if dia is None:
            res = await super()._propose_slots(args)
        else:
            nombre = caso.cobertura.get("dia_nombre")
            pedida = str(args.get("fecha") or "")
            try:
                fechas = [pedida] if date.fromisoformat(pedida).weekday() == dia else None
            except ValueError:
                fechas = self._miercoles()
            if fechas is None:
                return {
                    "ok": False,
                    "error": "dia_no_disponible_en_su_zona",
                    "instrucciones": (
                        f"En su zona solo se da servicio los {nombre}. Díselo con "
                        f"honestidad y ofrécele un {nombre}: vuelve a llamar "
                        "propose_slots sin fecha."
                    ),
                }
            res = {"ok": False, "error": "sin_disponibilidad"}
            for fecha in fechas:
                res = await super()._propose_slots({"fecha": fecha})
                if res.get("ok"):
                    break
            if res.get("ok"):
                res["instrucciones"] = (
                    f"En su zona solo se atiende en {nombre}: ofrécele estos "
                    "horarios (máximo 3, con su etiqueta tal cual) y dile por qué "
                    f"es {nombre}."
                )
        if res.get("ok"):
            caso.aceptada = True
        return res

    async def _resolve_offered(
        self, args: dict[str, Any], accion: str
    ) -> tuple[OfferedSlot | None, dict[str, Any] | None]:
        chosen, error = await super()._resolve_offered(args, accion)
        if (
            error is not None
            and error.get("error") == "hora_no_ofrecida"
            and self._ctx.calendar is None
        ):
            # Pidió una hora que nadie le ofreció: no se le contradice ni se
            # inventa; el dueño la verifica. (Con calendario propio no hace falta:
            # el error ya manda a consultar los horarios reales de ese día.)
            return None, await self._pasar_horario_al_dueno()
        return chosen, error

    async def _book_session(self, args: dict[str, Any]) -> dict[str, Any]:
        caso = self.caso
        supuestos: list[str] = []
        for campo in DIRECCION_CAMPOS:
            valor = str(args.get(campo) or "").strip()
            if not valor or valor.lower() in ("n/a", "na", "no aplica", "-", "s/n"):
                continue
            if campo != "referencia" and not self._lo_escribio_el_lead(valor):
                supuestos.append(campo)  # lo dedujo el modelo: no cuenta
                continue
            caso.direccion[campo] = valor[:160]
        if caso.cotizacion is None or not caso.aceptada:
            return {
                "ok": False,
                "error": "falta_aceptar_cotizacion",
                "instrucciones": "No se agenda sin cotización aceptada y horarios ofrecidos. Sigue el PASO ACTUAL.",
            }
        chosen, error = await self._resolve_offered(args, "book_session")
        if error is not None or chosen is None:
            return error or {"ok": False, "error": "slot_no_ofrecido"}
        faltan = caso.direccion_faltante()
        if faltan:
            nombres = ", ".join(DIRECCION_NOMBRES[c] for c in faltan)
            aviso = ""
            if supuestos:
                aviso = (
                    " OJO: mandaste "
                    + ", ".join(DIRECCION_NOMBRES[c] for c in supuestos)
                    + " sin que el lead lo escribiera; la dirección la da el lead, "
                    "no se deduce."
                )
            return {
                "ok": False,
                "error": "falta_direccion",
                "falta": faltan,
                "instrucciones": (
                    f"El horario {chosen.label} ya quedó elegido; no lo vuelvas a "
                    f"preguntar. Para la visita falta la dirección escrita: {nombres}. "
                    "Pídeselo en UNA sola pregunta y, con su respuesta, vuelve a "
                    "llamar book_session con el mismo start_utc." + aviso
                ),
            }
        await self._ficha({"direccion": caso.direccion_texto()})
        if not self._aprobacion:
            return await super()._book_session(args)
        return await self._solicitar_visita(chosen)

    def _dato_dicho(self, clave: str, valor: Any, crudos: dict[str, Any]) -> bool:
        """¿El lead dijo ese dato del inmueble, o lo supuso el modelo?

        En la autoprueba el modelo cotizó «departamento» a quien nunca dijo qué
        era (tenía casa): el precio salió del catálogo, pero de un dato inventado.
        """
        mensajes = [normalizar(m) for m in self._mensajes_lead]
        plano = " ".join(mensajes)
        # «90m2», «10x8» y «15mts» traen el número pegado: se separa.
        palabras = set(re.findall(r"\d+(?:\.\d+)?|[a-zñ]+", plano.replace(",", "")))
        if clave == "tipo_inmueble":
            patrones = _DICE_INMUEBLE.get(str(valor), ())
            return any(re.search(p, m) for p in patrones for m in mensajes)
        if clave == "m2":
            largo, ancho = crudos.get("largo"), crudos.get("ancho")
            if largo and ancho and all(self._numero_dicho(x, palabras, plano) for x in (largo, ancho)):
                return True  # lo dijo como largo por ancho
            if crudos.get("m2") in (None, ""):
                return False
        return self._numero_dicho(crudos.get(clave, valor), palabras, plano)

    def inmueble_dicho(self) -> str | None:
        """El tipo de inmueble que el lead dijo, si dijo uno solo."""
        mensajes = [normalizar(m) for m in self._mensajes_lead]
        dichos = {
            tipo for tipo, patrones in _DICE_INMUEBLE.items()
            if any(re.search(p, m) for p in patrones for m in mensajes)
        }
        return dichos.pop() if len(dichos) == 1 else None

    def m2_dicho(self) -> float | None:
        """Los metros cuadrados que el lead dijo, si dijo una sola cifra."""
        dichos: set[int] = set()
        for m in self._mensajes_lead:
            plano = normalizar(m)
            # «10 metros de largo por 8 de ancho» son medidas, no el área: esas
            # las multiplica el modelo (largo y ancho) y aquí no se adivinan.
            if re.search(r"\blargo\b|\bancho\b|\bfondo\b|\bfrente\b|\d\s*(x|por)\s*\d", plano):
                continue
            dichos.update(
                int(n) for n in re.findall(
                    # «a 50 metros del metro» es una distancia, no un área.
                    r"\b(\d{2,4})\s*(?:m2\b|mts?2?\b|metros?(?:\s+cuadrados)?\b)(?!\s+(?:de|del|a)\b)",
                    plano,
                )
            )
        return float(dichos.pop()) if len(dichos) == 1 else None

    @staticmethod
    def _numero_dicho(valor: Any, palabras: set[str], plano: str) -> bool:
        n = precios._numero(valor)
        if n is None:
            return False
        if n == 0 and _dice_cero(plano):
            return True
        entero = int(n) if float(n).is_integer() else None
        candidatos = {f"{n:g}"} | ({str(entero)} if entero is not None else set())
        if entero is not None:
            candidatos |= {w for w, v in _NUMEROS.items() if v == entero}
        return bool(candidatos & palabras)

    def _lo_escribio_el_lead(self, valor: str) -> bool:
        """¿Alguna palabra de ese dato aparece en lo que escribió el lead?"""
        piezas = set(re.findall(r"[a-z0-9ñ]+", normalizar(valor)))
        dichas: set[str] = set()
        for m in self._mensajes_lead:
            dichas.update(re.findall(r"[a-z0-9ñ]+", normalizar(m)))
        return bool(piezas & dichas)

    def _nota_de_zona(self) -> str:
        """Aviso para quien aprueba: las zonas de un solo día (Toluca, Lerma) no
        las cubren todos los técnicos, así que no basta con que el horario esté
        libre: hay que confirmar que ese día vaya alguien."""
        c = self.caso.cobertura
        if c.get("dia_restringido") is None:
            return ""
        zona = str(c.get("zona") or "zona restringida")
        return (
            f"⚠️ Zona {zona} (solo {c.get('dia_nombre', 'ese día')}): confirma que "
            "haya un técnico que vaya ese día antes de aprobar."
        )

    # --------------------------------------------- cambiar o cancelar la visita ---

    async def _cambiar_visita(self, args: dict[str, Any]) -> dict[str, Any]:
        """Reagendar o cancelar una visita ya registrada.

        Todo lo decide el servidor: el modelo solo dice qué quiere el cliente. Un
        cambio pasa por el mismo candado que una visita nueva (horario real del
        calendario + aprobación del técnico); la de antes sigue en pie hasta
        entonces. La cancelación pregunta una vez por qué y ofrece reagendar.
        """
        if self.caso.cita is None:
            return {
                "ok": False,
                "error": "sin_visita",
                "instrucciones": "No tiene una visita registrada: sigue el PASO ACTUAL.",
            }
        if str(args.get("accion") or "").strip().lower() == "cancelar":
            return await self._cancelar_visita(args)
        return await self._reagendar_visita(args)

    async def _responder_horario_sugerido(self, args: dict[str, Any]) -> dict[str, Any]:
        """El cliente contesta el horario que sugirió el técnico (acepta, o no puede)."""
        ctx, caso = self._ctx, self.caso
        sug = caso.contrapropuesta
        pending = await ctx.store.get_pending_booking(int(sug["folio"])) if sug else None
        if pending is None or pending.estado != "esperando_cliente":
            caso.contrapropuesta = None
            return {
                "ok": False,
                "error": "sin_sugerencia",
                "instrucciones": "No hay un horario sugerido esperando respuesta: sigue el PASO ACTUAL.",
            }
        cuando = str(sug.get("label") or "")
        destino = ctx.settings.aviso_dueno_identity or ctx.settings.owner_identity
        quien = self._nombre_lead or "El cliente"
        if args.get("acepta") is True:
            para_el_dueno, texto_cliente = await confirmar_en_linea(ctx, pending)
            confirmado = (await ctx.store.get_pending_booking(pending.id)).estado == "aprobado"
            if destino:
                await _enviar_al_dueno(
                    ctx, destino,
                    f"✅ {quien} aceptó el {cuando} (#{pending.id}). {para_el_dueno}",
                )
            caso.contrapropuesta = None
            if confirmado:
                caso.cita = {
                    **(caso.cita or {}),
                    "label": cuando,
                    "start_utc": pending.start_utc.isoformat(),
                    "estado": "confirmada",
                    "folio": pending.id,
                }
                caso.cambio = None
                self.texto_garantizado = texto_cliente or (
                    f"¡Confirmado! ✅ Tu visita quedó agendada para el {cuando}."
                )
            else:
                # El calendario no pudo reservar: no se le dice que quedó agendada.
                self.texto_garantizado = (
                    "Anoté que ese horario te queda bien 🙏 Lo estamos terminando de "
                    "confirmar y te avisamos por aquí en un momento."
                )
            return {
                "ok": True,
                "estado": "aceptada" if confirmado else "por_confirmar",
                "instrucciones": "Ya se le envió al lead el mensaje. No agregues nada.",
            }
        await ctx.store.resolve_pending_booking(pending.id, "rechazado")
        caso.contrapropuesta = None
        if destino:
            await _enviar_al_dueno(
                ctx, destino,
                f"ℹ️ {quien} no puede el {cuando} (#{pending.id}); está proponiendo otro horario.",
            )
        if pending.kind == "reagendar":
            caso.cambio = None
            siguiente = (
                "Su visita de antes sigue en pie. Si propone otro día u hora, llama "
                "cambiar_visita con accion reagendar; si ya no quiere moverla, díselo."
            )
        else:
            caso.cita = None
            caso.escalado = ""
            siguiente = (
                "Ya no hay horario apartado. Si dijo un día u hora, llama propose_slots "
                "(con esa fecha) y ofrécele los que sí estén libres; si no, pregúntale "
                "qué día y hora le acomodan."
            )
        return {"ok": True, "estado": "rechazada", "instrucciones": siguiente}

    def _horario_pedido(self, args: dict[str, Any], tz: Any, hoy: date) -> tuple[date | None, tuple[int, int] | None]:
        """Día y hora que pidió el cliente: de sus palabras primero, de lo que
        mandó el modelo después (p. ej. cuando solo contesta «a las 11»)."""
        texto = self._texto_lead
        pedida = fecha_pedida(texto, hoy)
        fecha: date | None = date.fromisoformat(pedida) if pedida else None
        if fecha is None and args.get("fecha"):
            try:
                fecha = date.fromisoformat(str(args["fecha"]))
            except ValueError:
                fecha = None
        hm: tuple[int, int] | None = None
        horas = analizar_horas(texto)
        if horas:
            hm = _hora_24(horas[0].hora, horas[0].minuto, horas[0].meridiem)
        elif args.get("hora"):
            m = re.match(r"^\s*(\d{1,2})(?::(\d{2}))?\s*$", str(args["hora"]))
            if m and int(m.group(1)) < 24:
                hm = (int(m.group(1)), int(m.group(2) or 0))
        return fecha, hm

    async def _reagendar_visita(self, args: dict[str, Any]) -> dict[str, Any]:
        ctx, caso = self._ctx, self.caso
        servicio = SERVICIO_DE_PLAGA.get(caso.plaga or "")
        if ctx.calendar is None or not ctx.settings.owner_identity or servicio is None:
            # Sin agenda propia no hay cómo revisar el horario: lo ve el técnico.
            await self._escalar(
                "cliente",
                f"Quiere mover su visita ({caso.cita.get('label')}): {self._texto_lead[:160]}",
                self._puente(),
            )
            return {"ok": True, "estado": "con_el_dueno", "instrucciones": "Ya se le avisó. No agregues nada."}
        tz = _zona_del_negocio(ctx)
        hoy = datetime.now(tz).date()
        fecha, hm = self._horario_pedido(args, tz, hoy)
        if fecha is None or hm is None:
            return {
                "ok": False,
                "error": "falta_dia_u_hora",
                "instrucciones": (
                    "Pregúntale en una línea qué día y a qué hora le acomoda; con su "
                    "respuesta vuelve a llamar cambiar_visita."
                ),
            }
        dia = caso.cobertura.get("dia_restringido")
        if dia is not None and fecha.weekday() != dia:
            return {
                "ok": False,
                "error": "dia_no_disponible_en_su_zona",
                "instrucciones": (
                    f"En su zona solo se da servicio los {caso.cobertura.get('dia_nombre')}. "
                    "Díselo con honestidad y pregúntale qué día de esos le acomoda."
                ),
            }
        res = await ToolRuntime._propose_slots(self, {"fecha": fecha.isoformat()})
        if not res.get("ok"):
            return res
        ofrecidos = await ctx.store.get_offered_slots(self._conv.id)
        elegido = next(
            (s for s in ofrecidos
             if (s.start_utc.astimezone(tz).hour, s.start_utc.astimezone(tz).minute) == hm),
            None,
        )
        if elegido is None:
            libres = ", ".join(res.get("horas_libres") or [])
            res["instrucciones"] = (
                f"Esa hora NO está libre ese día. Horas libres: {libres}. Díselo con "
                "amabilidad y ofrécele las más cercanas (máximo 3, con su etiqueta tal "
                "cual); cuando elija, vuelve a llamar cambiar_visita con su fecha y hora."
            )
            return res

        fin = elegido.end_utc or elegido.start_utc + timedelta(
            minutes=SERVICE_RULES[servicio].duration_minutes
        )
        antes = str(caso.cita.get("label") or "")
        dia_nuevo = re.sub(r"^(hoy|mañana)\s+", "", elegido.label)
        motivo = str(args.get("motivo") or "").strip()[:160]
        nota = f"CAMBIO DE VISITA. Antes: {antes}." + (f" Motivo: {motivo}." if motivo else "")
        activa = await ctx.store.get_active_calendar_booking(self._conv.id)
        if activa is not None:
            pending = await ctx.store.create_pending_booking(
                conversation_id=self._conv.id,
                crm_conversation_id=self._crm_conv_id,
                service_key=servicio,
                start_utc=elegido.start_utc,
                end_utc=fin,
                label=elegido.label,
                direccion=caso.direccion_texto(),
                dia_confirmado=elegido.label,
                next_reminder_at=next_reminder(ctx.settings.booking_reminder_minutes),
                telefono_cliente=self._conv.wa_identity,
                kind="reagendar",
                google_event_id=activa.google_event_id,
                nota=nota[:300],
            )
            caso.cambio = {
                "label": dia_nuevo,
                "start_utc": elegido.start_utc.isoformat(),
                "folio": pending.id,
            }
            sigue = f" Mientras tanto, tu visita del {antes} sigue en pie." if antes else ""
        else:
            # La visita aún espera su primera aprobación: se mueve ESA solicitud.
            abierta = next(
                (p for p in await ctx.store.list_pending_bookings_pendientes()
                 if p.conversation_id == self._conv.id),
                None,
            )
            if abierta is None:
                await self._escalar(
                    "cliente",
                    f"Quiere mover su visita ({antes}): {self._texto_lead[:160]}",
                    self._puente(),
                )
                return {"ok": True, "estado": "con_el_dueno", "instrucciones": "Ya se le avisó. No agregues nada."}
            await ctx.store.reagendar_pendiente(abierta.id, elegido.start_utc, fin, elegido.label)
            pending = await ctx.store.get_pending_booking(abierta.id) or abierta
            caso.cita.update(label=dia_nuevo, start_utc=elegido.start_utc.isoformat(), folio=pending.id)
            sigue = ""
        await enviar_solicitud_aprobacion(ctx, pending)
        await ctx.store.clear_offered_slots(self._conv.id)
        await self._ficha({"notas": f"{nota} Nuevo horario pendiente de aprobar: {dia_nuevo}."[:480]})
        saludo = f"Gracias, {self._nombre_lead}" if self._nombre_lead else "Gracias"
        cuando = f"para {elegido.label}" if dia_nuevo != elegido.label else f"para el {elegido.label}"
        self.texto_garantizado = (
            f"👍 {saludo}: ese horario sí lo tenemos disponible {cuando}.\n\n"
            "⏳ Solo falta confirmarlo con el técnico que te corresponda; en cuanto "
            f"quede confirmado te avisamos por aquí.{sigue}"
        )
        return {
            "ok": True,
            "estado": "cambio_registrado",
            "instrucciones": "Ya se le envió al lead el mensaje. No agregues nada.",
        }

    async def _cancelar_visita(self, args: dict[str, Any]) -> dict[str, Any]:
        ctx, caso = self._ctx, self.caso
        if not caso.cancelacion_preguntada:
            # Primera vez: con mucha amabilidad se pregunta por qué y se ofrece
            # reagendar. Nada se cancela todavía.
            caso.cancelacion_preguntada = True
            self.texto_garantizado = (
                "Claro, sin problema 🙏 ¿Me cuentas si hubo algún inconveniente? "
                "Si prefieres, con gusto reagendamos tu visita para otro día."
            )
            return {
                "ok": True,
                "estado": "motivo_preguntado",
                "instrucciones": "Ya se le preguntó por qué. No agregues nada; espera su respuesta.",
            }
        if args.get("confirmado") is not True:
            return {
                "ok": False,
                "error": "falta_confirmacion",
                "instrucciones": (
                    "Cancela SOLO cuando ya contestó y dice claramente que sí quiere "
                    "cancelar (confirmado=true, con su motivo). Si dijo que va a "
                    "verificar su fecha, no canceles: «sin problema, aquí estaré»."
                ),
            }
        antes = str(caso.cita.get("label") or "su visita")
        motivo = str(args.get("motivo") or "").strip()[:200] or self._texto_lead[:200]
        manual = ""
        activa = await ctx.store.get_active_calendar_booking(self._conv.id)
        if activa is not None:
            try:
                await ctx.calendar.cancel_booking(activa.google_event_id)
            except (CalendarError, AttributeError) as exc:
                logger.warning("plagas: no pude borrar el evento al cancelar: %s", exc)
                manual = " ⚠️ No pude borrar el evento del Calendar: quítalo a mano."
            await ctx.store.cancel_calendar_booking(self._conv.id)
        for abierta in await ctx.store.list_pending_bookings_pendientes():
            if abierta.conversation_id == self._conv.id:
                await ctx.store.resolve_pending_booking(abierta.id, "rechazado")
        caso.cita = None
        caso.cambio = None
        caso.cancelacion_preguntada = False
        destino = ctx.settings.aviso_dueno_identity or ctx.settings.owner_identity
        if destino:
            quien = self._nombre_lead or "Cliente"
            await _enviar_al_dueno(
                ctx,
                destino,
                f"❌ {quien} ({self._conv.wa_identity}) canceló su visita del {antes}.\n"
                f"Motivo: {motivo}{manual}",
            )
        await self._ficha({"notas": f"VISITA CANCELADA por el cliente ({antes}). Motivo: {motivo}"[:480]})
        nombre = f", {self._nombre_lead}" if self._nombre_lead else ""
        self.texto_garantizado = (
            f"Listo{nombre}: tu visita del {antes} quedó cancelada 🙏 Si más adelante "
            "quieres retomarla, aquí estaremos para ayudarte."
        )
        return {
            "ok": True,
            "estado": "cancelada",
            "instrucciones": "Ya se le envió al lead el mensaje. No agregues nada.",
        }

    async def _registrar_pendiente(self, chosen: OfferedSlot) -> None:
        """Con agenda propia: la solicitud queda con folio y se le pide al dueño
        «sí <folio>» / «no <folio>» (app/approvals.py). Aprobada, se crea el
        evento en Google Calendar; el recordatorio la reintenta si no llegó.
        Sin agenda propia o sin dueño configurado no hace nada."""
        ctx = self._ctx
        caso = self.caso
        servicio = SERVICIO_DE_PLAGA.get(caso.plaga or "")
        if ctx.calendar is None or not ctx.settings.owner_identity or servicio is None:
            return
        fin = chosen.end_utc or chosen.start_utc + timedelta(
            minutes=SERVICE_RULES[servicio].duration_minutes
        )
        precio = (caso.cotizacion or {}).get("precio")
        pending = await ctx.store.create_pending_booking(
            conversation_id=self._conv.id,
            crm_conversation_id=self._crm_conv_id,
            service_key=servicio,
            start_utc=chosen.start_utc,
            end_utc=fin,
            label=chosen.label,
            direccion=caso.direccion_texto(),
            dia_confirmado=chosen.label,
            next_reminder_at=next_reminder(ctx.settings.booking_reminder_minutes),
            costo_cotizado=float(precio) if isinstance(precio, (int, float)) else 0.0,
            telefono_cliente=self._conv.wa_identity,
            nota=self._nota_de_zona(),
        )
        if caso.cita is not None:
            caso.cita["folio"] = pending.id
        await enviar_solicitud_aprobacion(ctx, pending)

    def _confirma_de_inmediato(self) -> bool:
        """¿La visita se agenda al instante, sin que nadie la apruebe?

        Sí con calendario propio y plaga con regla de agenda: el horario elegido
        ya salió de la disponibilidad real, así que ES una confirmación. No en
        zonas de un solo día (Toluca, Lerma): ahí el dueño decide cada vez.

        Solo si AGENDA_CONFIRMACION=inmediata. Por defecto es `aprobacion`: aunque
        el horario esté libre, antes se confirma con el técnico designado (4 oct).
        """
        return (
            getattr(self._ctx.settings, "agenda_confirmacion", "aprobacion") == "inmediata"
            and self._ctx.calendar is not None
            and SERVICIO_DE_PLAGA.get(self.caso.plaga or "") is not None
            and self.caso.cobertura.get("dia_restringido") is None
        )

    async def _confirmar_visita(self, chosen: OfferedSlot) -> dict[str, Any] | None:
        """Agenda YA en Google Calendar. Devuelve el resultado de la herramienta, o
        None si el calendario falló (entonces se cae a la solicitud con aprobación)."""
        ctx, caso = self._ctx, self.caso
        servicio = SERVICIO_DE_PLAGA[caso.plaga or ""]
        regla = SERVICE_RULES[servicio]
        fin = chosen.end_utc or chosen.start_utc + timedelta(minutes=regla.duration_minutes)
        precio = (caso.cotizacion or {}).get("precio")
        descripcion = construir_description_evento(
            texto_base="Agendado por Nea (confirmación inmediata).",
            telefono_cliente=self._conv.wa_identity,
            direccion=caso.direccion_texto(),
            service_key=servicio,
            costo=float(precio) if isinstance(precio, (int, float)) else 0.0,
            crm_conversation_id=self._crm_conv_id,
        )
        try:
            resultado = await ctx.calendar.create_booking(
                chosen.start_utc, fin, f"Visita {regla.label}", descripcion, servicio
            )
        except CalendarSlotTaken as exc:
            # Se ocupó entre que se lo ofrecimos y dio su dirección: alternativas reales.
            frescos = _slots_from_payload(self._conv.id, exc.slots)
            await ctx.store.replace_offered_slots(self._conv.id, frescos)
            return {
                "ok": False,
                "error": "slot_taken",
                "detalle": "ese horario se acaba de ocupar; discúlpate breve y ofrece estas alternativas",
                "slots": _slots_for_llm(frescos),
            }
        except CalendarError as exc:
            logger.warning("plagas: Google Calendar no agendó (%s) — queda como solicitud", exc)
            return None

        dia = re.sub(r"^(hoy|mañana)\s+", "", chosen.label)
        await ctx.store.save_calendar_booking(
            self._conv.id, resultado["event_id"], servicio, chosen.start_utc, fin
        )
        await ctx.store.clear_offered_slots(self._conv.id)
        caso.cita = {
            "label": dia,
            "start_utc": chosen.start_utc.isoformat(),
            "estado": "confirmada",
            "event_id": resultado["event_id"],
        }
        self.booked = True
        info = catalogo.PLAGAS[caso.plaga or ""]
        await self._ficha({
            "cita_confirmada": dia,
            "calificado": True,
            "resultado": "agendo",
            "notas": (
                f"VISITA AGENDADA: {dia} — {info.get('nombre', '')} — "
                f"{caso.cotizacion['linea'] if caso.cotizacion else ''} — {caso.direccion_texto()}"
            )[:480],
        })
        # Al dueño: aviso informativo (nada que aprobar). Mejor esfuerzo.
        await avisar_cita_agendada(
            ctx, identidad_lead=self._conv.wa_identity, nombre=self._nombre_lead,
            caso=caso, etiqueta=chosen.label,
        )
        saludo = f"Listo, {self._nombre_lead}" if self._nombre_lead else "Listo"
        cuando = f"para {chosen.label}" if dia != chosen.label else f"para el {chosen.label}"
        partes = [
            f"✅ {saludo}: tu visita quedó agendada {cuando}.",
            f"📍 {caso.direccion_texto()}",
            "👷 Cuando tengamos designado a tu técnico, te enviaremos un mensaje por aquí.",
        ]
        if info.get("contencion"):
            partes.append(f"⚠️ {info['contencion']}")
        self.texto_garantizado = "\n\n".join(partes)
        return {
            "ok": True,
            "estado": "visita_confirmada",
            "instrucciones": "La visita YA quedó agendada y se le avisó al lead. No agregues nada.",
        }

    async def _solicitar_visita(self, chosen: OfferedSlot) -> dict[str, Any]:
        """Registra la visita. Con calendario propio se AGENDA al instante (ver
        `_confirma_de_inmediato`); si no, queda PENDIENTE de aprobación.

        Pendiente: no se toca el calendario real; la solicitud se anota en la
        ficha y el dueño la confirma con «sí N».
        """
        if self._confirma_de_inmediato():
            resultado = await self._confirmar_visita(chosen)
            if resultado is not None:
                return resultado
        caso = self.caso
        info = catalogo.PLAGAS[caso.plaga or ""] if caso.plaga else {}
        # La ficha y el expediente guardan el día sin «hoy»/«mañana»: se leen
        # días después y para entonces ya no es mañana.
        dia = re.sub(r"^(hoy|mañana)\s+", "", chosen.label)
        cuando = f"para {chosen.label}" if dia != chosen.label else f"para el {chosen.label}"
        caso.cita = {
            "label": dia,
            "start_utc": chosen.start_utc.isoformat(),
            "estado": "pendiente_de_aprobacion",
        }
        await self._registrar_pendiente(chosen)
        await self._ctx.store.clear_offered_slots(self._conv.id)
        self.booked = True
        if not caso.cita.get("folio"):
            # Sin folio (sin calendario propio o sin dueño que apruebe) la
            # conversación se le pasa al dueño y la IA se apaga. CON folio NO:
            # el dueño aprueba con «sí N» y Nea tiene que poder escribirle al
            # cliente la confirmación, y el CRM no deja escribir con la IA apagada.
            self.handoff_reason = "cliente"
            caso.escalado = f"Solicitud de visita: {dia}"
        await self._ficha({
            "cita_solicitada": dia,
            "calificado": True,
            "resultado": "agendo",
            "notas": (
                f"SOLICITUD DE VISITA pendiente de aprobar: {dia} — "
                f"{info.get('nombre', '')} — {caso.cotizacion['linea'] if caso.cotizacion else ''} — "
                f"{caso.direccion_texto()}"
            )[:480],
        })
        saludo = f"Gracias, {self._nombre_lead}" if self._nombre_lead else "Gracias"
        # Un solo mensaje, sin contradicción y sin la palabra «solicitud»: el horario
        # SÍ está disponible; lo que falta es confirmarlo con el técnico designado.
        partes = [
            f"👍 {saludo}: ese horario sí lo tenemos disponible {cuando}.",
            f"📍 {caso.direccion_texto()}",
            f"⏳ Solo falta confirmarlo con el técnico que te corresponda; en cuanto "
            "quede confirmado te avisamos por aquí.",
        ]
        if caso.cobertura.get("dia_restringido") is not None:
            partes.append(f"En tu zona damos servicio los {caso.cobertura.get('dia_nombre')}.")
        if info.get("contencion"):
            partes.append(f"⚠️ {info['contencion']}")
        self.texto_garantizado = "\n\n".join(partes)
        return {
            "ok": True,
            "estado": "solicitud_registrada",
            "instrucciones": "Ya se le envió al lead la confirmación de su solicitud. No agregues nada.",
        }

# Días que el lead puede PROponer («el sábado», «mañana», «pasado mañana», «el 12»).
# «mañana» sola es el día; «de la mañana» es la hora del reloj y no cuenta.
_RE_DIA_PROPUESTO = re.compile(
    r"\b(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo|hoy|pasado manana)\b"
    r"|(?<!la )\bmanana\b"
    r"|\bel\s+\d{1,2}(?:\s+de\s+[a-z]+)?\b"
    r"|\b\d{1,2}/\d{1,2}\b"
)

# Cómo dice la gente cada tipo de inmueble.
_DICE_INMUEBLE: dict[str, tuple[str, ...]] = {
    # «Toda la casa» o «en mi casa» los dice también quien vive en un depa:
    # cuenta «casa» solo cuando se dice como TIPO de inmueble.
    "casa": (
        r"^\W*casa\b", r"\b(es|vivo en|tengo|son|una|tipo) (una )?casa\b",
        # «…detrás del refri. Casa en la Del Valle»: al empezar una frase.
        r"[.!?;:]\s*casa\b", r",\s*casa (en|de)\b",
        r"\bcasa (sola|propia|habitacion|de (un|dos|tres|\d)|grande|chica)\b",
        r"\bcasita\b", r"\bresidencia\b",
    ),
    "departamento": (
        r"\bdep(a|as|to|tos|artamento|artamentos)\b", r"\bapartamento\b", r"\bcondominio\b",
    ),
    "local_comercial": (
        r"\blocal\b", r"\bnegocio\b", r"\brestauran", r"\bcomercio\b", r"\boficina",
        # «La bodega» de una casa no es un local: solo «es/tengo una bodega».
        r"\b(es|tengo) una bodega\b", r"\btienda\b", r"\bcafeteria\b", r"\btaqueria\b",
        r"\bfonda\b",
    ),
    "edificio": (r"\bedificio",),
}
_NUMEROS = {
    # «un» y «una» no: «vi una araña» no dice que haya un baño.
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11,
    "doce": 12, "quince": 15, "veinte": 20, "treinta": 30, "cuarenta": 40,
    "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90,
    "cien": 100, "doscientos": 200, "trescientos": 300,
}


def bloque_de_dos_cucarachas() -> str:
    """Lo que se le dice a quien tiene cucaracha alemana Y americana: solo catálogo."""
    alemana = catalogo.PLAGAS["cucaracha_alemana"]
    americana = catalogo.PLAGAS["cucaracha_americana"]

    def _visitas(info: dict[str, Any]) -> str:
        return info["visitas"][:1].upper() + info["visitas"][1:]

    lineas = [
        "Por lo que me cuentas tienes las dos 🪳: la cucaracha alemana (la chica) y "
        "la americana (la grande).",
    ]
    if alemana.get("tranquilidad"):
        lineas.append(f"💚 {alemana['tranquilidad']}")
    lineas += [
        f"🛠️ Alemana: {alemana.get('resumen') or alemana['procedimiento']}\n🗓️ {_visitas(alemana)}.",
        f"🛠️ Americana: {americana.get('resumen') or americana['procedimiento']}\n🗓️ {_visitas(americana)}.",
        catalogo.PREGUNTA_URGENCIA,
    ]
    return "\n\n".join(lineas)


def bloque_de_tratamiento(plaga: str, texto_del_lead: str = "") -> str:
    """Lo que se le dice al lead del tratamiento al confirmar la plaga: solo catálogo."""
    info = catalogo.PLAGAS[plaga]
    visitas = info["visitas"][:1].upper() + info["visitas"][1:]
    lineas = [f"🛠️ {info.get('resumen') or info['procedimiento']}", f"🗓️ {visitas}."]
    if info.get("tranquilidad"):
        lineas.insert(0, f"💚 {info['tranquilidad']}")
    # La precaución de la araña va solo si el lead describió una peligrosa
    # (sección 4.3): decírsela a todo el que tiene arañas es alarmar de más.
    if info.get("tranquilidad_peligrosa") and re.search(
        catalogo.ARANA_PELIGROSA, normalizar(texto_del_lead)
    ):
        lineas.append(info["tranquilidad_peligrosa"])
    return "\n".join(lineas) + f"\n\n{catalogo.PREGUNTA_URGENCIA}"


def _alias(texto: str) -> str | None:
    """La plaga del catálogo a la que se refiere un texto, o None."""
    plano = normalizar(texto)
    # El catálogo de alias va de lo específico a lo general: gana el primero.
    return next((clave for patron, clave in catalogo.ALIAS if re.search(patron, plano)), None)


_CERO_RE = re.compile(r"\bno (tengo|hay|tenemos|cuento|tiene|tienen)\b|\bni (una|un)\b|\bsin ningun")
_CERO_PALABRAS = ("ninguna", "ninguno", "ningun", "cero", "nada")


def _dice_cero(plano: str) -> bool:
    """¿El texto dice «ninguna», «no tengo», «cero»…, aunque tenga una errata?

    Caso real (4 oct): el cliente escribió «niguna silla secretarial» y el bot le
    volvió a preguntar cuántas había. Una errata no es un «no contesté».
    """
    if _CERO_RE.search(plano):
        return True
    for palabra in re.findall(r"[a-z]+", plano):
        if palabra in _CERO_PALABRAS:
            return True
        if len(palabra) >= 5 and difflib.get_close_matches(palabra, ("ninguna", "ninguno"), n=1, cutoff=0.8):
            return True
    return False


def _ultima_plaga_nombrada(texto: str) -> str | None:
    """La plaga que un texto nombra AL FINAL («no son cucarachas, son chinches»).

    `_alias` devuelve la primera del catálogo que aparezca; aquí manda la que se
    dijo último, que es la que el cliente quiere decir.
    """
    plano = normalizar(texto)
    hallazgos = [
        (m.start(), clave)
        for patron, clave in catalogo.ALIAS
        for m in re.finditer(patron, plano)
    ]
    return max(hallazgos)[1] if hallazgos else None


def _misma_familia(a: str, b: str) -> bool:
    """¿Las dos claves hablan de la misma plaga? (cucaracha* es una familia)."""
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return True
    if a.startswith("cucaracha") and b.startswith("cucaracha"):
        return True
    return a == b
