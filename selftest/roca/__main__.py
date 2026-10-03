"""Autoprueba de comportamiento del vertical de plagas.

    python -m selftest.roca --env-file ../.env                 # todo, 1 vez
    python -m selftest.roca --env-file ../.env --reps 3        # 3 veces cada caso
    python -m selftest.roca --env-file ../.env --solo alemana_casa,hostil
    python -m selftest.roca --env-file ../.env --modo base     # Nea genérica + brief

Necesita `LLM_API_KEY`, `LLM_MODEL` y (para OpenRouter) `LLM_BASE_URL`, en el
entorno o en un `--env-file`. La llave nunca va por argumentos ni se imprime.
No toca WhatsApp, ni un CRM, ni una base: el CRM es de mentira y vive en memoria.

Sale con 0 si todos los casos pasan y con 1 si alguno falla. Deja los
transcripts y el resumen en `selftest/transcripts/<fecha>/`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from selftest.roca import checks
from selftest.roca.corredor import correr_todos
from selftest.roca.escenarios import ESCENARIOS, POR_ID

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
CLAVES = ("LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL")


def _leer_env(ruta: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        out[clave.strip()] = valor.strip().strip('"').strip("'")
    return out


def _config(env_files: list[str]) -> dict[str, Any]:
    valores = {k: os.environ.get(k, "") for k in CLAVES}
    for ruta in env_files:
        leido = _leer_env(Path(ruta))
        for k in CLAVES:
            if leido.get(k):
                valores[k] = leido[k]
    if not valores["LLM_API_KEY"]:
        sys.exit("Falta LLM_API_KEY (en el entorno o en --env-file).")
    return {
        "llm_api_key": valores["LLM_API_KEY"],
        "llm_model": valores["LLM_MODEL"] or "z-ai/glm-5.3-flash",
        "llm_base_url": valores["LLM_BASE_URL"],
    }


def _perfil(modo: str) -> dict[str, Any]:
    if modo == "base":
        brief = (AQUI / "brief_base.md").read_text(encoding="utf-8")
        return {"profile": {"name": "Nea", "instructions": brief}, "kb": None}
    # En el vertical el conocimiento del negocio vive en el catálogo; el
    # perfil del CRM solo pone el nombre (y lo que el dueño quiera añadir).
    return {"profile": {"name": "Nea"}, "kb": None}


def _transcript(res: dict[str, Any], fallas: dict[str, list[str]]) -> str:
    estado = "✅ PASA" if not any(fallas.values()) else "❌ FALLA"
    lineas = [f"### {res['id']} · rep {res['rep']} · {estado}", f"_{res['titulo']}_", ""]
    for f in fallas["escenario"]:
        lineas.append(f"- ❌ escenario: {f}")
    for f in fallas["universales"]:
        lineas.append(f"- ❌ universal: {f}")
    if any(fallas.values()):
        lineas.append("")
    for i, t in enumerate(res["turnos"], 1):
        for m in t["lead"]:
            lineas.append(f"**Lead {i}:** {m}")
        for h in t.get("herramientas", []):
            args = json.dumps(h["args"], ensure_ascii=False)
            lineas.append(f"> 🔧 `{h['herramienta']}` {args[:400]}")
        if t.get("candados"):
            lineas.append(f"> 🔒 candados: {', '.join(t['candados'])}")
        if t.get("bot"):
            cuerpo = t["bot"].replace("\n", "\n> ")
            lineas.append(f"**Nea {i}** _({t.get('paso')}, {t.get('segundos')} s)_:\n> {cuerpo}")
        else:
            lineas.append(f"**Nea {i}:** _(silencio)_")
        if t.get("error"):
            lineas.append(f"```\n{t['error']}\n```")
        lineas.append("")
    if res.get("handoffs"):
        lineas.append(f"Handoffs: {res['handoffs']}")
    if res.get("ficha"):
        lineas.append(f"Ficha en el CRM: `{json.dumps(res['ficha'], ensure_ascii=False)}`")
    lineas.append("\n---\n")
    return "\n".join(lineas)


def _resumen(resultados: list[dict[str, Any]], evaluados: list[dict[str, list[str]]], args: Any, cfg: dict[str, Any]) -> str:
    por_caso: dict[str, list[bool]] = {}
    tipos: Counter[str] = Counter()
    candados_vistos: Counter[str] = Counter()
    turnos = segundos = 0
    uso = Counter()
    for res, ev in zip(resultados, evaluados):
        por_caso.setdefault(res["id"], []).append(not any(ev.values()))
        for f in ev["universales"] + ev["escenario"]:
            tipos[f.split(":")[0]] += 1
        for t in res["turnos"]:
            turnos += 1
            segundos += t.get("segundos") or 0
            candados_vistos.update(t.get("candados") or [])
        for quien in ("nea", "lead"):
            for k, v in (res.get("uso", {}).get(quien) or {}).items():
                uso[f"{quien}.{k}"] += v
    total = len(resultados)
    pasan = sum(1 for ev in evaluados if not any(ev.values()))
    lineas = [
        f"# Autoprueba ROCA — modo `{args.modo}`",
        "",
        f"- Fecha: {datetime.now():%Y-%m-%d %H:%M}",
        f"- Modelo: `{cfg['llm_model']}`",
        f"- Conversaciones: {total} ({len(por_caso)} escenarios × {args.reps})",
        f"- **Pasan: {pasan}/{total} ({100 * pasan / max(total, 1):.0f}%)**",
        f"- Turnos: {turnos} · {segundos / max(turnos, 1):.1f} s por turno",
        f"- Tokens de Nea: {uso['nea.prompt']:,} de entrada ({uso['nea.cached']:,} en caché), "
        f"{uso['nea.completion']:,} de salida, {uso['nea.llamadas']:,} llamadas",
        "",
        "## Por escenario",
        "",
        "| Escenario | Pasa |",
        "|---|---|",
    ]
    for caso, oks in por_caso.items():
        marca = "✅" if all(oks) else "⚠️" if any(oks) else "❌"
        lineas.append(f"| {marca} `{caso}` — {POR_ID[caso].titulo} | {sum(oks)}/{len(oks)} |")
    lineas += ["", "## Fallas por tipo", ""]
    lineas += [f"- `{k}`: {v}" for k, v in tipos.most_common()] or ["- ninguna"]
    lineas += ["", "## Candados que se dispararon (antes de enviar)", ""]
    lineas += [f"- `{k}`: {v}" for k, v in candados_vistos.most_common()] or ["- ninguno"]
    return "\n".join(lineas) + "\n"


def _reevaluar(carpeta: Path, args: Any) -> int:
    """Las comprobaciones de HOY sobre conversaciones de ayer.

    Sirve cuando se corrige una comprobación (un falso positivo, una
    expectativa mal escrita): se re-califica la corrida sin pagar otra vez el
    modelo, y la comparación entre rondas queda con la misma vara.
    """
    resultados = json.loads((carpeta / "resultados.json").read_text(encoding="utf-8"))
    for r in resultados:
        r.pop("fallas", None)
    evaluados = [checks.evaluar(r, POR_ID[r["id"]].espera) for r in resultados]
    args.modo = resultados[0]["modo"] if resultados else args.modo
    args.reps = max((r["rep"] for r in resultados), default=1)
    cfg = {"llm_model": "(re-evaluación de " + carpeta.name + ")"}
    resumen = _resumen(resultados, evaluados, args, cfg)
    (carpeta / "resumen-reevaluado.md").write_text(resumen, encoding="utf-8")
    (carpeta / "transcripts-reevaluado.md").write_text(
        "\n".join(_transcript(r, e) for r, e in zip(resultados, evaluados)), encoding="utf-8"
    )
    print(resumen)
    return 0 if all(not any(e.values()) for e in evaluados) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env-file", action="append", default=[])
    ap.add_argument("--modo", choices=("vertical", "base"), default="vertical")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--solo", default="", help="ids separados por coma")
    ap.add_argument("--paralelo", type=int, default=8)
    ap.add_argument("--salida", default="")
    ap.add_argument("--verboso", action="store_true")
    ap.add_argument(
        "--reevaluar", default="",
        help="carpeta de una corrida anterior: vuelve a pasar las comprobaciones "
             "sobre sus conversaciones (sin llamar al modelo)",
    )
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO if args.verboso else logging.ERROR)
    for ruidoso in ("httpx", "openai", "httpcore"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

    if args.reevaluar:
        return _reevaluar(Path(args.reevaluar), args)

    cfg = _config(args.env_file)
    elegidos = ESCENARIOS
    if args.solo:
        ids = [s.strip() for s in args.solo.split(",") if s.strip()]
        desconocidos = [i for i in ids if i not in POR_ID]
        if desconocidos:
            sys.exit(f"Escenarios desconocidos: {desconocidos}")
        elegidos = [POR_ID[i] for i in ids]

    def avisar(res: dict[str, Any]) -> None:
        ev = checks.evaluar(res, POR_ID[res["id"]].espera)
        marca = "ok " if not any(ev.values()) else "FALLA"
        print(f"  {marca}  {res['id']} (rep {res['rep']}, {len(res['turnos'])} turnos)", flush=True)

    print(f"Autoprueba ROCA · modo {args.modo} · {len(elegidos)} escenarios × {args.reps} · {cfg['llm_model']}")
    resultados = asyncio.run(correr_todos(
        elegidos, modo=args.modo, cfg=cfg, reps=args.reps, paralelo=args.paralelo,
        perfil=_perfil(args.modo), avisar=avisar,
    ))
    resultados.sort(key=lambda r: (r["id"], r["rep"]))
    evaluados = [checks.evaluar(r, POR_ID[r["id"]].espera) for r in resultados]

    salida = Path(args.salida) if args.salida else (
        RAIZ / "selftest" / "transcripts" / f"{datetime.now():%Y%m%d-%H%M%S}-{args.modo}"
    )
    salida.mkdir(parents=True, exist_ok=True)
    resumen = _resumen(resultados, evaluados, args, cfg)
    (salida / "resumen.md").write_text(resumen, encoding="utf-8")
    (salida / "transcripts.md").write_text(
        "\n".join(_transcript(r, e) for r, e in zip(resultados, evaluados)), encoding="utf-8"
    )
    (salida / "resultados.json").write_text(
        json.dumps(
            [{**r, "fallas": e} for r, e in zip(resultados, evaluados)],
            ensure_ascii=False, indent=1, default=str,
        ),
        encoding="utf-8",
    )
    print()
    print(resumen)
    print(f"Transcripts: {salida}")
    return 0 if all(not any(e.values()) for e in evaluados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
