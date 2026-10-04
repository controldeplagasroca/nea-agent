-- 012_fase_sin_check_legacy.sql — quita la restricción de fases de la Nea anterior.
--
-- La Nea anterior de ROCA (su migración 009) dejó en `bot_conversation` un CHECK
-- que solo admite sus fases: cobertura, identificacion, empatia, procedimiento,
-- cotizacion, envio, aceptacion, agendamiento, recomendaciones, cerrada.
-- Esta Nea guarda otras: descubrimiento, agendando (y cerrada). Con ese CHECK
-- vivo en producción, TODO UPDATE que escribía `phase = 'agendando'` (al cotizar)
-- o `'descubrimiento'` (/reset) fallaba: el turno reventaba después de enviar,
-- la red de seguridad apagaba la IA de esa conversación y el expediente no se
-- guardaba. Idempotente: en una base nueva no hay nada que quitar.

ALTER TABLE bot_conversation
  DROP CONSTRAINT IF EXISTS bot_conversation_phase_valida;

-- La Nea anterior también cambió el valor por defecto a 'cobertura'.
ALTER TABLE bot_conversation
  ALTER COLUMN phase SET DEFAULT 'descubrimiento';

-- Las conversaciones que quedaron con fases de la Nea anterior vuelven a un valor
-- de esta (lo único que el código lee es si la fase es 'cerrada').
UPDATE bot_conversation SET phase = 'agendando'
 WHERE phase = 'agendamiento';
UPDATE bot_conversation SET phase = 'cerrada'
 WHERE phase = 'recomendaciones';
UPDATE bot_conversation SET phase = 'descubrimiento'
 WHERE phase IN ('cobertura', 'identificacion', 'empatia', 'procedimiento',
                 'cotizacion', 'envio', 'aceptacion');
