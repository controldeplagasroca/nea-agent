-- 009_caso.sql — el expediente del vertical de plagas.
-- Lo que el servidor ya sabe del lead en esta conversación (cobertura, plaga
-- confirmada, cotización, dirección, visita solicitada) y con lo que decide
-- qué paso toca en cada turno (app/plagas/caso.py). Vive aquí y no en el
-- historial porque el modelo no ve más que los últimos mensajes, y es
-- justo al perder de vista lo ya dicho cuando vuelve a preguntar o inventa.
-- Vacío ('{}') fuera de ese vertical. Idempotente.

ALTER TABLE bot_conversation
  ADD COLUMN IF NOT EXISTS caso JSONB NOT NULL DEFAULT '{}'::jsonb;
