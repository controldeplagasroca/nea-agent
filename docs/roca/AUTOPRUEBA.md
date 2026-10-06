# Autoprueba con el modelo real

Corre conversaciones completas contra el modelo de producción y revisa, de forma
determinista, lo que le llegó al cliente. No toca WhatsApp, ni el CRM, ni la base: el CRM
es de mentira y vive en memoria. Necesita `LLM_API_KEY`, `LLM_MODEL` y `LLM_BASE_URL`
(OpenRouter) en el entorno o en un archivo `.env`; la llave nunca va por argumentos.

```bash
python -m selftest.roca --env-file ../.env                      # todos los casos, 1 vez
python -m selftest.roca --env-file ../.env --reps 3             # 3 veces cada caso
python -m selftest.roca --env-file ../.env --solo chinches_todo_en_el_primer_mensaje
```

Deja los transcripts y el resumen en `selftest/transcripts/<fecha>/`. Sale con 1 si algo falla.

## Qué revisa de más (4 oct)

- `pregunta_repetida`: el bot hace una pregunta casi igual a una que ya hizo.
- `repregunta_dato_dicho`: pide la calle, la colonia, la alcaldía, el tipo de inmueble o
  los colchones y sillones que el cliente ya había escrito (hasta ese mismo turno).
- `dice_agendada_sin_aprobacion`, precios fuera del catálogo, más de una pregunta, largo.

## Casos de conversaciones reales

| id | Qué reproduce |
|---|---|
| `chinches_todo_en_el_primer_mensaje` | Ethel: dirección, muebles y plaga en el primer mensaje; no se le vuelve a pedir nada. |
| `chinches_contesta_donde_las_ve` | «en cama y cabecera», «ya las vi», «pican»: no se repite la pregunta. |
| `cucarachas_sin_pistas` | «tengo cucarachas» a secas: se presentan las dos especies. |
| `chinches` | Fórmula de precio del dueño (3 colchones = $1,750). |

Para sumar una conversación mala: agrega un `Escenario` en `selftest/roca/escenarios.py`
con los mensajes del cliente en `apertura` y lo que NO debe decir el bot en
`no_debe_decir`. Un chequeo nuevo va en `selftest/roca/checks.py` con su prueba en
`tests/test_autoprueba_y_lectura.py`.

## Lo que esta autoprueba no cubre

El calendario de Google, la aprobación del dueño, los reagendos y las cancelaciones usan
el CRM de mentira, no el calendario. Esos ciclos se prueban en
`tests/test_escenarios_sinteticos.py` y `tests/test_contrapropuesta.py`.
