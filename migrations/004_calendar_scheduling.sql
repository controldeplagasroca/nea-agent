-- 004_calendar_scheduling.sql — agenda real contra Google Calendar (motor de
-- agendamiento que vocero-crm deja fuera de alcance a propósito, ver su
-- README e issue #8 de kevinrivm/vocero-crm). Idempotente.

ALTER TABLE offered_slots
  ADD COLUMN IF NOT EXISTS service_key TEXT NOT NULL DEFAULT '';

-- Una fila por cita activa; se conserva tras reagendar (mismo evento de
-- Google, se actualizan las fechas) — así reschedule_session sabe qué mover
-- sin depender del CRM para rastrearlo.
CREATE TABLE IF NOT EXISTS calendar_bookings (
  id               BIGSERIAL PRIMARY KEY,
  conversation_id  BIGINT NOT NULL REFERENCES bot_conversation(id) ON DELETE CASCADE,
  google_event_id  TEXT NOT NULL,
  service_key      TEXT NOT NULL,
  start_utc        TIMESTAMPTZ NOT NULL,
  end_utc          TIMESTAMPTZ NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  canceled_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_calendar_bookings_active
  ON calendar_bookings (conversation_id)
  WHERE canceled_at IS NULL;
