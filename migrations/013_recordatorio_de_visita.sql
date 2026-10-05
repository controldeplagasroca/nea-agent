-- 013_recordatorio_de_visita.sql — recordatorio al cliente por plantilla de Meta.
-- Idempotente. `recordatorio_enviado_at` se limpia al reagendar (la cita nueva
-- merece su propio recordatorio); `created_at` pasa a ser «cuándo se fijó el
-- horario vigente»: la regla «no recordar si se agendó con menos de 24 h» mira eso.
ALTER TABLE calendar_bookings ADD COLUMN IF NOT EXISTS recordatorio_enviado_at TIMESTAMPTZ;
