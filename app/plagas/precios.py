"""Cuánto cuesta. La ÚNICA fuente de una cifra en toda la conversación.

Reglas globales (especificación, sección 5): el precio va POR VISITA, exacto,
sin redondear, y las visitas de un tratamiento NUNCA se suman en un total.

Tres resultados:
- `falta`: falta una variable → trae la pregunta ya redactada.
- `ok`: hay precio → trae la línea literal que se le dice al lead.
- `requiere_dueno`: fuera de rango, requiere inspección, o la fórmula todavía
  no está en el catálogo → cotiza una persona, Nea no inventa.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.plagas import catalogo
from app.plagas.texto import normalizar


@dataclass
class Cotizacion:
    estado: str  # ok | falta | requiere_dueno
    plaga: str
    variables: dict[str, Any] = field(default_factory=dict)
    falta: str = ""
    pregunta: str = ""
    precio: int | None = None  # por visita
    linea_precio: str = ""
    extras: list[str] = field(default_factory=list)
    motivo: str = ""


def dinero(n: int) -> str:
    return f"${n:,} {catalogo.NEGOCIO['moneda']}"


def _numero(valor: Any) -> float | None:
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    m = re.search(r"\d+(?:\.\d+)?", str(valor).replace(",", ""))
    return float(m.group(0)) if m else None


def _inmueble(valor: Any) -> str | None:
    s = normalizar(str(valor or "")).replace("_", " ")
    if not s:
        return None
    if "depa" in s or "depto" in s or "apartamento" in s or "condominio" in s:
        return "departamento"
    if "edificio" in s:
        return "edificio"
    if any(
        k in s
        for k in ("local", "negocio", "restauran", "comerci", "oficina", "bodega",
                  "tienda", "cafeteria", "taqueria", "cocina industrial")
    ):
        return "local_comercial"
    if "casa" in s:
        return "casa"
    return None


def limpiar_variables(crudas: dict[str, Any] | None) -> dict[str, Any]:
    """Lo que mandó el modelo → variables normalizadas (lo ilegible se descarta)."""
    out: dict[str, Any] = {}
    crudas = crudas or {}
    if (tipo := _inmueble(crudas.get("tipo_inmueble"))) is not None:
        out["tipo_inmueble"] = tipo
    largo, ancho = _numero(crudas.get("largo")), _numero(crudas.get("ancho"))
    m2 = _numero(crudas.get("m2"))
    if m2 is None and largo and ancho:
        m2 = largo * ancho
    if m2 is not None and m2 > 0:
        out["m2"] = int(m2) if float(m2).is_integer() else round(m2, 1)
    for clave in (
        "refrigeradores", "registros", "sanitarios", "colchones", "sillones",
        "sillas_comedor",
    ):
        n = _numero(crudas.get(clave))
        if n is not None and n >= 0:
            out[clave] = int(n)
    return out


def _falta(plaga: str, variables: dict[str, Any], clave: str, pregunta: str = "") -> Cotizacion:
    return Cotizacion(
        "falta", plaga, variables, falta=clave,
        pregunta=pregunta or catalogo.VARIABLES[clave]["pregunta"],
    )


def _dueno(plaga: str, variables: dict[str, Any], motivo: str) -> Cotizacion:
    return Cotizacion("requiere_dueno", plaga, variables, motivo=motivo)


def _tramo(tramos: list[tuple[int, int, int]], m2: float) -> tuple[int, int, int] | None:
    return next((t for t in tramos if t[0] <= m2 <= t[1]), None)


def cotizar(plaga: str, variables: dict[str, Any] | None) -> Cotizacion:
    info = catalogo.PLAGAS.get(plaga) or {}
    regla = info.get("precio")
    v = limpiar_variables(variables)
    if info.get("siempre_dueno") or not regla:
        return _dueno(plaga, v, info.get("siempre_dueno") or "esa plaga no se cotiza por chat")
    tipo = regla["tipo"]

    if tipo == "inspeccion":
        return _dueno(plaga, v, "se presupuesta por pieza, tras una inspección técnica en sitio")

    if tipo == "por_inmueble":
        if "tipo_inmueble" not in v:
            return _falta(plaga, v, "tipo_inmueble")
        inmueble = v["tipo_inmueble"]
        if inmueble not in regla["inmuebles"]:
            return _dueno(
                plaga, v,
                f"para {catalogo.INMUEBLES[inmueble]} el precio lo define una inspección en sitio",
            )
        if inmueble == "local_comercial":
            if "refrigeradores" not in v:
                return _falta(plaga, v, "refrigeradores")
            if v["refrigeradores"] > regla["max_refrigeradores"]:
                return _dueno(
                    plaga, v,
                    f"con más de {regla['max_refrigeradores']} refrigeradores o "
                    "congeladores hace falta una inspección en sitio",
                )
        precio = regla["inmuebles"][inmueble]
        return Cotizacion(
            "ok", plaga, v, precio=precio,
            linea_precio=f"{dinero(precio)} por visita ({catalogo.INMUEBLES[inmueble]})",
        )

    if tipo == "por_inmueble_m2":
        if "tipo_inmueble" not in v:
            return _falta(plaga, v, "tipo_inmueble", "¿Es casa o departamento?")
        inmueble = v["tipo_inmueble"]
        if inmueble not in regla["tramos"]:
            return _dueno(
                plaga, v, f"para {catalogo.INMUEBLES[inmueble]} cotiza directamente el negocio"
            )
        if "m2" not in v:
            return _falta(plaga, v, "m2")
        tramo = _tramo(regla["tramos"][inmueble], v["m2"])
        if tramo is None:
            return _dueno(
                plaga, v, f"{v['m2']} m² queda fuera de los rangos que se cotizan por chat"
            )
        return Cotizacion(
            "ok", plaga, v, precio=tramo[2],
            linea_precio=(
                f"{dinero(tramo[2])} por visita "
                f"({catalogo.INMUEBLES[inmueble]} de {tramo[0]} a {tramo[1]} m²)"
            ),
        )

    if tipo == "por_m2":
        if "tipo_inmueble" in regla["variables"]:
            if "tipo_inmueble" not in v:
                return _falta(plaga, v, "tipo_inmueble", "¿Es casa o departamento?")
            validos = regla.get("inmuebles_validos")
            if validos and v["tipo_inmueble"] not in validos:
                return _dueno(
                    plaga, v,
                    f"para {catalogo.INMUEBLES[v['tipo_inmueble']]} cotiza directamente el negocio",
                )
        if "m2" not in v:
            return _falta(plaga, v, "m2")
        tramo = _tramo(regla["tramos"], v["m2"])
        if tramo is None:
            return _dueno(
                plaga, v, f"{v['m2']} m² queda fuera de los rangos que se cotizan por chat"
            )
        return Cotizacion(
            "ok", plaga, v, precio=tramo[2],
            linea_precio=f"{dinero(tramo[2])} por visita (de {tramo[0]} a {tramo[1]} m²)",
            extras=[regla["promo"]] if regla.get("promo") else [],
        )

    if tipo == "calculadora_sanitarios":
        for clave in regla["variables"]:
            if clave not in v:
                pregunta = (
                    "¿Es casa, departamento o edificio?" if clave == "tipo_inmueble" else ""
                )
                return _falta(plaga, v, clave, pregunta)
        inmueble = v["tipo_inmueble"]
        base = regla["base"].get(inmueble)
        if base is None:
            return _dueno(plaga, v, "el precio de este servicio lo confirma directamente el negocio")
        extra = max(0, v["sanitarios"] - regla["sanitarios_incluidos"])
        precio = base + extra * regla["extra_por_sanitario"]
        extras = []
        if extra:
            extras.append(
                f"Incluye {dinero(regla['extra_por_sanitario'])} por cada baño adicional "
                f"a los {regla['sanitarios_incluidos']} de la tarifa base "
                f"({extra} adicional{'es' if extra != 1 else ''}), en cada visita."
            )
        return Cotizacion(
            "ok", plaga, v, precio=precio,
            linea_precio=f"{dinero(precio)} por visita ({catalogo.INMUEBLES[inmueble]})",
            extras=extras,
        )

    if tipo == "calculadora_area":
        if "m2" not in v:
            return _falta(
                plaga, v, "m2",
                "¿Cuánto mide más o menos el área a proteger (largo y ancho, o los metros cuadrados)?",
            )
        if regla["precio_por_caja"] is None or regla["m_por_caja"] is None:
            return _dueno(plaga, v, "el precio de este servicio lo confirma directamente el negocio")
        # El número de cajas lo calcula el sistema: jamás se le pregunta al lead.
        cajas = max(1, -(-int(v["m2"]) // int(regla["m_por_caja"])))
        precio = cajas * regla["precio_por_caja"]
        return Cotizacion(
            "ok", plaga, v, precio=precio,
            linea_precio=f"{dinero(precio)} por visita ({v['m2']} m²)",
        )

    if tipo == "calculadora_muebles":
        for clave in regla["variables"]:
            if clave not in v:
                return _falta(plaga, v, clave)
        unitarios = (regla["por_colchon"], regla["por_sillon"], regla["por_silla"])
        if any(u is None for u in unitarios):
            return _dueno(plaga, v, "el precio de este servicio lo confirma directamente el negocio")
        precio = (
            (regla["base"] or 0)
            + v["colchones"] * regla["por_colchon"]
            + v["sillones"] * regla["por_sillon"]
            + v["sillas_comedor"] * regla["por_silla"]
        )
        return Cotizacion(
            "ok", plaga, v, precio=precio,
            linea_precio=(
                f"{dinero(precio)} por visita ({v['colchones']} colchones, "
                f"{v['sillones']} sillones, {v['sillas_comedor']} sillas)"
            ),
        )

    return _dueno(plaga, v, "esa plaga no se cotiza por chat")


PREGUNTA_DE_CIERRE = "¿Te gustaría que agendemos tu primera visita?"


def bloque_de_cierre(cot: Cotizacion) -> str:
    """El resumen de la cotización, armado con datos 100% del catálogo.

    Se construye aquí y no en el prompt: como instrucción, 0 de 5 bloques
    salieron bien etiquetados en las pruebas del negocio (sección 8.2).
    """
    info = catalogo.PLAGAS[cot.plaga]
    lineas = [
        "📋 *Resumen de tu cotización*",
        f"{info['emoji']} {info['nombre']}",
        f"🛠️ Tratamiento: {info['visitas']}",
        f"💵 {cot.linea_precio}",
    ]
    lineas += [f"🎁 {e}" if e.lower().startswith("promo") else f"➕ {e}" for e in cot.extras]
    lineas.append(f"🤝 {catalogo.NEGOCIO['pago']}")
    return "\n".join(lineas)
