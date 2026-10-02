# Cómo se comporta esta Nea — y dónde vive cada regla

Mapa de la «Especificación de comportamiento» de Control de Plagas ROCA contra
este código. La idea que lo ordena todo es la misma que el negocio aprendió a
golpes (sección 15 de su documento):

> **El modelo pone la voz. El servidor pone los hechos y el orden.**

Una regla que solo vive en el prompt se cumple «casi siempre», y el «casi» es
un precio mal dicho o una cita inventada. Por eso aquí cada regla que cuesta
dinero o confianza está en **código**; el prompt se queda con el tono.

## Las tres capas

```
                    mensaje del lead
                           │
        ┌──────────────────▼───────────────────┐
   1.   │  EXPEDIENTE + PASO ACTUAL            │  app/plagas/caso.py
        │  El servidor sabe qué se sabe ya y   │
        │  le dice al modelo qué toca y qué    │
        │  está PROHIBIDO en este turno.       │
        └──────────────────┬───────────────────┘
                           │  el modelo redacta y llama herramientas
        ┌──────────────────▼───────────────────┐
   2.   │  HERRAMIENTAS CON COMPUERTAS         │  app/plagas/herramientas.py
        │  cobertura · diagnóstico · precio ·  │  + cobertura.py, diagnostico.py,
        │  agenda. Fuera de orden = error que  │    precios.py, catalogo.py
        │  dice qué va primero. Los textos que │
        │  no pueden variar los arma el        │
        │  servidor («texto garantizado»).     │
        └──────────────────┬───────────────────┘
                           │  texto final del modelo
        ┌──────────────────▼───────────────────┐
   3.   │  CANDADOS                            │  app/plagas/candados.py
        │  Se revisa el texto ANTES de enviar. │  app/plagas/turno.py
        │  Falta → una corrección. Falta grave │
        │  que persiste → texto de respaldo.   │
        └──────────────────┬───────────────────┘
                           ▼
                  WhatsApp (vía el CRM)
```

## Sección por sección

Leyenda: 🔒 código (determinista) · 💬 prompt · 🔒+💬 las dos.

### 2. Flujo de servicio — las 9 fases

| Regla | Dónde | Cómo |
|---|---|---|
| El orden cobertura → identificación → empatía → procedimiento → cotización → envío → aceptación → agenda | 🔒 | `paso_actual()` calcula el paso con el expediente y lo pone al final del prompt, con su «PROHIBIDO en este paso». |
| No se salta una fase hacia adelante; el intento devuelve un error accionable | 🔒 | `cotizar` rechaza sin cobertura (`falta_cobertura`), sin plaga (`falta_identificar`) o en el mismo turno de la confirmación (`primero_el_tratamiento`). `propose_slots` rechaza sin cotización o en el turno del precio. `book_session` rechaza sin aceptación o sin dirección. |
| Cobertura e identificación no se restringen por fase | 🔒 | Esas dos herramientas se pueden llamar siempre. |

### Herramientas obligatorias por paso

En identificación, en cobertura cuando trae código postal, en cotización
cuando pide precio y en aceptación cuando dice que sí, el primer llamado al
modelo va con `tool_choice="required"` y un aviso de sistema que nombra la
herramienta (`app/plagas/turno.py`, `herramienta_obligada`). Por qué así y no
con el nombre: [LOOP.md, ronda 8](LOOP.md#ronda-8--el-forzado-que-no-forzaba).

### 3. Identidad, voz y estilo

| Regla | Dónde | Cómo |
|---|---|---|
| Es IA y lo dice; jamás revela modelo ni proveedor | 🔒+💬 | Prompt (BLINDAJE) + candado `revela_modelo` (grave) que busca nombres de modelos y proveedores en el texto. Candado `finge_humano` contra «vivo cerca», «mi casa», «yo también tuve». |
| Jamás enumera herramientas ni usa jerga interna | 🔒+💬 | Candado `jerga_tecnica`. |
| Una pregunta por mensaje; 3–4 líneas | 🔒+💬 | Candados `varias_preguntas` y `muy_largo` (piden una corrección). |
| Sin fórmulas de call center; «es que», «echado»; no decirle que su respuesta «es ambigua» | 🔒+💬 | Candados `call_center`, `ortografia`, `juzga_respuesta`. |
| Emojis con libertad, tono de tú | 💬 | Prompt. |
| No repetir un mensaje ya enviado | 🔒 | Viene del Nea raíz (`_respuesta_invalida` en `app/turn.py`). |
| «Lee antes de preguntar» | 🔒+💬 | El expediente lista lo que ya dio el lead; el paso de cotización dice **cuál** dato falta (lo calcula el catálogo, no el modelo). |
| Ráfagas: contestar todos los puntos | 💬 | Prompt. El coalesce de ráfagas es del Nea raíz. |

### 4. Identificación de plagas

| Regla | Dónde | Cómo |
|---|---|---|
| Mínimo dos señales distintas de la misma plaga | 🔒 | `diagnostico.evaluar()`. La plaga la confirma la herramienta, no el modelo. |
| Solo cuentan señales que el lead **escribió** | 🔒 | Cada señal viaja con su cita, y la cita tiene que (1) estar en los mensajes del lead y (2) **decir eso**: llevar una palabra típica de la señal («chiquitas», «cocina», «coladera»…), o ser un «sí» a una pregunta de Nea sobre esa señal. Si no, se rechaza. Sin el punto 2, «pues normales, no sé» pasaba como «son chiquitas». |
| Cucarachas: tamaño/color **y** ubicación, de la misma especie; el baño no distingue | 🔒 | `_cucaracha()`. Rasgos de las dos especies no confirman ninguna. |
| No mezclar rasgos de las dos especies al confirmar | 🔒+💬 | El resultado de la herramienta solo trae el tratamiento de la especie confirmada. |
| Tarjeta comparativa garantizada si no cierra | 🔒 | Primer atasco → la tarjeta sale como texto garantizado (reemplaza lo que escribió el modelo). |
| Después de la tarjeta, foto; no repetir en bucle | 🔒 | Segundo atasco → oferta de foto. Tercero → pasa al dueño. |
| Elegir en la tarjeta | 🔒 | Solo cuenta en el turno siguiente a la tarjeta y citando ESE mensaje. Vale por dos señales (la tarjeta describe tamaño, color y lugar juntos), salvo que lo ya dicho apunte a la otra especie. |
| Datos de precio no se preguntan al identificar | 💬 | «PROHIBIDO en este paso» del expediente. |
| Plaga fuera de catálogo: honestidad y handoff | 🔒 | Si el lead nombra una (garrapatas, avispas, piojos…) y ninguna del catálogo, el servidor contesta y pasa al dueño **sin llamar al modelo**. Si aparece más tarde, `plaga="otra"` hace lo mismo. Candado `promete_plaga_fuera` contra «sí atendemos X». |
| Identificar no es luz verde para cotizar | 🔒 | `cotizar` rechaza en el turno de la confirmación. |
| Araña violinista / viuda negra: precaución sin alarmar | 💬 | La línea de precaución viaja en el expediente. |

### 5 y 6. Precios y tratamientos

| Regla | Dónde | Cómo |
|---|---|---|
| El precio **siempre** sale de `cotizar()` | 🔒 | `precios.cotizar()` + candado `precio_no_cotizado` (grave): cualquier cifra en pesos que no esté en la cotización de esta conversación no sale. |
| Por visita, exacto, sin sumar visitas | 🔒 | La línea de precio es literal del catálogo; un total distinto lo frena el mismo candado. |
| Qué variables pide cada plaga | 🔒 | `catalogo.PLAGAS[…]["precio"]["variables"]`; `cotizar` devuelve la pregunta ya redactada, una a la vez. |
| Fuera de rango, >4 refrigeradores, inspección | 🔒 | `requiere_dueno` → texto garantizado + handoff, con los datos en la ficha. |
| Colchones **totales** de toda la casa | 🔒 | La pregunta está escrita en el catálogo. |
| Roedores: jamás preguntar cuántas cajas | 🔒+💬 | La herramienta no tiene ese parámetro; el número lo calcula el servidor. |
| Tratamiento, visitas e intervalos | 🔒 | Vienen en el resultado de `identificar_plaga` y en el expediente; el prompt no trae ninguno. |
| Contención (sin aerosol…) como advertencia obligatoria | 🔒 | Va en el texto garantizado de la solicitud de visita. |
| IVA solo si pide factura | 💬 | Prompt, con la frase del catálogo. |

### 7. Cobertura

| Regla | Dónde | Cómo |
|---|---|---|
| Nunca de memoria | 🔒 | `cobertura.verificar()`. |
| Zonas excluidas, incluso por código postal | 🔒 | `ZONAS_EXCLUIDAS`. «GAM» solo cuenta como palabra suelta. |
| Lerma y Toluca solo en miércoles | 🔒 | Queda en el expediente y `propose_slots` **solo** consulta miércoles. |
| La colonia sola no basta: pedir CP | 🔒 | `requiere_mas_datos`. |

### 8. Cierre y comunicación del precio

| Regla | Dónde | Cómo |
|---|---|---|
| Bloque de cierre bien etiquetado | 🔒 | `bloque_de_cierre()`: lo arma el servidor en el turno en que `cotizar` tiene éxito. |
| Precio antes de tiempo: ni se ignora ni se suelta | 🔒+💬 | Prompt + candado de precio. Si ya toca cotizar y lo pide, `cotizar` es obligatoria; si el modelo no la llama, la corre el servidor y pregunta el dato que falta. |
| Re-cierre sin volver a cotizar (pendiente del negocio) | 🔒 | Resuelto: la cotización queda en el expediente y el modelo la repite tal cual; el candado deja pasar esa cifra y solo esa. |
| El bloque sin pregunta de seguimiento (pendiente del negocio) | 🔒 | Resuelto: el servidor le añade «¿Te gustaría que agendemos tu primera visita?». |

### 9. Agendamiento

| Regla | Dónde | Cómo |
|---|---|---|
| Horarios reales, máximo 3 | 🔒+💬 | `propose_slots` contra la agenda del CRM; candado `horario_inventado` (grave). |
| Solo se reserva lo ofrecido | 🔒 | Del Nea raíz (`_resolve_offered`). |
| Dirección completa por escrito | 🔒 | `book_session` devuelve qué campo falta. Un dato que el lead no escribió no cuenta. |
| Pendiente de aprobación del dueño | 🔒 | `_solicitar_visita()`: no toca el calendario; ficha + handoff. Candado `cita_inventada` (grave). |

### 10. Cliente recurrente

| Regla | Dónde | Cómo |
|---|---|---|
| Detectarlo | 🔒+💬 | `parece_recurrente()` con las frases fuertes; etapa «Cliente» del CRM; cita ya agendada. Las frases débiles («programar», «confirmar») las decide el modelo. |
| No recalificar ni recotizar | 🔒 | Paso `cliente_recurrente`; `identificar_plaga` y `cotizar` se niegan. |
| Handoff con motivo `cliente` | 💬 | Prompt + paso. |

### 11. Ficha del CRM

🔒 La escribe el servidor desde las herramientas: `geo`, `plaga`,
`tipo_inmueble`, `cotizacion`, `datos_cotizacion`, `direccion`,
`cita_solicitada`, `calificado`, `resultado`, `notas`. El modelo no tiene
herramienta para escribirla.

### 12 y 13. Handoff, hostilidad y blindaje

| Regla | Dónde | Cómo |
|---|---|---|
| Catálogo cerrado de 5 motivos | 🔒 | Del Nea raíz (`canonical_handoff_reason`); la herramienta solo ofrece `cliente`, `modelo`, `hostilidad`. |
| Tercer mensaje hostil seguido | 🔒 | Del Nea raíz (`app/hostility.py`). |
| Segunda sonda de «qué modelo eres» → handoff | 🔒 | `es_sonda()` cuenta en el expediente; a la segunda el handoff sucede aunque el modelo no lo llame. |
| No adoptar formatos impuestos, no salirse del tema | 💬 | Prompt. |

### 14. Multimedia

Del Nea raíz (`app/media.py`), más dos reglas en el prompt: la foto sirve para
identificar (cita `"foto"`) y el pin no sustituye la dirección escrita.

### Lo que añadieron los audios del dueño (1 de octubre)

En dos audios el dueño contó cómo fallaba su bot anterior. Cada queja quedó
como regla con su prueba (`tests/test_plagas_audios.py`) y su escenario.

| Lo que contó | Dónde | Cómo quedó |
|---|---|---|
| «No lleva de la mano: pregunta color y tamaño muy preciso» | 🔒 | Las preguntas las pone el catálogo y ya traen las dos opciones («¿chiquitas (1 a 2 cm, café claro) o grandes…?»). Con «chiquitas» + «cocina» confirma: son dos preguntas como máximo. Vocabulario del dueño añadido a las señales (voladoras, patinadoras, licuadora, la calle). |
| «Ya dijo cocina, y vuelve a preguntar por el baño / el color / dónde» | 🔒 | El baño no distingue especie y no se repregunta si ya hay cocina o drenaje. Candado `repregunta_identificacion` (grave): con la plaga confirmada, ninguna pregunta de tamaño, color o lugar. `verificar_cobertura` sobre una zona ya verificada contesta «ya estaba» en vez de reiniciar la conversación. `cotizar` toma el tipo de inmueble y los metros que el lead ya escribió aunque el modelo no los mande. |
| «No explica: yo le digo que no se preocupe, que no es por falta de higiene, que son dos visitas» | 🔒 | Al confirmar cucaracha alemana, el bloque del servidor abre con la línea de tranquilidad (`tranquilidad` en el catálogo) y sigue con el tratamiento y las visitas. |
| «Que sepa contestar: ¿es tóxico?, ¿daña la salud?, ¿sí funciona?; el reingreso es a los 15–20 minutos» | 🔒+💬 | `catalogo.DUDAS` viaja en el prompt como lo único aprobado. Candado `seguridad_inventada` (grave): otro tiempo de reingreso, «no es tóxico», «orgánico», «no huele», «seguro para mascotas», «certificado». |
| «Alucina con las garantías» | 🔒+💬 | Candado `garantia_inventada` (grave): solo se menciona la garantía que venga en el tratamiento del catálogo (hoy, la de termita de madera seca). Para lo demás: «ese punto lo define el dueño» y ofrece comunicarlo. |
| «Dice "voy a revisar, la cotización te la mando" y nunca manda nada»; «"nosotros te avisamos cuando haya disponibilidad"» | 🔒 | Candado `promesa_vacia` (grave): prometer algo para después solo pasa si en ese turno la conversación se le pasó al dueño. Si no, se pide corrección y, si reincide, sale la pregunta del dato que falta. Además, pedir precio fuerza `cotizar` y, si el modelo no la llama, la corre el servidor. |
| «A mí nunca me llega un mensaje con la autorización» | 🔒 | Cada pase al dueño deja la ficha llena y la conversación en la bandeja. Con `AVISO_DUENO_WA`, además le llega el resumen a su WhatsApp (`app/plagas/aviso.py`). |
| «La agenda la decido yo: tengo tres técnicos y armo rutas» | 🔒 | `AGENDA_MODO=aprobacion`: la visita es una solicitud; el calendario no se toca. |

Y lo que apareció al probar esos cambios (ronda 10 de [LOOP.md](LOOP.md)):

| Regla | Dónde | Cómo |
|---|---|---|
| Una palabra negada no es una señal («ni chicas ni grandes», «no son chiquitas», «en la cocina nunca») | 🔒 | `diagnostico._afirma()`. |
| Rasgos de las dos cucarachas no confirman ninguna «por mayoría» | 🔒 | `_cucaracha()`: con una sola señal de la otra especie ya no se confirma; desempata lo que el lead elige en la tarjeta. |
| No preguntar un dato de precio que esa plaga no usa (metros para la alemana, baños para la hormiga) | 🔒 | Candado `pregunta_dato_ajeno` (grave). |
| No cumplir encargos ajenos (una receta, un poema, una tarea) | 🔒+💬 | Alerta de sistema en ese turno + candado `encargo_ajeno`. |
| No presentarse dos veces | 🔒 | `sin_resaludo()` quita el «¡Hola! Soy Nea…» repetido. |
| Si el modelo reincide, se le quita la frase mala, no el mensaje entero | 🔒 | `podar()` antes del texto de respaldo (`app/plagas/turno.py`). |
| «¿Es peligrosa? ¿Qué pasa si me pica?» no es motivo de pase al dueño | 💬 | El expediente de la araña dice qué contestar (sin diagnosticar) y que la conversación sigue. |

## Qué NO cambió

Todo lo demás es Nea 1.0.0 tal cual: webhook, relay al CRM, coalesce,
seguimiento, candado de cierre, modo cloud, multi-organización. Con `VERTICAL`
vacía este código se comporta exactamente como el raíz (hay una prueba:
`test_sin_el_vertical_todo_sigue_como_la_nea_de_siempre`).
