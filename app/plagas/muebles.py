"""Cuántos colchones, sillones y sillas dijo el cliente, con sus palabras.

Caso real (4 oct): «…tengo 2 colchones, 2 sillon 1 silla secretarial» en el PRIMER
mensaje, y el bot preguntó «¿cuántos colchones hay?». Lo que el cliente ya escribió se
toma directo de su texto; el modelo no tiene que acordarse de pasarlo.

Solo cuenta lo dicho junto a su sustantivo («2 colchones», «una silla secretarial»,
«ninguna silla de comedor»): un número suelto no se adivina.
"""
from __future__ import annotations

import re

from app.plagas.texto import normalizar

_PALABRAS = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
}
_NUM = r"(\d{1,3}|" + "|".join(_PALABRAS) + r")"

# variable → patrón del sustantivo (el orden importa: lo específico va primero)
_COSAS = {
    "sillas_secretariales": r"sillas?\s+(?:secretaria(?:l(?:es)?)?|de\s+oficina)",
    "sillas_comedor": r"sillas?\s+(?:de\s+)?comedor",
    "sillones": r"(?:sillon(?:es)?|sofas?)",
    "colchones": r"colchon(?:es)?",
    # Lo que pide el precio de la cucaracha americana y del local comercial. «Dos
    # baños y medio» no es 2: queda sin leer y se pregunta.
    "sanitarios": r"(?:banos?|sanitarios?|wc)(?!\s+y\s+medio)",
    "registros": r"(?:registros?|coladeras?)",
    "refrigeradores": r"(?:refris?|refrigeradores?|congeladores?)",
}
_CERO = r"(?:nin?gun[ao]s?|ni\s+(?:una|un)|cero|sin|no\s+(?:tengo|hay|tenemos|cuento\s+con))"


def _valor(token: str) -> int:
    return int(token) if token.isdigit() else _PALABRAS[token]


def muebles_dichos(mensajes: list[str]) -> dict[str, int]:
    """{variable: cantidad} de lo que el cliente dijo; lo último que dijo manda."""
    dichos: dict[str, int] = {}
    for mensaje in mensajes:
        plano = normalizar(mensaje)
        for clave, sustantivo in _COSAS.items():
            for m in re.finditer(r"\b" + _NUM + r"\s+" + sustantivo + r"\b", plano):
                dichos[clave] = _valor(m.group(1))
            # «ninguna silla secretarial», «no tengo sillones», «sin colchones»
            if re.search(r"\b" + _CERO + r"\s+(?:\w+\s+){0,2}?" + sustantivo + r"\b", plano):
                dichos[clave] = 0
    return dichos
