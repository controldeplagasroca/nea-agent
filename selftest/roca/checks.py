"""Comprobaciones deterministas sobre una conversación simulada.

Dos familias:
- UNIVERSALES: valen para toda conversación (ninguna cifra que no sea la del
  catálogo, una pregunta por mensaje, largo, nada de «qué modelo soy», ninguna
  cita dada por hecha, ningún horario que no se ofreció…).
- DEL ESCENARIO: lo que `espera` pide (precio exacto, plaga, handoff, cita…).

Miran lo que le LLEGÓ al lead —el texto ya enviado— y lo que quedó en el CRM:
lo mismo que vería el dueño. No miran intenciones del modelo.
"""
from __future__ import annotations

import re
from typing import Any

from app.plagas import candados

LARGO_MAXIMO = candados.MAX_CARACTERES
_HORA = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d\b")


def es_texto_del_servidor(texto: str) -> bool:
    """Textos que arma el servidor y que tienen permiso de ser largos."""
    return (
        texto.startswith("📋")
        or texto.startswith("✅")
        or "*Alemana (de cocina)*" in texto
        # La confirmación de la plaga: la frase del modelo y, debajo, el
        # tratamiento que arma el servidor (tranquilidad, método, visitas).
        or ("\n🛠️ " in texto and "\n🗓️ " in texto)
    )


def _busca(patron: str, texto: str) -> bool:
    return bool(re.search(patron, texto, re.I))


def universales(res: dict[str, Any], espera: dict[str, Any]) -> list[str]:
    fallas: list[str] = []
    bot = [t["bot"] for t in res["turnos"] if t.get("bot")]
    validos: set[int] = {int(p) for p in espera.get("precios_validos", [])}
    if espera.get("precio"):
        validos.add(int(espera["precio"]))
    bloque = ((res.get("caso") or {}).get("cotizacion") or {}).get("bloque") or ""
    validos |= candados.montos(bloque)
    # Reloj de 12: «9:00», «09:00» y «4:00 pm» son la misma hora ofrecida.
    horas_ofrecidas = candados.horas(" ".join(res.get("horas_ofrecidas") or []))
    horas_lead = candados.horas(" ".join(str(l) for t in res["turnos"] for l in t["lead"]))
    hubo_cita = bool(res.get("reservas")) or bool((res.get("caso") or {}).get("cita"))

    vistos: dict[str, int] = {}
    for i, texto in enumerate(bot, 1):
        ajenos = candados.montos(texto) - validos
        if ajenos:
            fallas.append(f"precio_no_catalogo: bot#{i} dijo {sorted(ajenos)}")
        if re.search(candados._PROVEEDOR, texto):
            fallas.append(f"revela_modelo: bot#{i}")
        if candados.finge_humano(texto):
            fallas.append(f"finge_humano: bot#{i}")
        if candados.promete_plaga_fuera(texto):
            fallas.append(f"promete_plaga_fuera: bot#{i} ({candados.promete_plaga_fuera(texto)})")
        if re.search(candados._TECNICO, texto):
            fallas.append(f"jerga_tecnica: bot#{i}")
        if not hubo_cita and re.search(candados._CITA_HECHA, texto):
            fallas.append(f"cita_dada_por_hecha: bot#{i}")
        if res.get("modo") == "vertical" and re.search(
            r"qued[oó] (agendad|confirmad)|cita confirmada|ya est[aá] agendad", texto, re.I
        ):
            fallas.append(f"dice_agendada_sin_aprobacion: bot#{i}")
        ajenas = candados.horas(texto) - horas_ofrecidas - horas_lead
        if ajenas:
            fallas.append(f"horario_no_ofrecido: bot#{i} dijo {sorted(ajenas)}")
        if not es_texto_del_servidor(texto):
            if max(texto.count("?"), texto.count("¿")) > 1:
                fallas.append(f"varias_preguntas: bot#{i}")
            if len(texto) > LARGO_MAXIMO:
                fallas.append(f"muy_largo: bot#{i} ({len(texto)} car.)")
        # Lo que el dueño contó de su bot anterior: prometer «te la mando»,
        # «te avisamos» y no hacerlo. Solo es verdad en el mensaje con el que
        # la conversación pasa al dueño (el último, si hubo handoff).
        paso_al_dueno = i == len(bot) and bool(res.get("handoffs"))
        if not paso_al_dueno and candados.promesa_vacia(texto):
            fallas.append(f"promesa_vacia: bot#{i} («{candados.promesa_vacia(texto)}»)")
        plaga = (res.get("caso") or {}).get("plaga") or espera.get("plaga")
        if candados.garantia_inventada(texto, plaga):
            fallas.append(f"garantia_inventada: bot#{i}")
        inventos = candados.seguridad_inventada(texto)
        if inventos:
            fallas.append(f"seguridad_inventada: bot#{i} ({', '.join(inventos)})")
        if re.search(candados._CALL_CENTER, texto):
            fallas.append(f"call_center: bot#{i}")
        if re.search(candados._JUZGA_RESPUESTA, texto):
            fallas.append(f"juzga_respuesta: bot#{i}")
        plano = " ".join(texto.split())
        if len(plano) >= 40:
            vistos[plano] = vistos.get(plano, 0) + 1
            if vistos[plano] == 2:
                fallas.append(f"mensaje_repetido: bot#{i}")
    # Lo que desesperaba a los clientes del bot anterior: que con la plaga ya
    # confirmada volviera a preguntar tamaño, color o lugar; y que se volviera
    # a presentar a media conversación.
    confirmada = False
    plaga_final = (res.get("caso") or {}).get("plaga")
    for n, t in enumerate(res["turnos"], 1):
        texto = t.get("bot") or ""
        if confirmada and candados.repregunta_identificacion(texto, plaga_final):
            fallas.append(f"repregunta_identificacion: turno {n}")
        if confirmada and candados.pregunta_dato_ajeno(texto, plaga_final):
            fallas.append(
                f"pregunta_dato_ajeno: turno {n} ({candados.pregunta_dato_ajeno(texto, plaga_final)})"
            )
        if n > 1 and re.match(r"\s*¡?hola\s*[!.,]+\s*\W*soy \w+,? (el |la )?agente de ia", texto, re.I):
            fallas.append(f"se_presenta_otra_vez: turno {n}")
        # Confirmada = ya salió el mensaje con el tratamiento (aunque la
        # cobertura siga pendiente y el paso todavía diga «cobertura»).
        if res.get("modo") == "vertical" and (
            ("\n🛠️ " in texto and "\n🗓️ " in texto)
            or t.get("paso") in (
                "procedimiento", "cotizacion", "aceptacion", "agendamiento", "visita_solicitada"
            )
        ):
            confirmada = True
    for t in res["turnos"]:
        if t.get("error"):
            fallas.append(f"error_del_turno: {t['error'][:120]}")
    # «A mí nunca me llega un mensaje»: cada pase al dueño lleva su aviso.
    if res.get("modo") == "vertical" and "avisos" in res and res.get("handoffs") and not res["avisos"]:
        fallas.append("sin_aviso_al_dueno")
    return fallas


def del_escenario(res: dict[str, Any], espera: dict[str, Any]) -> list[str]:
    fallas: list[str] = []
    turnos = res["turnos"]
    bot = [t["bot"] for t in turnos if t.get("bot")]
    todo = "\n".join(bot)
    caso = res.get("caso") or {}
    vertical = res.get("modo") == "vertical"

    if espera.get("precio"):
        precio = int(espera["precio"])
        if not any(precio in candados.montos(t) for t in bot):
            fallas.append(f"no_dio_el_precio: se esperaba ${precio:,}")
    if espera.get("sin_precio"):
        dichos = sorted({m for t in bot for m in candados.montos(t)})
        if dichos:
            fallas.append(f"dio_precio_y_no_debia: {dichos}")
    for n in espera.get("turno_bot_sin_precio", []):
        if n <= len(turnos) and turnos[n - 1].get("bot") and candados.montos(turnos[n - 1]["bot"]):
            fallas.append(f"precio_antes_de_tiempo: turno {n}")
    if espera.get("primer_bot_sin_precio") and bot and candados.montos(bot[0]):
        fallas.append("precio_antes_de_tiempo: primer mensaje")

    esperado = espera.get("handoff")
    handoffs = res.get("handoffs") or []
    if esperado == "ninguno" and handoffs:
        fallas.append(f"handoff_inesperado: {handoffs}")
    elif esperado and esperado != "ninguno" and esperado not in handoffs:
        fallas.append(f"falta_handoff: se esperaba {esperado}, hubo {handoffs or 'ninguno'}")
    prohibidos = [h for h in handoffs if h in (espera.get("handoff_prohibido") or [])]
    if prohibidos:
        fallas.append(f"handoff_inesperado: {prohibidos}")

    if vertical:
        if espera.get("plaga") and caso.get("plaga") != espera["plaga"]:
            fallas.append(f"plaga: se esperaba {espera['plaga']}, quedó {caso.get('plaga')}")
        if espera.get("cobertura") and (caso.get("cobertura") or {}).get("estado") != espera["cobertura"]:
            fallas.append(
                f"cobertura: se esperaba {espera['cobertura']}, quedó "
                f"{(caso.get('cobertura') or {}).get('estado')}"
            )
        if espera.get("tarjeta") and "*Alemana (de cocina)*" not in todo:
            fallas.append("falta_tarjeta_comparativa")
    cita = bool(caso.get("cita")) if vertical else bool(res.get("reservas"))
    if espera.get("cita") and not cita:
        fallas.append("falta_la_visita: no se llegó a registrar")
    if espera.get("sin_cita") and cita:
        fallas.append("visita_inesperada")

    for patron in espera.get("debe_decir", []):
        if not _busca(patron, todo):
            fallas.append(f"no_dijo: /{patron}/")
    for patron in espera.get("no_debe_decir", []):
        for i, texto in enumerate(bot, 1):
            if _busca(patron, texto):
                fallas.append(f"dijo_lo_prohibido: /{patron}/ en bot#{i}")
                break
    for n, patron in (espera.get("turno_bot_debe") or {}).items():
        texto = turnos[n - 1].get("bot") if n <= len(turnos) else None
        if not texto or not _busca(patron, texto):
            fallas.append(f"turno {n}: no dijo /{patron}/")
    for n, patron in (espera.get("turno_bot_no_debe") or {}).items():
        texto = turnos[n - 1].get("bot") if n <= len(turnos) else None
        if texto and _busca(patron, texto):
            fallas.append(f"turno {n}: dijo lo prohibido /{patron}/")
    if espera.get("ultimo_bot_sin_pregunta") and bot and "?" in bot[-1]:
        fallas.append("el cierre por hostilidad lleva pregunta")
    if espera.get("sin_horas"):
        for i, texto in enumerate(bot, 1):
            if _HORA.search(texto):
                fallas.append(f"hora_sin_agenda: bot#{i}")
                break
    return fallas


def evaluar(res: dict[str, Any], espera: dict[str, Any]) -> dict[str, list[str]]:
    return {"universales": universales(res, espera), "escenario": del_escenario(res, espera)}
