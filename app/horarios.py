"""Interpretación de la hora que dice el LEAD, y su contraste con los slots.

Por qué existe este módulo: `_resolve_offered` validaba que el `start_utc` que
manda el modelo estuviera entre los slots ofrecidos, pero **nunca miraba lo que
el cliente había escrito**. En el caso real:

    Agente ofrece: 09:00, 09:30, 10:00 (todos de la MAÑANA)
    Cliente dice:  "si mañana 21 dept 9:30 pm"
    Agente agenda: 09:30 — y le confirma "mañana ... a las 09:30"

El modelo leyó "9:30 pm" como el slot de 09:30 AM, y el servidor lo aceptó
porque ese slot SÍ estaba ofrecido. El epoch era válido; la interpretación del
cliente no.

Aquí se extraen las horas del mensaje del lead —con su meridiano explícito o
inferido— y se contrastan contra la hora LOCAL REAL del slot elegido. Si no
cuadran, el agendamiento se rechaza con un error accionable que le dice al
modelo que pregunte, en vez de asumir.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ_POR_DEFECTO = "America/Mexico_City"


def zona_agente(agent_timezone: str | None) -> ZoneInfo:
    """Zona del negocio, tolerante a un valor inválido en la configuración."""
    try:
        return ZoneInfo(agent_timezone or TZ_POR_DEFECTO)
    except Exception:
        return ZoneInfo(TZ_POR_DEFECTO)


def _norm(texto: str) -> str:
    return texto.translate(str.maketrans("áéíóúüñ", "aeiouun")).lower()


@dataclass(frozen=True)
class HoraLead:
    """Una hora mencionada por el lead, ya interpretada."""

    hora: int            # hora de 12 h (1-12) tal como se leería en un reloj
    minuto: int
    meridiem: str | None  # "am" | "pm" | None si el lead no lo dijo
    crudo: str

    @property
    def es_pm(self) -> bool | None:
        if self.meridiem is None:
            return None
        return self.meridiem == "pm"

    def como_texto(self) -> str:
        sufijo = {"am": " de la mañana", "pm": " de la noche", None: ""}[self.meridiem]
        return f"{self.hora}:{self.minuto:02d}{sufijo}"


# Separador entre hora y minutos. El punto y coma NO es un capricho: el caso
# real que llegó por WhatsApp fue "si mañana 21 dept 9;30 pm", con punto y coma
# en vez de dos puntos. Sin soportarlo, el parser no encontraba ninguna hora,
# la validación no tenía nada que contrastar y la reserva pasaba igual — el bug
# seguía vivo. El punto SÍ se excluye a propósito: "9.30" chocaría con
# cantidades decimales como "$1,200.50" e inyectaría horas falsas.
_SEP_HORA = r"[:;]"

# "9:30 pm" / "9 pm" / "9;30 pm" / "4pm / "9:30 p.m."
_RE_MERIDIEM_ADJUNTO = re.compile(
    r"\b(\d{1,2})(?:" + _SEP_HORA + r"(\d{2}))?\s*(a\s?\.?\s?m\.?|p\s?\.?\s?m\.?)\b"
)
# "9:30 de la noche" / "10 por la tarde" / "7 de la manana" / "3 de la madrugada"
_RE_PALABRA_DIA = re.compile(
    r"\b(\d{1,2})(?:" + _SEP_HORA + r"(\d{2}))?\s*(?:de|por|en)\s+la\s+"
    r"(manana|tarde|noche|madrugada)\b"
)
# "9:30" / "9;30" / "a las 9" / "a las 21". El lookahead evita que "a las 21:30"
# se lea como las 21:00 — sin él, el patrón corto se come los minutos.
_RE_HORA_SIMPLE = re.compile(
    r"\b(\d{1,2})" + _SEP_HORA + r"(\d{2})\b"
    r"|\ba\s+las\s+(\d{1,2})\b(?!" + _SEP_HORA + r")"
)

# Frases que fijan el meridiano de TODA la frase, cuando el lead no lo puso
# pegado a la hora (p. ej. "mejor a las 9:30 de la noche").
_PALABRA_A_MERIDIEM = {
    "manana": "am",
    "madrugada": "am",
    "tarde": "pm",
    "noche": "pm",
}


def meridiem_global(texto: str) -> str | None:
    """Meridiano declarado en la frase: "de la mañana", "de la noche"…

    OJO: "mañana" SOLA significa *el día de mañana*, no la mañana del reloj.
    Solo cuenta cuando viene como "de/por/en la mañana".
    """
    t = _norm(texto)
    encontrados = set()
    for palabra, mer in _PALABRA_A_MERIDIEM.items():
        if re.search(rf"\b(?:de|por|en)\s+la\s+{palabra}\b", t):
            encontrados.add(mer)
    if len(encontrados) == 1:
        return encontrados.pop()
    return None


def _a_meridiem(token: str) -> str:
    return "am" if token.replace(" ", "").replace(".", "").startswith("a") else "pm"


def analizar_horas(texto: str) -> list[HoraLead]:
    """Todas las horas mencionadas en el mensaje del lead, ya interpretadas."""
    if not texto:
        return []
    t = _norm(texto)
    global_mer = meridiem_global(texto)

    # Las que traen meridiano explícito pegado a la hora mandan sobre las demás.
    con_meridiem: list[HoraLead] = []
    ocupados: list[tuple[int, int]] = []
    for m in _RE_MERIDIEM_ADJUNTO.finditer(t):
        hora, minuto, token = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if not (0 <= hora <= 23 and 0 <= minuto <= 59):
            continue
        con_meridiem.append(
            HoraLead(_hora_12(hora), minuto, _a_meridiem(token), m.group(0).strip())
        )
        ocupados.append(m.span())

    con_palabra: list[HoraLead] = []
    for m in _RE_PALABRA_DIA.finditer(t):
        if any(s <= m.start() < e for s, e in ocupados):
            continue
        hora, minuto, palabra = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if not (0 <= hora <= 23 and 0 <= minuto <= 59):
            continue
        con_palabra.append(
            HoraLead(
                _hora_12(hora), minuto, _PALABRA_A_MERIDIEM[palabra], m.group(0).strip()
            )
        )
        ocupados.append(m.span())

    simples: list[HoraLead] = []
    for m in _RE_HORA_SIMPLE.finditer(t):
        if any(s <= m.start() < e for s, e in ocupados):
            continue
        bruto = m.group(1) or m.group(3)
        if bruto is None:
            continue
        hora = int(bruto)
        minuto = int(m.group(2) or 0)
        if not (0 <= hora <= 23 and 0 <= minuto <= 59):
            continue
        mer = global_mer if len(con_meridiem) + len(con_palabra) == 0 else None
        # "21:30" ya trae el meridiano implícito en el propio número.
        if hora > 12:
            mer = "pm"
        simples.append(HoraLead(_hora_12(hora), minuto, mer, m.group(0).strip()))

    # Deduplicado por (hora, minuto): la MISMA hora puede capturarse dos veces
    # porque los patrones se solapan ("a las 9:30 pm" lo agarran tanto el
    # patrón con meridiano como el simple). Reglas:
    #
    #   - Un meridiano EXPLÍCITO reemplaza a la lectura vaga de la misma hora.
    #   - Pero dos meridianos explícitos DISTINTOS conviven: el lead pudo
    #     corregirse. Ejemplo real: dice "9:30 pm", el agente pregunta "¿de la
    #     mañana o de la noche?", y el lead contesta "de la mañana". Si nos
    #     quedáramos con la primera lectura, la reserva quedaría BLOQUEADA para
    #     siempre en esa conversación.
    vistos: dict[tuple[int, int], list[HoraLead]] = {}
    for h in con_meridiem + con_palabra + simples:
        clave = (h.hora, h.minuto)
        grupo = vistos.setdefault(clave, [])
        if any(g.meridiem == h.meridiem for g in grupo):
            continue  # esa misma lectura ya está
        if h.meridiem is None:
            if grupo:
                continue  # ya hay una lectura con meridiano: esta no aporta
            grupo.append(h)
        else:
            vistos[clave] = [g for g in grupo if g.meridiem is not None] + [h]

    return [h for grupo in vistos.values() for h in grupo]


def _hora_12(hora: int) -> int:
    """23 -> 11, 12 -> 12, 0 -> 12, 9 -> 9."""
    if hora == 0:
        return 12
    return hora - 12 if hora > 12 else hora


def _coincide(h: HoraLead, local: datetime) -> bool:
    slot_h12 = local.hour % 12 or 12
    if h.hora != slot_h12 or h.minuto != local.minute:
        return False
    if h.meridiem is None:
        return True  # el lead no dijo meridiano: no hay nada que contrastar
    return h.es_pm == (local.hour >= 12)


def validar_hora_contra_slot(
    texto_lead: str, slot_utc: datetime, tz: ZoneInfo
) -> tuple[bool, dict | None]:
    """¿Lo que dijo el lead corresponde a la hora LOCAL del slot elegido?

    Devuelve `(True, None)` si no hay nada que objetar, o `(False, error)` con
    el contrato de error listo para el modelo.
    """
    horas = analizar_horas(texto_lead)
    if not horas:
        # El lead no dio una hora (p. ej. "sí, perfecto" sobre un horario que el
        # agente ya nombró). Eso lo cubre el candado de `parece_confirmar_horario`.
        return True, None

    if slot_utc.tzinfo is None:
        slot_utc = slot_utc.replace(tzinfo=timezone.utc)
    local = slot_utc.astimezone(tz)

    if any(_coincide(h, local) for h in horas):
        return True, None

    slot_pm = local.hour >= 12
    sufijo = "de la noche" if slot_pm else "de la mañana"
    etiqueta_slot = f"{local.hour:02d}:{local.minute:02d} ({sufijo})"

    # ¿Coincide en el reloj de 12 h pero con el meridiano al revés? Es
    # exactamente el caso "9:30 pm" vs slot de 09:30 — el más peligroso, porque
    # parece correcto y manda al técnico a la hora equivocada.
    choque_meridiano = any(
        h.hora == (local.hour % 12 or 12) and h.minuto == local.minute for h in horas
    )
    dicho = ", ".join(h.como_texto() for h in horas)

    if choque_meridiano:
        return False, {
            "ok": False,
            "error": "ambiguo_am_pm",
            "hora_del_lead": dicho,
            "hora_del_slot": etiqueta_slot,
            "mensaje_al_cliente": (
                f"Solo para confirmar: ¿{horas[0].hora}:{horas[0].minuto:02d} de la "
                f"mañana o de la noche? Los horarios que te ofrecí fueron {sufijo}."
            ),
            "detalle": (
                f"El lead dijo «{dicho}», pero el horario que estás intentando "
                f"apartar es {etiqueta_slot}. El meridiano NO cuadra."
            ),
            "instrucciones": (
                "NO agendes: primero pregunta explícitamente y espera su "
                "respuesta. Usa algo como: «Solo para confirmar: ¿"
                f"{horas[0].hora}:{horas[0].minuto:02d} de la mañana o de la "
                f"noche? Los horarios que te ofrecí fueron {sufijo}.» "
                "Si el lead quiere una hora que NO está entre las que ofreciste, "
                "no la apartes: usa propose_slots y ofrécele las que sí hay."
            ),
        }

    # El lead pidió una hora que nadie le ofreció.
    return False, {
        "ok": False,
        "error": "hora_no_ofrecida",
        "hora_del_lead": dicho,
        "hora_del_slot": etiqueta_slot,
        "mensaje_al_cliente": (
            "Ese horario no lo tengo disponible 😔 ¿Te comparto los que sí tengo?"
        ),
        "detalle": (
            f"El lead habló de «{dicho}» pero el horario elegido es "
            f"{etiqueta_slot}, y ninguna de las horas que mencionó corresponde "
            "a un horario que le hayas ofrecido."
        ),
        "instrucciones": (
            "NO agendes una hora que no ofreciste, y no asumas que está libre. "
            "Vuelve a proponer horarios reales con propose_slots y ofrécele "
            "solo esos."
        ),
    }
