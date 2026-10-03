-- 010_agenda_gcal_aprobaciones.sql — agenda propia contra Google Calendar y
-- aprobación del dueño ("sí <folio>" / "no <folio>"). Portado de la Nea
-- anterior (004-007 y 010 de allá). Idempotente: en una base que YA tiene
-- estas tablas (producción de ROCA) no cambia nada.

-- Una fila por cita activa; se conserva tras reagendar (mismo evento de
-- Google, se actualizan las fechas).
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

-- Solicitudes de cita por aprobar por el dueño.
CREATE TABLE IF NOT EXISTS pending_bookings (
  id                  BIGSERIAL PRIMARY KEY,
  conversation_id     BIGINT NOT NULL REFERENCES bot_conversation(id) ON DELETE CASCADE,
  crm_conversation_id TEXT NOT NULL,
  service_key         TEXT NOT NULL,
  start_utc           TIMESTAMPTZ NOT NULL,
  end_utc             TIMESTAMPTZ NOT NULL,
  label               TEXT NOT NULL,
  direccion           TEXT NOT NULL,
  dia_confirmado      TEXT NOT NULL,
  estado              TEXT NOT NULL DEFAULT 'pendiente', -- pendiente|aprobado|rechazado
  reminders_sent      INT NOT NULL DEFAULT 0,
  next_reminder_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at         TIMESTAMPTZ
);
ALTER TABLE pending_bookings ADD COLUMN IF NOT EXISTS costo_cotizado NUMERIC NOT NULL DEFAULT 0;
ALTER TABLE pending_bookings ADD COLUMN IF NOT EXISTS telefono_cliente TEXT NOT NULL DEFAULT '';
ALTER TABLE pending_bookings ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'nueva';
ALTER TABLE pending_bookings ADD COLUMN IF NOT EXISTS google_event_id TEXT;
ALTER TABLE pending_bookings ADD COLUMN IF NOT EXISTS avisado_al_dueno BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_pending_bookings_pendiente
  ON pending_bookings (next_reminder_at)
  WHERE estado = 'pendiente';
