"""Relay: body crudo + firma intactos, reintento con backoff, abandono a las 24 h."""
from __future__ import annotations

import asyncio
from datetime import timedelta

import httpx

from app.relay import RelayWorker
from app.state import utcnow
from tests.conftest import CRM_WEBHOOK_URL


async def test_relay_reintenta_ante_500_y_entrega(ctx, respx_mock):
    route = respx_mock.post(CRM_WEBHOOK_URL).mock(
        side_effect=[httpx.Response(500), httpx.Response(200)]
    )
    body = b'{"payload": "crudo con bytes exactos"}'
    firma = "sha256=abc123"
    rid = await ctx.store.enqueue_relay(body, firma)

    worker = RelayWorker(ctx.store, CRM_WEBHOOK_URL, asyncio.Event())
    t0 = utcnow()
    await worker.process_due(now=t0)

    item = ctx.store.relays[rid]
    assert item.delivered_at is None
    assert item.attempts == 1
    assert item.next_retry_at > t0  # backoff programado

    # aún no toca reintentar
    await worker.process_due(now=t0 + timedelta(seconds=1))
    assert route.call_count == 1

    # pasado el backoff → entrega
    await worker.process_due(now=t0 + timedelta(seconds=10))
    assert route.call_count == 2
    assert ctx.store.relays[rid].delivered_at is not None

    # el CRM recibió los bytes EXACTOS y la firma original
    for call in route.calls:
        assert call.request.content == body
        assert call.request.headers["x-hub-signature-256"] == firma
    await worker.aclose()


async def test_relay_backoff_crece_exponencial(ctx, respx_mock):
    respx_mock.post(CRM_WEBHOOK_URL).mock(return_value=httpx.Response(503))
    rid = await ctx.store.enqueue_relay(b"{}", None)
    worker = RelayWorker(ctx.store, CRM_WEBHOOK_URL, asyncio.Event())

    t0 = utcnow()
    await worker.process_due(now=t0)
    delay1 = (ctx.store.relays[rid].next_retry_at - t0).total_seconds()
    t1 = t0 + timedelta(seconds=delay1 + 0.1)
    await worker.process_due(now=t1)
    delay2 = (ctx.store.relays[rid].next_retry_at - t1).total_seconds()
    assert delay2 > delay1  # exponencial
    await worker.aclose()


async def test_relay_abandona_tras_24h(ctx, respx_mock):
    route = respx_mock.post(CRM_WEBHOOK_URL).mock(return_value=httpx.Response(200))
    rid = await ctx.store.enqueue_relay(b"{}", None)
    ctx.store.relays[rid].created_at = utcnow() - timedelta(hours=25)

    worker = RelayWorker(ctx.store, CRM_WEBHOOK_URL, asyncio.Event())
    await worker.process_due()
    assert route.call_count == 0  # ya ni lo intenta
    assert ctx.store.relays[rid].abandoned_at is not None
    await worker.aclose()


async def test_relay_sin_firma_no_manda_header(ctx, respx_mock):
    route = respx_mock.post(CRM_WEBHOOK_URL).mock(return_value=httpx.Response(200))
    await ctx.store.enqueue_relay(b'{"x":1}', None)
    worker = RelayWorker(ctx.store, CRM_WEBHOOK_URL, asyncio.Event())
    await worker.process_due()
    assert "x-hub-signature-256" not in route.calls[0].request.headers
    await worker.aclose()
