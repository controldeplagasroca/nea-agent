"""¿Se atiende esa zona? Respuesta determinista, nunca de memoria del modelo.

Tres resultados, los de la especificación (sección 7):
- `requiere_mas_datos`: el nombre de la colonia solo no basta → se pide el CP.
- `fuera_de_zona`: zona excluida o código postal que no se atiende.
- `dentro_de_zona`: se sigue con la conversación (a veces con día restringido).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from app.plagas import catalogo
from app.plagas.texto import normalizar

_CP = re.compile(r"(?<!\d)(\d{5})(?!\d)")


@dataclass
class Cobertura:
    estado: str  # dentro_de_zona | fuera_de_zona | requiere_mas_datos
    zona: str = ""
    cp: str = ""
    motivo: str = ""
    # Día de la semana (0 = lunes) al que se limita el servicio, y su nombre.
    dia_restringido: int | None = None
    dia_nombre: str = ""

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)


def extraer_cp(texto: str) -> str:
    m = _CP.search(texto or "")
    return m.group(1) if m else ""


def _en_rangos(cp: int, rangos: list[tuple[int, int]]) -> bool:
    return any(lo <= cp <= hi for lo, hi in rangos)


def _zona_por(lista: list[dict[str, Any]], texto: str, cp: int | None) -> dict[str, Any] | None:
    for zona in lista:
        if any(re.search(p, texto) for p in zona["patrones"]):
            return zona
        if cp is not None and _en_rangos(cp, zona["cps"]):
            return zona
    return None


def verificar(zona: str = "", codigo_postal: str = "") -> Cobertura:
    texto = normalizar(zona)
    cp_txt = extraer_cp(str(codigo_postal or "")) or extraer_cp(zona or "")
    cp = int(cp_txt) if cp_txt else None

    excluida = _zona_por(catalogo.ZONAS_EXCLUIDAS, texto, cp)
    if excluida is not None:
        return Cobertura(
            "fuera_de_zona", zona=zona.strip(), cp=cp_txt,
            motivo=f"{excluida['nombre']} es una zona donde por ahora no se da servicio",
        )

    restringida = _zona_por(catalogo.ZONAS_DIA_RESTRINGIDO, texto, cp)
    if restringida is not None:
        return Cobertura(
            "dentro_de_zona", zona=zona.strip() or restringida["nombre"], cp=cp_txt,
            motivo=f"{restringida['nombre']} se atiende SOLO en {restringida['dia_nombre']}",
            dia_restringido=restringida["dia"], dia_nombre=restringida["dia_nombre"],
        )

    if cp is None:
        return Cobertura(
            "requiere_mas_datos", zona=zona.strip(),
            motivo="hay colonias con el mismo nombre en distintas alcaldías: falta el código postal",
        )
    if _en_rangos(cp, catalogo.COBERTURA_CPS):
        return Cobertura("dentro_de_zona", zona=zona.strip(), cp=cp_txt)
    return Cobertura(
        "fuera_de_zona", zona=zona.strip(), cp=cp_txt,
        motivo=f"el código postal {cp_txt} queda fuera de la zona de servicio",
    )
