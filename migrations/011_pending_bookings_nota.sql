-- 011_pending_bookings_nota.sql — texto libre que acompaña la solicitud al dueño
-- (p. ej. «Zona Toluca: confirma que haya técnico ese miércoles»). Va en la
-- fila para que el recordatorio reenvíe el mismo mensaje. Idempotente.
ALTER TABLE pending_bookings ADD COLUMN IF NOT EXISTS nota TEXT NOT NULL DEFAULT '';
