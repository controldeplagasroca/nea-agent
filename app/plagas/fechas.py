"""El día que el cliente pide con sus palabras («mañana», «el martes», «el 12»).

Si el cliente dice «¿tienen mañana a las 10?», Nea consulta ESE día en el calendario
(y le confirma si está libre) en vez de depender de que el modelo recuerde pasar la
fecha. Solo entiende lo común; lo demás devuelve None y se ofrece el reparto normal.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from app.plagas.texto import normalizar

_DIAS = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "domingo": 6,
}
_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def _fecha(anio: int, mes: int, dia: int) -> date | None:
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def _proxima(hoy: date, mes: int, dia: int) -> date | None:
    """El próximo `dia/mes` desde hoy (este año, o el siguiente si ya pasó)."""
    esta = _fecha(hoy.year, mes, dia)
    if esta is not None and esta >= hoy:
        return esta
    return _fecha(hoy.year + 1, mes, dia)


def fecha_pedida(texto: str, hoy: date) -> str | None:
    """AAAA-MM-DD del día que el texto pide, o None si no pide uno claro."""
    t = normalizar(texto)
    if not t:
        return None
    if re.search(r"\bpasado manana\b", t):
        return (hoy + timedelta(days=2)).isoformat()
    # «mañana» el día; «en la mañana» es la hora del reloj y no cuenta.
    if re.search(r"(?<!la )\bmanana\b", t):
        return (hoy + timedelta(days=1)).isoformat()
    if re.search(r"\bhoy\b", t):
        return hoy.isoformat()

    m = re.search(r"\b(\d{1,2}) de (" + "|".join(_MESES) + r")\b", t)
    if m:
        f = _proxima(hoy, _MESES[m.group(2)], int(m.group(1)))
        return f.isoformat() if f else None

    m = re.search(r"\b(" + "|".join(_DIAS) + r")\b", t)
    if m:
        faltan = (_DIAS[m.group(1)] - hoy.weekday()) % 7 or 7
        return (hoy + timedelta(days=faltan)).isoformat()

    m = re.search(r"\b(\d{1,2})/(\d{1,2})\b", t)
    if m:
        f = _proxima(hoy, int(m.group(2)), int(m.group(1)))
        return f.isoformat() if f else None

    m = re.search(r"\bel (\d{1,2})\b(?! ?(?:%|de la|colchon|sillon|metros|m2))", t)
    if m:
        dia = int(m.group(1))
        for mes_extra in (0, 1):
            mes = hoy.month + mes_extra
            anio = hoy.year + (1 if mes > 12 else 0)
            f = _fecha(anio, mes - 12 if mes > 12 else mes, dia)
            if f is not None and f >= hoy:
                return f.isoformat()
    return None
