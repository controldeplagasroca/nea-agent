"""PgStore: las citas por aprobar y las citas de Calendar.

Las pruebas de Postgres real se omiten sin base; aun así el código de PgStore
tiene que *ejecutarse*. En producción (4 oct) `create_pending_booking` reventó con
`NameError: _pending_from_row`: las funciones que convierten la fila en la cita
nunca se habían definido, y ninguna prueba con MemoryStore lo podía ver."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from app.db import PgStore

AHORA = datetime(2026, 10, 5, 17, 0, tzinfo=timezone.utc)


def _fila_pendiente(**extra: Any) -> dict[str, Any]:
    fila: dict[str, Any] = dict(
        id=7, conversation_id=1, crm_conversation_id="cv_1", service_key="alemana",
        start_utc=AHORA, end_utc=AHORA, label="lunes 5, 11:00", direccion="Poniente 81",
        dia_confirmado="lunes", costo_cotizado="1100", telefono_cliente="525523083093",
        kind="nueva", google_event_id=None, nota="", estado="pendiente",
        reminders_sent=0, avisado_al_dueno=False, next_reminder_at=AHORA,
        created_at=AHORA, resolved_at=None,
    )
    fila.update(extra)
    return fila


class _PoolFalso:
    """Lo mínimo de asyncpg.Pool: devuelve filas (diccionarios) y anota las consultas."""

    def __init__(self, fila: dict[str, Any] | None) -> None:
        self.fila, self.consultas = fila, []

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        self.consultas.append((sql, args))
        return self.fila

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        self.consultas.append((sql, args))
        return [self.fila] if self.fila else []

    async def execute(self, sql: str, *args: Any) -> str:
        self.consultas.append((sql, args))
        return "OK"


def _store(fila: dict[str, Any] | None) -> tuple[PgStore, _PoolFalso]:
    store = PgStore("postgres://x")
    pool = _PoolFalso(fila)
    store._pool = pool  # type: ignore[assignment]
    return store, pool


async def test_crear_una_cita_por_aprobar_devuelve_la_cita_y_guarda_la_nota():
    store, pool = _store(_fila_pendiente(nota="⚠️ Zona Toluca"))
    p = await store.create_pending_booking(
        1, "cv_1", "alemana", AHORA, AHORA, "lunes 5, 11:00", "Poniente 81", "lunes",
        AHORA, costo_cotizado=1100.0, telefono_cliente="525523083093", nota="⚠️ Zona Toluca",
    )
    assert p.id == 7 and p.costo_cotizado == 1100.0 and p.nota == "⚠️ Zona Toluca"
    assert pool.consultas[0][1][-1] == "⚠️ Zona Toluca"  # la nota viaja al INSERT


async def test_leer_listar_y_resolver_citas_por_aprobar():
    store, pool = _store(_fila_pendiente())
    assert (await store.get_pending_booking(7)).estado == "pendiente"
    assert [p.id for p in await store.list_pending_bookings_pendientes()] == [7]
    assert [p.id for p in await store.list_pending_bookings_for_conversation(1)] == [7]
    assert [p.id for p in await store.due_booking_reminders(AHORA)] == [7]
    await store.resolve_pending_booking(7, "aprobado")
    await store.mark_pending_avisado(7)
    assert any("UPDATE pending_bookings" in c[0] for c in pool.consultas)


async def test_sin_fila_get_devuelve_none():
    store, _ = _store(None)
    assert await store.get_pending_booking(99) is None
    assert await store.get_active_calendar_booking(1) is None


async def test_citas_de_calendar_se_guardan_y_se_leen():
    fila = dict(id=3, conversation_id=1, google_event_id="evt_1", service_key="alemana",
                start_utc=AHORA, end_utc=AHORA, created_at=AHORA)
    store, _ = _store(fila)
    b = await store.save_calendar_booking(1, "evt_1", "alemana", AHORA, AHORA)
    assert b.google_event_id == "evt_1"
    assert (await store.get_active_calendar_booking(1)).id == 3


def test_ningun_nombre_sin_definir_en_el_codigo():
    """pyflakes: un nombre sin definir solo revienta cuando ese camino corre."""
    pyflakes_api = pytest.importorskip("pyflakes.api")
    from pyflakes.reporter import Reporter
    import io

    salida = io.StringIO()
    reporter = Reporter(salida, salida)
    for ruta in sorted((Path(__file__).resolve().parent.parent / "app").rglob("*.py")):
        pyflakes_api.check(ruta.read_text(encoding="utf-8"), str(ruta), reporter)
    sin_definir = [l for l in salida.getvalue().splitlines() if "undefined name" in l]
    assert sin_definir == []
