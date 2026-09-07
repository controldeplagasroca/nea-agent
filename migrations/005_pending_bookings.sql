-- 005_pending_bookings.sql — aprobación obligatoria del dueño antes de
-- confirmar una cita: book_session ya no reserva directo en Google Calendar,
-- crea una fila aquí y espera "sí <folio>" / "no <folio>" del dueño por
-- WhatsApp. Idempotente.

CREATE TABLE IF NOT EXISTS pending_bookings (
  id                 BIGSERIAL PRIMARY KEY,
  conversation_id    BIGINT NOT NULL REFERENCES bot_conversation(id) ON DELETE CASCADE,
  crm_conversation_id TEXT NOT NULL,
  service_key      TEXT NOT NULL,
  start_utc        TIMESTAMPTZ NOT NULL,
  end_utc          TIMESTAMPTZ NOT NULL,
  label            TEXT NOT NULL,
  direccion        TEXT NOT NULL,
  dia_confirmado   TEXT NOT NULL,
  estado           TEXT NOT NULL DEFAULT 'pendiente', -- pendiente|aprobado|rechazado
  reminders_sent   INT NOT NULL DEFAULT 0,
  next_reminder_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_pending_bookings_pendiente
  ON pending_bookings (next_reminder_at)
  WHERE estado = 'pendiente';
