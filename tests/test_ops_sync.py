"""Integración ROCA OPS → Nea (POST /roca-ops/sync).

Contexto: `VOCERO_SYNC_URL` de OPS apuntaba a este endpoint, que no existía —
OPS recibía 404 en cada intento y la sincronización nunca ocurrió. Estas
pruebas fijan el contrato real que OPS ya manda.
"""
from __future__ import annotations

import json

import httpx
import pytest

from app.main import create_app
from tests.conftest import CRM_URL, make_ctx, make_settings, mock_crm_basics

SECRETO = "secreto-de-prueba"
PAYLOAD = {
    "clientId": "cli_123",
    "phone": "525512345678",
    "fullName": "Ana Pérez",
    "status": "activo",
    "nextTreatmentDate": "2026-10-15",
}


@pytest.fixture
async def app_con_secreto(respx_mock):
    ctx = make_ctx(settings=make_settings(roca_ops_sync_secret=SECRETO))
    app = create_app(ctx=ctx)
    yield app, ctx
    await ctx.crm.aclose()


@pytest.fixture
async def app_sin_secreto(respx_mock):
    ctx = make_ctx(settings=make_settings(roca_ops_sync_secret=""))
    app = create_app(ctx=ctx)
    yield app, ctx
    await ctx.crm.aclose()


async def _post(app, payload, headers=None):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        return await client.post("/roca-ops/sync", json=payload, headers=headers or {})


async def test_sync_escribe_la_ficha_del_lead(app_con_secreto, respx_mock):
    app, ctx = app_con_secreto
    routes = mock_crm_basics(respx_mock)

    resp = await _post(app, PAYLOAD, {"X-Vocero-Secret": SECRETO})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "sincronizado": True}
    assert routes["ficha"].call_count == 1
    body = json.loads(routes["ficha"].calls[0].request.content)
    # Se prefijan con ops_ para no pisar lo que el lead dijo por WhatsApp.
    assert body["ficha"]["ops_client_id"] == "cli_123"
    assert body["ficha"]["ops_estado"] == "activo"
    assert body["ficha"]["ops_proximo_tratamiento"] == "2026-10-15"


async def test_next_treatment_null_borra_el_recordatorio(app_con_secreto, respx_mock):
    """null es un valor, no una ausencia: significa 'ya no tiene tratamiento'."""
    app, ctx = app_con_secreto
    routes = mock_crm_basics(respx_mock)

    resp = await _post(
        app,
        {**PAYLOAD, "nextTreatmentDate": None},
        {"X-Vocero-Secret": SECRETO},
    )

    assert resp.status_code == 200
    body = json.loads(routes["ficha"].calls[0].request.content)
    assert body["ficha"]["ops_proximo_tratamiento"] is None


async def test_sync_sin_secreto_configurado_falla_cerrado(app_sin_secreto, respx_mock):
    """Escribe datos de clientes: sin secreto no se atiende a nadie."""
    app, ctx = app_sin_secreto
    mock_crm_basics(respx_mock)

    resp = await _post(app, PAYLOAD, {"X-Vocero-Secret": "lo-que-sea"})

    assert resp.status_code == 503


async def test_sync_con_secreto_incorrecto_da_401(app_con_secreto, respx_mock):
    app, ctx = app_con_secreto
    routes = mock_crm_basics(respx_mock)

    resp = await _post(app, PAYLOAD, {"X-Vocero-Secret": "equivocado"})

    assert resp.status_code == 401
    assert routes["ficha"].call_count == 0


async def test_sync_sin_header_da_401(app_con_secreto, respx_mock):
    app, ctx = app_con_secreto
    mock_crm_basics(respx_mock)

    resp = await _post(app, PAYLOAD)

    assert resp.status_code == 401


async def test_sync_sin_phone_da_400(app_con_secreto, respx_mock):
    app, ctx = app_con_secreto
    mock_crm_basics(respx_mock)

    resp = await _post(app, {"clientId": "cli_1"}, {"X-Vocero-Secret": SECRETO})

    assert resp.status_code == 400


async def test_sync_de_lead_sin_conversacion_no_es_error(app_con_secreto, respx_mock):
    """Un cliente de OPS que todavía no escribe por WhatsApp no es un fallo."""
    app, ctx = app_con_secreto
    respx_mock.get(f"{CRM_URL}/api/bot/context").mock(
        return_value=httpx.Response(404, json={})
    )

    resp = await _post(app, PAYLOAD, {"X-Vocero-Secret": SECRETO})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "sincronizado": False}


async def test_sync_normaliza_el_telefono_mexicano(app_con_secreto, respx_mock):
    """Meta reporta 521XXXXXXXXXX y 52XXXXXXXXXX para la misma persona."""
    app, ctx = app_con_secreto
    route = respx_mock.get(f"{CRM_URL}/api/bot/context").mock(
        return_value=httpx.Response(
            200, json={"conversation": {"id": "cv_1"}, "contact": {}, "lead": {}}
        )
    )
    respx_mock.put(f"{CRM_URL}/api/bot/ficha").mock(
        return_value=httpx.Response(200, json={})
    )

    resp = await _post(
        app, {**PAYLOAD, "phone": "5215512345678"}, {"X-Vocero-Secret": SECRETO}
    )

    assert resp.status_code == 200
    wa_identity = route.calls[0].request.url.params["waIdentity"]
    assert wa_identity == "525512345678"
