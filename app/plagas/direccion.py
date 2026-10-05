"""La dirección que el cliente ya escribió, leída por el servidor.

Caso real (4 oct): «vivo en Portales en 03300 calle Vértiz 2200, alcaldía Benito Juárez»
en el PRIMER mensaje, y al final el bot pidió «mándame tu dirección completa». El modelo
tiene que acordarse de pasarla a book_session; si no lo hace, se pierde. Aquí se lee de
lo que el cliente escribió, sin depender de él.

Solo se toma lo que está junto a su marcador («calle», «colonia», «alcaldía», «int.»…);
no se adivina nada sin marcador, salvo «vivo en X en <código postal>».
"""
from __future__ import annotations

import re
import unicodedata

_CORTE = (
    r"col|colonia|alcaldia|municipio|delegacion|cp|c\.p|calle|av|avenida|int|interior|"
    r"depto|dpto|departamento|esquina|entre|ref|referencia|tengo|vivo|quiero|y|con|que|"
    r"para|por|mi|es|esta|estoy|somos|soy|en"
)
_MARCADORES_CALLE = (
    r"calle|av\.?|avenida|calzada|calz\.?|privada|cerrada|andador|eje|boulevard|"
    r"blvd\.?|periferico|circuito|prolongacion|callejon"
)


def _plano(texto: str) -> str:
    """Minúsculas y sin acentos, carácter por carácter: conserva el largo del original."""
    out = []
    for c in texto:
        d = unicodedata.normalize("NFKD", c)
        out.append((d[0] if d else c).lower())
    return "".join(out)


def _titulo(texto: str) -> str:
    return " ".join(p.capitalize() if len(p) > 2 else p for p in texto.split())


def _palabras_hasta_corte(original: str, plano: str, inicio: int, maximo: int = 4) -> tuple[str, int]:
    """Hasta `maximo` palabras desde `inicio`, sin cruzar un número ni una palabra de corte."""
    palabras: list[str] = []
    pos = inicio
    for m in re.finditer(r"[^\s,;.()]+", plano[inicio:]):
        token = m.group(0)
        if re.fullmatch(r"#?\d+[a-z]?", token) or re.fullmatch(rf"(?:{_CORTE})\.?", token):
            break
        palabras.append(original[inicio + m.start(): inicio + m.end()])
        pos = inicio + m.end()
        if len(palabras) >= maximo:
            break
    return " ".join(palabras), pos


def direccion_dicha(texto: str) -> dict[str, str]:
    """Campos de la dirección que `texto` dice con claridad (vacío si no dice ninguno)."""
    original = texto or ""
    plano = _plano(original)
    campos: dict[str, str] = {}

    m = re.search(rf"\b(?:{_MARCADORES_CALLE})\s+", plano)
    if m:
        marcador = m.group(0).strip().rstrip(".")
        nombre, fin = _palabras_hasta_corte(original, plano, m.end())
        if nombre:
            campos["calle"] = _titulo(nombre) if marcador == "calle" else f"{marcador.capitalize()}. {_titulo(nombre)}"
            n = re.match(r"\s*(?:#|no\.?|num(?:ero)?\.?\s*)?\s*(\d{1,5}[a-z]?)\b", plano[fin:])
            if n:
                campos["numero_exterior"] = n.group(1).upper()
    if "numero_exterior" not in campos:
        n = re.search(r"(?:#|\bnumero\s+|\bnum\.?\s+|\bno\.\s*)(\d{1,5}[a-z]?)\b", plano)
        if n:
            campos["numero_exterior"] = n.group(1).upper()

    m = re.search(r"\b(?:int(?:erior)?\.?|depto\.?|dpto\.?|departamento)\s*#?\s*(\d{1,4}[a-z]?)\b", plano)
    if m:
        campos["numero_interior"] = m.group(1).upper()

    m = re.search(r"\b(?:col\.?|colonia)\s+", plano)
    if m:
        nombre, _ = _palabras_hasta_corte(original, plano, m.end())
        if nombre:
            campos["colonia"] = _titulo(nombre)
    else:
        # «vivo en Portales en 03300», «estoy en la Narvarte, cp 03020»
        m = re.search(r"\b(?:vivo|estoy|somos|vivimos)\s+en\s+(?:la\s+|el\s+|los\s+)?", plano)
        if m:
            nombre, fin = _palabras_hasta_corte(original, plano, m.end(), maximo=3)
            resto = plano[fin:]
            if nombre and re.match(r"\s*,?\s*(?:en\s+|cp\s*|c\.p\.?\s*|codigo postal\s*)?\d{5}\b", resto):
                campos["colonia"] = _titulo(nombre)

    m = re.search(r"\b(?:alcaldia|municipio|delegacion)\s+(?:de\s+|la\s+)?", plano)
    if m:
        nombre, _ = _palabras_hasta_corte(original, plano, m.end(), maximo=3)
        if nombre:
            campos["alcaldia_municipio"] = _titulo(nombre)

    m = re.search(r"\b(?:ref(?:erencia)?\.?:?|entre|esquina(?: con)?)\s+(.{3,90})", plano)
    if m:
        inicio = m.start(1)
        fragmento = original[inicio: inicio + 90]
        fragmento = re.split(r"[\n)]", fragmento)[0].strip(" .,;")
        etiqueta = plano[m.start(): m.start(1)].strip()
        campos["referencia"] = fragmento if etiqueta.startswith(("ref", "esquina")) else f"entre {fragmento}"
    return campos
