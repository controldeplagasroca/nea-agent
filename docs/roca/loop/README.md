# Evidencia del improvement loop

Lo que produjo cada ronda de la autoprueba (`python -m selftest.roca`), tal
como salió en su momento. Las cifras comparables entre rondas —todas
re-calificadas con las comprobaciones finales— están en [`../LOOP.md`](../LOOP.md).

| Archivo | Qué es |
|---|---|
| `r1-base-resumen.md` | Línea base: Nea genérica con la especificación del negocio como prompt (34 × 2) |
| `final-base-resumen.md` · `final-base-transcripts.md` | La misma línea base con los escenarios finales (34 × 3), con cada conversación completa |
| `r1-vertical-resumen.md` … `r5-vertical-resumen.md` | Las rondas del vertical de plagas |
| `final-vertical-resumen.md` · `final-vertical-transcripts.md` | La última corrida completa (`final4`, 34 × 3), con cada conversación |
| `final6-dirigida-resumen.md` · `final6-dirigida-transcripts.md` | La verificación de los arreglos de la ronda 9 (8 escenarios), re-calificada |
| `ronda10-audios-resumen.md` · `ronda10-audios-transcripts.md` | Ronda 10: los 3 escenarios que salieron de los audios del dueño (× 3), ya con los arreglos |
| `ronda10-completa-resumen.md` · `ronda10-completa-transcripts.md` | Ronda 10: los 37 escenarios con el código final (× 1), con cada conversación |

En los transcripts, `🔧` es una herramienta que llamó el modelo y `🔒` un
candado que se disparó antes de enviar (`reparado` = se arregló sin volver a
llamar al modelo). Las direcciones y nombres son inventados por el cliente
simulado.
