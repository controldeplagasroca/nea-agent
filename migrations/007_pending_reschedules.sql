-- 007_pending_reschedules.sql — extiende el candado de aprobación del dueño
-- para que también cubra REAGENDAR una cita ya aprobada, no solo agendar una
-- nueva. reschedule_session ya no mueve el evento directo en Google Calendar
-- cuando OWNER_WA_ID está configurado -- crea una fila aquí igual que
-- book_session (mismo mecanismo de folio "sí <n>" / "no <n>"). Idempotente.

ALTER TABLE pending_bookings
  ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'nueva';
  -- 'nueva' (agendar por primera vez) | 'reagendar' (mover una cita ya
  -- aprobada a otro horario)

ALTER TABLE pending_bookings
  ADD COLUMN IF NOT EXISTS google_event_id TEXT;
  -- solo para kind='reagendar': el evento existente que hay que mover al
  -- aprobar. NULL para kind='nueva' (el evento todavía no existe).
