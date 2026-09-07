-- 006_costo_cotizado.sql — guarda el costo cotizado en pending_bookings para
-- trazabilidad interna y para poder incluirlo en la description del evento
-- de Calendar (que ROCA Ops lee de forma read-only, ver app/approvals.py).
-- Idempotente.

ALTER TABLE pending_bookings
  ADD COLUMN IF NOT EXISTS costo_cotizado NUMERIC NOT NULL DEFAULT 0;

-- Teléfono del lead, guardado aquí (no solo en bot_conversation) para poder
-- armar la description del evento de Calendar sin un segundo lookup.
ALTER TABLE pending_bookings
  ADD COLUMN IF NOT EXISTS telefono_cliente TEXT NOT NULL DEFAULT '';
