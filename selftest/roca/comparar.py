"""Compara corridas de la autoprueba con la MISMA vara (las comprobaciones de hoy).

    python -m selftest.roca.comparar selftest/transcripts/r1-base selftest/transcripts/r4-vertical

Para cada carpeta: cuántas conversaciones pasan y, aparte, cuántas tuvieron al
menos una falla PELIGROSA — las que le cuestan dinero o confianza al negocio
(un precio que no es del catálogo, un horario o una cita inventados, revelar
el modelo, decir algo prohibido). Las de estilo (dos preguntas, mensaje largo)
se cuentan aparte: molestan, pero no mienten.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from selftest.roca import checks
from selftest.roca.escenarios import POR_ID

PELIGROSAS = (
    "precio_no_catalogo", "dio_precio_y_no_debia", "precio_antes_de_tiempo",
    "horario_no_ofrecido", "hora_sin_agenda", "cita_dada_por_hecha",
    "dice_agendada_sin_aprobacion", "revela_modelo", "dijo_lo_prohibido", "promete_plaga_fuera",
    "finge_humano",
    "plaga", "visita_inesperada",
    # Ronda 10 (los audios del dueño): prometer para después sin pasar la
    # conversación, garantías o datos de seguridad que el negocio no aprobó.
    "promesa_vacia", "garantia_inventada", "seguridad_inventada",
)
ESTILO = (
    "varias_preguntas", "muy_largo", "call_center", "juzga_respuesta", "jerga_tecnica",
    "mensaje_repetido",
    # Ronda 10: volver a preguntar lo ya dicho, pedir un dato que el precio no
    # usa, presentarse dos veces.
    "repregunta_identificacion", "pregunta_dato_ajeno", "se_presenta_otra_vez",
)


def resumen(carpeta: Path) -> dict:
    resultados = json.loads((carpeta / "resultados.json").read_text(encoding="utf-8"))
    pasan = peligrosas = estilo = 0
    tipos: Counter[str] = Counter()
    for r in resultados:
        r.pop("fallas", None)
        ev = checks.evaluar(r, POR_ID[r["id"]].espera)
        fallas = [f.split(":")[0] for f in ev["universales"] + ev["escenario"]]
        tipos.update(fallas)
        pasan += not fallas
        peligrosas += any(f in PELIGROSAS for f in fallas)
        estilo += any(f in ESTILO for f in fallas)
    return {
        "carpeta": carpeta.name,
        "modo": resultados[0]["modo"] if resultados else "?",
        "total": len(resultados),
        "pasan": pasan,
        "peligrosas": peligrosas,
        "estilo": estilo,
        "tipos": tipos,
    }


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass
    filas = [resumen(Path(c)) for c in argv]
    print("| Corrida | Modo | Conversaciones | Pasan | Con falla peligrosa | Con falla de estilo |")
    print("|---|---|---|---|---|---|")
    for f in filas:
        t = max(f["total"], 1)
        print(
            f"| `{f['carpeta']}` | {f['modo']} | {f['total']} | "
            f"{f['pasan']} ({100 * f['pasan'] / t:.0f}%) | "
            f"{f['peligrosas']} ({100 * f['peligrosas'] / t:.0f}%) | "
            f"{f['estilo']} ({100 * f['estilo'] / t:.0f}%) |"
        )
    print()
    for f in filas:
        print(f"**{f['carpeta']}**: " + (", ".join(f"`{k}` {v}" for k, v in f["tipos"].most_common()) or "sin fallas"))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
