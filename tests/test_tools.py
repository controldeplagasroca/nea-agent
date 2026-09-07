"""Tools: book_session SOLO acepta slots ofrecidos; slot_taken trae alternativas.

Las herramientas de agenda (propose_slots/book_session/reschedule_session)
hablan con app.gcal.GoogleCalendarClient — aquí se prueba la ORQUESTACIÓN
(tools.py) contra tests.conftest.FakeCalendar; la lógica real de
disponibilidad/duración/ventanas por servicio se prueba en tests/test_gcal.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.gcal import CalendarSlotTaken
from app.state import OfferedSlot
from app.tools import ToolRuntime
from tests.conftest import (
    CRM_CONV_ID,
    CRM_URL,
    IDENTITY,
    crm_context,
    make_ctx,
    make_settings,
)

SLOT_ISO = "2026-07-20T16:00:00Z"
SLOT_DT = datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc)
SLOT_END_DT = SLOT_DT + timedelta(minutes=90)  # duración de "alemana"
OWNER_ID = "525500000000"


@pytest.fixture
async def runtime_y_ctx():
    ctx = make_ctx()
    conv = await ctx.store.get_or_create_conversation(IDENTITY)
    await ctx.store.replace_offered_slots(
        conv.id,
        [
            OfferedSlot(
                conversation_id=conv.id,
                start_utc=SLOT_DT,
                end_utc=SLOT_END_DT,
                label="lunes 20 de julio, 10:00 am",
                service_key="alemana",
            )
        ],
    )
    runtime = ToolRuntime(ctx, conv, CRM_CONV_ID)
    yield runtime, ctx, conv
    await ctx.crm.aclose()


@pytest.fixture
async def runtime_con_dueno_ctx():
    """Mismo escenario que runtime_y_ctx, pero con OWNER_WA_ID configurado —
    book_session debe crear un pending_booking en vez de reservar directo."""
    ctx = make_ctx(settings=make_settings(owner_wa_id=OWNER_ID))
    conv = await ctx.store.get_or_create_conversation(IDENTITY)
    await ctx.store.replace_offered_slots(
        conv.id,
        [
            OfferedSlot(
                conversation_id=conv.id,
                start_utc=SLOT_DT,
                end_utc=SLOT_END_DT,
                label="lunes 20 de julio, 10:00 am",
                service_key="alemana",
            )
        ],
    )
    runtime = ToolRuntime(ctx, conv, CRM_CONV_ID)
    yield runtime, ctx, conv
    await ctx.crm.aclose()


DIRECCION_OK = "Calle Amores 123, depto 4B"


async def test_book_rechaza_slot_no_ofrecido(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "book_session",
        {"start_utc": "2026-07-20T17:00:00Z", "direccion_completa": DIRECCION_OK},
    )  # nunca ofrecido
    assert result["ok"] is False
    assert result["error"] == "slot_no_ofrecido"
    assert ctx.calendar.booking_calls == []  # jamás llegó a la agenda
    assert runtime.booked is False


async def test_book_acepta_slot_ofrecido_epoch_exacto(runtime_y_ctx, respx_mock):
    runtime, ctx, conv = runtime_y_ctx
    ficha_route = respx_mock.put(f"{CRM_URL}/api/bot/ficha").mock(
        return_value=httpx.Response(200, json={"ficha": {}, "stageMoved": True})
    )
    # mismo instante escrito con offset en vez de Z — el epoch es lo que cuenta
    result = await runtime.execute(
        "book_session",
        {
            "start_utc": "2026-07-20T16:00:00+00:00",
            "direccion_completa": DIRECCION_OK,
        },
    )
    assert result["ok"] is True
    assert runtime.booked is True
    call = ctx.calendar.booking_calls[0]
    assert call["start_utc"] == SLOT_DT
    assert call["end_utc"] == SLOT_END_DT
    assert call["service_key"] == "alemana"
    # al reservar se limpian los ofrecidos y queda la cita activa rastreada
    assert await ctx.store.get_offered_slots(conv.id) == []
    active = await ctx.store.get_active_calendar_booking(conv.id)
    assert active is not None
    assert active.google_event_id == "evt_1"
    assert active.start_utc == SLOT_DT
    # la dirección real queda guardada en la ficha del lead (campo geo)
    body = json.loads(ficha_route.calls[0].request.content)
    assert body["ficha"]["geo"] == DIRECCION_OK


async def test_book_slot_taken_ofrece_alternativas_frescas(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    frescos = [
        {"startUtc": "2026-07-21T16:00:00Z", "endUtc": None, "label": "martes 21, 10:00 am"},
        {"startUtc": "2026-07-21T17:00:00Z", "endUtc": None, "label": "martes 21, 11:00 am"},
    ]
    ctx.calendar.create_result = CalendarSlotTaken(frescos)
    result = await runtime.execute(
        "book_session", {"start_utc": SLOT_ISO, "direccion_completa": DIRECCION_OK}
    )
    assert result["ok"] is False
    assert result["error"] == "slot_taken"
    assert [s["label"] for s in result["slots"]] == [s["label"] for s in frescos]
    # los frescos quedan como los nuevos (y únicos) reservables
    offered = await ctx.store.get_offered_slots(conv.id)
    assert [s.label for s in offered] == [s["label"] for s in frescos]
    assert runtime.booked is False


async def test_book_rechaza_direccion_vacia(runtime_y_ctx):
    """Regresión (2026-09-07): en vivo, el bot agendó una cita real con SOLO
    colonia+alcaldía (dato usado para verificar cobertura) y JAMÁS pidió
    calle, número exterior/interior ni referencia de acceso -- la regla en
    prosa ("nunca agendes sin dirección completa") no bastó, mismo patrón
    que verificar_cobertura. book_session debe rechazarlo server-side."""
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "book_session", {"start_utc": SLOT_ISO, "direccion_completa": ""}
    )
    assert result["ok"] is False
    assert result["error"] == "direccion_incompleta"
    assert ctx.calendar.booking_calls == []
    assert runtime.booked is False


async def test_book_con_dueno_no_reserva_directo_crea_pendiente(
    runtime_con_dueno_ctx, respx_mock
):
    """Con OWNER_WA_ID configurado, book_session ya NO llama a Google
    Calendar directo -- crea un pending_booking y le avisa al dueño por
    WhatsApp (folio), y el lead recibe un mensaje de "voy a confirmar con el
    equipo", nunca una confirmación definitiva."""
    runtime, ctx, conv = runtime_con_dueno_ctx
    respx_mock.get(f"{CRM_URL}/api/bot/context", params={"waIdentity": OWNER_ID}).mock(
        return_value=httpx.Response(200, json=crm_context(conv_id="cv_owner"))
    )
    owner_msg_route = respx_mock.post(f"{CRM_URL}/api/bot/messages").mock(
        return_value=httpx.Response(200, json={"messageId": "msg_1"})
    )
    result = await runtime.execute(
        "book_session",
        {
            "start_utc": SLOT_ISO,
            "dia_confirmado": "lunes a las 10",
            "direccion_completa": DIRECCION_OK,
        },
    )
    assert result["ok"] is True
    assert result["pendiente_aprobacion"] is True
    assert ctx.calendar.booking_calls == []  # nunca tocó la agenda real
    assert runtime.booked is False

    pendientes = await ctx.store.list_pending_bookings_pendientes()
    assert len(pendientes) == 1
    assert pendientes[0].direccion == DIRECCION_OK
    assert pendientes[0].crm_conversation_id == CRM_CONV_ID

    body = json.loads(owner_msg_route.calls[0].request.content)
    assert body["conversationId"] == "cv_owner"
    assert f"#{pendientes[0].id}" in body["text"]

    # los slots ofrecidos se limpian igual (evita doble-reserva del mismo lead)
    assert await ctx.store.get_offered_slots(conv.id) == []


async def test_book_rechaza_direccion_reciclada_de_otro_domicilio(
    runtime_con_dueno_ctx, respx_mock
):
    """Regresión (2026-09-07): en vivo, el lead dio "Calle Amores 123" para
    un domicilio, luego mencionó un domicilio DISTINTO dando solo el código
    postal (nunca la calle) -- y book_session igual reutilizó "Calle Amores
    123", la dirección vieja de la cita anterior de esa misma conversación."""
    runtime, ctx, conv = runtime_con_dueno_ctx
    await ctx.store.create_pending_booking(
        conv.id, CRM_CONV_ID, "hormiga", SLOT_DT, SLOT_END_DT,
        "lunes 20 de julio, 10:00 am", DIRECCION_OK, "lunes a las 10", SLOT_DT,
    )
    # el lead NO volvió a escribir esa dirección en sus mensajes recientes
    result = await runtime.execute(
        "book_session",
        {
            "start_utc": SLOT_ISO,
            "dia_confirmado": "lunes a las 10",
            "direccion_completa": DIRECCION_OK,
        },
    )
    assert result["ok"] is False
    assert result["error"] == "direccion_repetida_sin_confirmar"
    assert ctx.calendar.booking_calls == []
    assert (await ctx.store.list_pending_bookings_pendientes())[0].direccion == DIRECCION_OK
    # no se creó una SEGUNDA pending_booking para el intento rechazado
    assert len(await ctx.store.list_pending_bookings_for_conversation(conv.id)) == 1


async def test_book_acepta_direccion_repetida_si_el_lead_la_reescribio(
    runtime_con_dueno_ctx, respx_mock
):
    """Si el lead SÍ volvió a escribir la misma dirección recientemente
    (ej. dos domicilios que casualmente comparten calle y número), no debe
    rechazarse -- el candado es contra la REUTILIZACIÓN silenciosa, no
    contra coincidencias reales confirmadas por el lead."""
    runtime, ctx, conv = runtime_con_dueno_ctx
    await ctx.store.create_pending_booking(
        conv.id, CRM_CONV_ID, "hormiga", SLOT_DT, SLOT_END_DT,
        "lunes 20 de julio, 10:00 am", DIRECCION_OK, "lunes a las 10", SLOT_DT,
    )
    await ctx.store.add_message(conv.id, "user", f"Sí, es en {DIRECCION_OK} otra vez")
    respx_mock.get(f"{CRM_URL}/api/bot/context", params={"waIdentity": OWNER_ID}).mock(
        return_value=httpx.Response(200, json=crm_context(conv_id="cv_owner"))
    )
    respx_mock.post(f"{CRM_URL}/api/bot/messages").mock(
        return_value=httpx.Response(200, json={"messageId": "msg_1"})
    )
    result = await runtime.execute(
        "book_session",
        {
            "start_utc": SLOT_ISO,
            "dia_confirmado": "lunes a las 10",
            "direccion_completa": DIRECCION_OK,
        },
    )
    assert result["ok"] is True
    assert result["pendiente_aprobacion"] is True


async def test_book_direccion_nueva_sin_coincidencia_no_se_rechaza(
    runtime_con_dueno_ctx, respx_mock
):
    """Una dirección previa en la conversación no bloquea una dirección
    NUEVA y distinta -- el candado solo activa cuando coinciden los números."""
    runtime, ctx, conv = runtime_con_dueno_ctx
    await ctx.store.create_pending_booking(
        conv.id, CRM_CONV_ID, "hormiga", SLOT_DT, SLOT_END_DT,
        "lunes 20 de julio, 10:00 am", DIRECCION_OK, "lunes a las 10", SLOT_DT,
    )
    respx_mock.get(f"{CRM_URL}/api/bot/context", params={"waIdentity": OWNER_ID}).mock(
        return_value=httpx.Response(200, json=crm_context(conv_id="cv_owner"))
    )
    respx_mock.post(f"{CRM_URL}/api/bot/messages").mock(
        return_value=httpx.Response(200, json={"messageId": "msg_1"})
    )
    result = await runtime.execute(
        "book_session",
        {
            "start_utc": SLOT_ISO,
            "dia_confirmado": "lunes a las 10",
            "direccion_completa": "Calle Reforma 789, colonia Nápoles",
        },
    )
    assert result["ok"] is True
    assert result["pendiente_aprobacion"] is True


async def test_book_rechaza_direccion_sin_numero(runtime_y_ctx):
    """Colonia+alcaldía sola (sin calle/número) no es una dirección real para
    que el técnico llegue -- debe seguir pidiéndose calle y número."""
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "book_session",
        {
            "start_utc": SLOT_ISO,
            "direccion_completa": "Colonia Nápoles, Benito Juárez",
        },
    )
    assert result["ok"] is False
    assert result["error"] == "direccion_incompleta"
    assert runtime.booked is False


async def test_propose_slots_pide_reparto_por_dia_y_persiste_todos(runtime_y_ctx):
    """El catálogo reservable es ancho a propósito: guardar solo 3 dejaba al
    agente sin nada que ofrecer cuando el lead pedía otro día. El "máximo 3"
    es cuántos SE ENSEÑAN, y eso lo gobierna el prompt."""
    runtime, ctx, conv = runtime_y_ctx
    seis = [
        {
            "startUtc": f"2026-07-2{d}T16:00:00Z",
            "endUtc": f"2026-07-2{d}T16:30:00Z",
            "label": f"día 2{d}, 10:00 am",
        }
        for d in range(6)
    ]
    ctx.calendar.availability_queue = [seis]
    result = await runtime.execute("propose_slots", {"servicio": "alemana"})
    assert result["ok"] is True
    assert len(result["slots"]) == 6
    assert len(await ctx.store.get_offered_slots(conv.id)) == 6
    assert runtime.proposed is True
    # El reparto se le pide a la agenda, no se improvisa aquí.
    call = ctx.calendar.availability_calls[0]
    assert call["service_key"] == "alemana"
    assert call["per_day"] == 3
    assert call["days"] == 5


async def test_propose_slots_servicio_no_reconocido(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute("propose_slots", {"servicio": "moscas"})
    assert result["ok"] is False
    assert result["error"] == "servicio_no_agendable"
    assert ctx.calendar.availability_calls == []


async def test_propose_slots_termita_no_se_agenda_sola(runtime_y_ctx):
    """Termita (madera seca) es 'bajo consulta' — nunca auto-agendada."""
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute("propose_slots", {"servicio": "termita de madera seca"})
    assert result["ok"] is False
    assert result["error"] == "servicio_no_agendable"
    assert ctx.calendar.availability_calls == []


async def test_update_ficha_manda_lo_que_haya(runtime_y_ctx, respx_mock):
    runtime, ctx, conv = runtime_y_ctx
    ficha_route = respx_mock.put(f"{CRM_URL}/api/bot/ficha").mock(
        return_value=httpx.Response(200, json={"ficha": {}, "stageMoved": False})
    )
    result = await runtime.execute(
        "update_ficha",
        {"rubro": "clínica dental", "rol": "el dueño mero mero", "campo_raro": "x"},
    )
    assert result["ok"] is True
    body = json.loads(ficha_route.calls[0].request.content)
    # drift tolerado: se manda tal cual, el CRM normaliza flojo
    assert body["ficha"]["rol"] == "el dueño mero mero"
    assert body["ficha"]["campo_raro"] == "x"


async def test_handoff_se_difiere_al_final_del_turno(runtime_y_ctx, respx_mock):
    runtime, ctx, conv = runtime_y_ctx
    handoff_route = respx_mock.post(f"{CRM_URL}/api/bot/handoff").mock(
        return_value=httpx.Response(200, json={})
    )
    result = await runtime.execute("handoff", {"reason": "pidió humano"})
    assert result["ok"] is True
    assert runtime.handoff_reason == "pidió humano"
    # la tool NO llama al CRM: turn.py lo hace después de la despedida
    assert handoff_route.call_count == 0


async def test_crm_caido_en_tool_no_tumba_el_turno(runtime_y_ctx, respx_mock):
    runtime, ctx, conv = runtime_y_ctx
    respx_mock.put(f"{CRM_URL}/api/bot/ficha").mock(
        return_value=httpx.Response(500)
    )
    result = await runtime.execute("update_ficha", {"rubro": "ferretería"})
    assert result["ok"] is False
    assert result["error"] == "crm_error"


async def test_propose_slots_etiqueta_con_el_dia_en_palabras(runtime_y_ctx):
    """La etiqueta corta ("vie 7 ago, 10:30") se presta a que el lead entienda
    otro día — basta un "10:30, de mañana" para agendar mal."""
    runtime, ctx, conv = runtime_y_ctx
    ctx.calendar.availability_queue = [
        [
            {
                "startUtc": "2026-08-07T16:30:00Z",
                "endUtc": "2026-08-07T17:00:00Z",
                "label": "vie 7 ago, 10:30",
                "dayLabel": "hoy viernes 7 de agosto",
                "time": "10:30",
            },
            {
                "startUtc": "2026-08-10T15:00:00Z",
                "endUtc": "2026-08-10T15:30:00Z",
                "label": "lun 10 ago, 09:00",
                "dayLabel": "lunes 10 de agosto",
                "time": "09:00",
            },
        ]
    ]
    result = await runtime.execute("propose_slots", {"servicio": "alemana"})
    assert [s["label"] for s in result["slots"]] == [
        "hoy viernes 7 de agosto, 10:30",
        "lunes 10 de agosto, 09:00",
    ]
    assert result["dias_con_agenda"] == [
        "hoy viernes 7 de agosto",
        "lunes 10 de agosto",
    ]


async def test_reschedule_mueve_la_cita_sin_handoff(runtime_y_ctx):
    """Antes esto era handoff obligado y el lead se quedaba sin nadie."""
    runtime, ctx, conv = runtime_y_ctx
    old_start = SLOT_DT - timedelta(days=7)
    old_end = old_start + timedelta(minutes=90)
    await ctx.store.save_calendar_booking(conv.id, "evt_old", "alemana", old_start, old_end)

    result = await runtime.execute(
        "reschedule_session",
        {"start_utc": SLOT_ISO, "dia_confirmado": "sí, el lunes 20"},
    )
    assert result["ok"] is True
    assert result["label"] == "lunes 20 de julio, 10:00 am"
    call = ctx.calendar.reschedule_calls[0]
    assert call["event_id"] == "evt_old"
    assert call["old_start"] == old_start
    assert call["new_start"] == SLOT_DT
    assert await ctx.store.get_offered_slots(conv.id) == []
    active = await ctx.store.get_active_calendar_booking(conv.id)
    assert active is not None
    assert active.start_utc == SLOT_DT


async def test_reschedule_rechaza_slot_no_ofrecido(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "reschedule_session",
        {"start_utc": "2026-07-20T17:00:00Z", "dia_confirmado": "el lunes"},
    )
    assert result["error"] == "slot_no_ofrecido"
    assert ctx.calendar.reschedule_calls == []


async def test_reschedule_sin_cita_manda_a_book(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    # sin cita activa previa sembrada — el estado por defecto del fixture
    result = await runtime.execute(
        "reschedule_session", {"start_utc": SLOT_ISO, "dia_confirmado": "el lunes"}
    )
    assert result["ok"] is False
    assert result["error"] == "sin_cita"
    assert ctx.calendar.reschedule_calls == []


async def test_cancel_borra_la_cita_y_no_es_handoff(runtime_y_ctx, respx_mock):
    """Antes esto era handoff obligado; ahora Nea cancela y solo deja aviso."""
    runtime, ctx, conv = runtime_y_ctx
    start = SLOT_DT - timedelta(days=7)
    end = start + timedelta(minutes=90)
    await ctx.store.save_calendar_booking(conv.id, "evt_old", "alemana", start, end)
    ficha_route = respx_mock.put(f"{CRM_URL}/api/bot/ficha").mock(
        return_value=httpx.Response(200, json={"ficha": {}, "stageMoved": False})
    )

    result = await runtime.execute("cancel_session", {})

    assert result["ok"] is True
    assert runtime.canceled is True
    assert runtime.handoff_reason is None  # cancelar NO dispara handoff
    assert ctx.calendar.cancel_calls == ["evt_old"]
    assert await ctx.store.get_active_calendar_booking(conv.id) is None
    body = json.loads(ficha_route.calls[0].request.content)
    assert body["ficha"]["resultado"] == "cancelo"


async def test_cancel_sin_cita_no_llega_a_la_agenda(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute("cancel_session", {})
    assert result["ok"] is False
    assert result["error"] == "sin_cita"
    assert ctx.calendar.cancel_calls == []


async def test_calcular_multiplicar_da_entero_limpio(runtime_y_ctx):
    """Certificación en vivo (2026-09-06): el LLM cotizó $2,200 (rango 101-250
    m²) para un depa de 5x10 -- nunca multiplicó, asumió el rango de más."""
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute("calcular", {"operacion": "multiplicar", "a": 5, "b": 10})
    assert result == {"ok": True, "resultado": 50}


async def test_calcular_sumar_y_restar(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    suma = await runtime.execute("calcular", {"operacion": "sumar", "a": 1500, "b": 200})
    assert suma == {"ok": True, "resultado": 1700}
    resta = await runtime.execute("calcular", {"operacion": "restar", "a": 10, "b": 3})
    assert resta == {"ok": True, "resultado": 7}


async def test_calcular_resultado_no_entero_se_conserva(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute("calcular", {"operacion": "multiplicar", "a": 2.5, "b": 3})
    assert result == {"ok": True, "resultado": 7.5}


async def test_calcular_operacion_no_reconocida(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute("calcular", {"operacion": "dividir", "a": 10, "b": 2})
    assert result["ok"] is False
    assert result["error"] == "operacion_no_reconocida"


async def test_identificar_plaga_alemana_por_cocina(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "identificar_plaga",
        {"tamano_color": "chiquita, cafecita", "ubicacion": "atrás del refri, en la cocina"},
    )
    assert result["ok"] is True
    assert result["especie"] == "alemana"


async def test_identificar_plaga_americana_por_drenaje(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "identificar_plaga",
        {"tamano_color": "grandota, cafe rojiza, hasta vuela", "ubicacion": "en la coladera del patio"},
    )
    assert result["ok"] is True
    assert result["especie"] == "americana"


async def test_identificar_plaga_sin_datos_no_concluyente(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "identificar_plaga", {"tamano_color": "no sé", "ubicacion": "no sé"}
    )
    assert result["ok"] is True
    assert result["especie"] == "no_concluyente"


async def test_identificar_plaga_ambigua_pide_mas_detalle(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    # una señal de cada especie: empate a propósito
    result = await runtime.execute(
        "identificar_plaga",
        {"tamano_color": "grande", "ubicacion": "cocina"},
    )
    assert result["ok"] is True
    assert result["especie"] == "ambigua"


async def test_identificar_plaga_solo_tamano_no_concluye(runtime_y_ctx):
    """Regresión: una sola palabra de tamaño/color (sin ubicación real) NO
    debe declarar la especie — se vio en vivo que "chiquita" solo bastaba
    para que el bot dijera "es cucaracha alemana" sin haber pedido dónde la
    vio, y luego se re-clasificaba en automático con cada palabra nueva."""
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "identificar_plaga",
        {"tamano_color": "chiquita, cafecita", "ubicacion": "no sé, no me fijé"},
    )
    assert result["ok"] is True
    assert result["especie"] != "alemana"
    assert result["especie"] != "americana"


async def test_identificar_plaga_solo_ubicacion_no_concluye(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "identificar_plaga",
        {"tamano_color": "no sé", "ubicacion": "cerca de la coladera"},
    )
    assert result["ok"] is True
    assert result["especie"] != "alemana"
    assert result["especie"] != "americana"


async def test_verificar_cobertura_colonia_sola_pide_mas_datos(runtime_y_ctx):
    """Regresión (2026-09-06): el lead dijo "Colonia Buenos Aires" (existe
    tanto en zona cubierta como pegada a Tepito) y el bot respondió "está en
    nuestra zona de cobertura" sin más -- dos veces seguidas en vivo, incluso
    con la regla escrita en prosa en el perfil del negocio."""
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "verificar_cobertura",
        {"colonia": "Buenos Aires", "alcaldia_municipio": "", "codigo_postal": ""},
    )
    assert result["ok"] is True
    assert result["cobertura"] == "requiere_mas_datos"


async def test_verificar_cobertura_con_codigo_postal_alcanza(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "verificar_cobertura",
        {"colonia": "Buenos Aires", "alcaldia_municipio": "", "codigo_postal": "06350"},
    )
    assert result["ok"] is True
    assert result["cobertura"] == "dentro_de_zona"


async def test_verificar_cobertura_con_alcaldia_clara_alcanza(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "verificar_cobertura",
        {"colonia": "Nápoles", "alcaldia_municipio": "Benito Juárez", "codigo_postal": ""},
    )
    assert result["ok"] is True
    assert result["cobertura"] == "dentro_de_zona"


async def test_verificar_cobertura_tepito_fuera_de_zona(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "verificar_cobertura",
        {"colonia": "Centro", "alcaldia_municipio": "Tepito", "codigo_postal": ""},
    )
    assert result["ok"] is True
    assert result["cobertura"] == "fuera_de_zona"


async def test_verificar_cobertura_ecatepec_fuera_de_zona(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "verificar_cobertura",
        {"colonia": "Buenos Aires", "alcaldia_municipio": "Ecatepec", "codigo_postal": ""},
    )
    assert result["ok"] is True
    assert result["cobertura"] == "fuera_de_zona"


async def test_verificar_cobertura_gustavo_a_madero_fuera_de_zona(runtime_y_ctx):
    runtime, ctx, conv = runtime_y_ctx
    result = await runtime.execute(
        "verificar_cobertura",
        {"colonia": "Centro", "alcaldia_municipio": "Gustavo A. Madero", "codigo_postal": ""},
    )
    assert result["ok"] is True
    assert result["cobertura"] == "fuera_de_zona"
