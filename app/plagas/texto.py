"""Utilidades de texto para comparar lo que escribe el lead (sin acentos ni mayúsculas)."""
from __future__ import annotations

import re
import unicodedata

_VACIAS = frozenset(
    "que los las del una uno unos unas por con para como pero mas muy hay son "
    "esta estan este esto esa ese eso mis sus tus nos les the and tengo tiene "
    "tienen creo pues bueno asi aqui alla ahi cuando donde desde hasta entre "
    "sobre algo todo toda todos todas ver vez veo visto han has hemos".split()
)


def normalizar(texto: str) -> str:
    """minúsculas, sin acentos, espacios colapsados."""
    s = unicodedata.normalize("NFKD", texto or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower()).strip()


def palabras(texto: str) -> list[str]:
    """Palabras con contenido (3+ letras, sin las vacías), normalizadas."""
    return [
        w for w in re.findall(r"[a-z0-9ñ]+", normalizar(texto))
        if len(w) >= 3 and w not in _VACIAS
    ]


AFIRMACIONES = re.compile(
    r"^\W*(si+|sip|simon|claro|exacto|asi es|correcto|aja|afirmativo|efectivamente|"
    r"eso|esa|ese|tal cual|creo que si|si claro|si exacto)\b",
)


def es_afirmacion(texto: str) -> bool:
    return bool(AFIRMACIONES.match(normalizar(texto)))
