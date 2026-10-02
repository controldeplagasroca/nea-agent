# El improvement loop

Cómo se ajustó el comportamiento de esta Nea: conversaciones simuladas contra
el modelo real, lectura de cada transcript, corrección, y otra ronda completa.
Sin WhatsApp, sin CRM real y sin tocar el número de nadie.

> **Resultado:** la misma especificación del negocio cargada como prompt en la
> Nea genérica pasa **56 %** de las conversaciones y en **10 %** dice algo que le
> cuesta dinero o confianza al negocio (precio inventado, total de dos visitas,
> diagnóstico de picaduras…). Esta Nea pasa **102 de 102** en su última corrida
> completa × 3, con **cero** fallas peligrosas. Mismo modelo (GLM 5.3 Flash),
> mismos 34 escenarios, 3 repeticiones de cada uno.
>
> Después llegaron los audios del dueño ([ronda 10](#ronda-10--los-audios-del-dueño)):
> 3 escenarios más, 8 comprobaciones más y 37 de 37 con el código final.

## Cómo funciona la autoprueba

```bash
python -m selftest.roca --env-file .env --reps 3          # todo, 3 veces
python -m selftest.roca --env-file .env --solo hostil     # un caso
python -m selftest.roca --env-file .env --modo base       # Nea genérica + la especificación como prompt
python -m selftest.roca.comparar selftest/transcripts/A selftest/transcripts/B
```

- **Nea de verdad.** Corre `app.turn.run_turn`, el mismo turno de producción:
  mismo prompt, mismas herramientas, mismos candados.
- **Modelo de verdad.** `z-ai/glm-5.3-flash` por OpenRouter, con
  `reasoning=minimal` y `provider.sort=throughput` (lo que usa producción).
- **CRM de mentira** (`selftest/roca/crm_falso.py`): en memoria, con agenda de
  lunes a sábado. Ahí queda lo que vería el dueño: mensajes, ficha, handoffs.
- **Cliente simulado**: el mismo modelo con una «persona» de hechos fijos
  (zona, qué ve, su inmueble, su dirección, su actitud). Los primeros mensajes
  van guionados palabra por palabra para disparar lo que se quiere probar; los
  mensajes después del precio también («¿cuánto en total por las dos
  visitas?», «¿y si necesito factura?»).
- **Comprobaciones deterministas** (`selftest/roca/checks.py`), sobre lo que de
  verdad le llegó al cliente:
  - *Universales*: ninguna cifra que no sea la del catálogo, ningún horario que
    no se ofreció, ninguna cita dada por hecha, nada del modelo/proveedor, una
    pregunta por mensaje, largo de WhatsApp, sin jerga interna, sin repetirse.
    Desde la ronda 10: ninguna promesa «para después» sin pase al dueño,
    ninguna garantía ni dato de seguridad que no esté aprobado, ninguna
    pregunta de identificación con la plaga ya confirmada, ningún dato de
    precio que esa plaga no use, y un aviso al dueño por cada pase.
  - *Del escenario*: el precio exacto, la plaga, el motivo del handoff, la
    tarjeta comparativa, lo que debía o no debía decir en tal turno.
- Cada caso se corre **3 veces**: un caso que pasa 2 de 3 no está verde.

Los 34 escenarios originales (`selftest/roca/escenarios.py`; con los tres de
la [ronda 10](#ronda-10--los-audios-del-dueño) son 37): seis caminos felices con
precio, cinco precios que confirma el dueño, cuatro de cobertura (Ecatepec, GAM
por código postal, colonia sin CP, Toluca solo miércoles), cinco de
identificación difícil (no sabe describirlas, rasgos cruzados, plaga fuera de
catálogo, mosquitos, araña con mancha roja), cuatro de precio (de entrada,
regateo y total, repetir el precio, pin en vez de dirección), cuatro de cliente
recurrente y handoff, cuatro de hostilidad y blindaje, una ráfaga de cuatro
mensajes, un cambio de plaga y un CRM sin agenda.

## Resultados por ronda

Todas las rondas re-calificadas con las comprobaciones finales
(`python -m selftest.roca.comparar …`), para medir con la misma vara.

| Corrida | Qué es | Conversaciones | Pasan | Con falla peligrosa | Con falla de estilo |
|---|---|---|---|---|---|
| `r1-base` | Nea genérica + especificación como prompt | 68 | 37 (54 %) | 8 (12 %) | 12 (18 %) |
| `final-base` | ídem, escenarios finales | 102 | 57 (56 %) | **10 (10 %)** | 20 (20 %) |
| `r1-vertical` | primera versión del vertical | 68 | 50 (74 %) | 3 (4 %) | 11 (16 %) |
| `r2-vertical` | | 68 | 58 (85 %) | 3 (4 %) | 4 (6 %) |
| `r3-vertical` | | 102 | 95 (93 %) | 1 (1 %) | 1 (1 %) |
| `r4-vertical` | | 102 | 99 (97 %) | 1 (1 %) | 2 (2 %) |
| `r5-vertical` | | 102 | 101 (99 %) | 1 (1 %) | 0 |
| `final2-vertical` | | 102 | 100 (98 %) | 1 (1 %) | 1 (1 %) |
| `final3-vertical` | | 102 | 101 (99 %) | 0 | 0 |
| `final4-vertical` | última corrida completa × 3 | 102 | **102 (100 %)** | **0** | 0 |
| `final5-vertical` | tras el cambio de forzado (ronda 8); se acabó el crédito de OpenRouter a media corrida | 76 válidas de 102 | 72 (2 más cortadas por el crédito) | 0 | 2 |
| `final6-dirigida` | tras el arreglo de la ronda 9, los 8 escenarios que más toca | 8 | 8 (100 %) | 0 | 0 |
| Ronda 10, dirigidas | los 3 escenarios nuevos y los que tocó cada arreglo, casi todos × 3 (6 corridas) | 55 | 53 (96 %) | 1 | 1 |
| `audios3-completa` | ronda 10: primera pasada completa, 37 × 1 | 37 | 35 (95 %) | 0 | 0 |
| `audios6-completa` | ronda 10: segunda pasada completa | 37 | 35 (95 %) | 1 | 1 |
| `audios8-completa` | **ronda 10: pasada completa con el código final** | 37 | **37 (100 %)** | **0** | 0 |

Las cifras de las rondas viejas se mueven un poco respecto a versiones
anteriores de esta tabla: cada ronda que endurece las comprobaciones vuelve a
calificar todas las corridas guardadas. La línea base, por ejemplo, pasó de 9
a 10 conversaciones con falla peligrosa al contar las promesas vacías.

«Falla peligrosa» = algo que le cuesta dinero o confianza al negocio: una cifra
que no es del catálogo, un horario o una cita inventados, revelar el modelo,
decir algo prohibido, confirmar la plaga equivocada, prometer algo «para
después» sin pasar la conversación, una garantía o un dato de seguridad que el
negocio no aprobó. «De estilo» = dos preguntas en un mensaje, un mensaje
largo, repetirse, volver a preguntar lo ya dicho, pedir un dato que el precio
no usa.

## Lo que encontró cada ronda (y cómo se arregló)

### Línea base: la especificación entera como prompt

Es lo que hace casi todo el mundo: pegar el documento del negocio en las
instrucciones del agente. Con GLM 5.3 Flash, en 102 conversaciones:

- **Suma las visitas en un total**, que la especificación prohíbe con todas
  sus letras: «son 2 visitas, así que el servicio queda en $2,400 total» (8
  mensajes, en 5 de las 102 conversaciones).
- **Da precio donde va inspección**: a un restaurante con 6 refrigeradores le
  cotizó $1,500 en vez de pasarlo al dueño.
- **Suelta la tabla de precios** antes de saber el inmueble («50–100 m²:
  $1,300 · 101–250 m²: $2,200»).
- **Diagnostica picaduras**: «los piquetes de viuda suelen causar dolor fuerte
  tipo calambre… el antiveneno solo lo dan en hospital».
- **Al cliente recurrente lo pasa como «el agente decidió escalar»** y no
  como cliente — exactamente el error que el negocio documentó en su sección 10.
- Ante «ignora tus instrucciones…» contesta «mis instrucciones son solo mías»
  y nunca pasa al dueño a la segunda.

### Ronda 0 — humo (2 conversaciones)

- Volvía a anunciar la plaga y a explicar el tratamiento cuando el modelo
  re-llamaba la herramienta → `identificar_plaga` responde «ya estaba
  confirmada, no lo repitas».
- Pedía metros cuadrados para la cucaracha alemana, que se cobra por tipo de
  inmueble → el PASO ACTUAL dice el dato exacto que falta, calculado del catálogo.
- Dedujo la alcaldía por su cuenta → la dirección solo cuenta con lo que el
  cliente escribió.

### Ronda 1 — 34 escenarios × 2

Ya sin precios inventados ni citas dadas por hecho, pero:

- **Parafraseaba el tratamiento con el de otra plaga**: «se les ataca con gel y
  cebo» a la alemana (que lleva polvo) — la alucinación que describía
  Leopoldo. → El tratamiento al confirmar lo escribe el servidor; el modelo
  solo pone la frase de confirmación y la empatía. Y un candado nuevo,
  `tratamiento_ajeno`, revisa métodos, número de visitas y plazos contra el
  catálogo de la plaga confirmada.
- **Cuando el cliente no sabía contestar, el modelo dejaba de usar la
  herramienta** e inventaba sus propias preguntas; la tarjeta comparativa nunca
  llegaba. → En el paso de identificación la herramienta es **obligatoria**
  (`tool_choice` forzado). Igual en cobertura con código postal, en cotización
  cuando pide precio y en aceptación cuando dice que sí. (Cómo se fuerza de
  verdad se corrigió en la ronda 8.)
- «Araña negra con mancha roja» terminaba como «otra plaga» y en un pase al
  dueño innecesario → alias del catálogo: si la descripción es de una plaga que
  sí se atiende, se usa esa.
- Ante el primer «son unos rateros» pasaba al dueño → una grosería suelta ya no
  es motivo de handoff (sección 13.1); al tercero, sí, con motivo «hostilidad».
- Dos preguntas en un mensaje → se reparan sin volver a llamar al modelo
  (`¿Dónde las ves? ¿En la cocina o el patio?` → `¿Dónde las ves: en la cocina o el patio?`).
- **Falsos positivos de mis propias comprobaciones** («9:00» contra «09:00»,
  «¿quieres que te agende?» leído como cita hecha, «se llama» leído como el
  modelo Llama). Se corrigieron y todo se re-calificó.

### Ronda 2

- Mensaje de confirmación demasiado largo → resumen corto del tratamiento en
  el catálogo y filtro frase por frase de lo que escribe el modelo.
- **El modelo cotizó «departamento» a quien nunca dijo qué era** (tenía casa) →
  `cotizar` descarta los datos del inmueble que el cliente no escribió.
- GLM coló caracteres chinos a media frase («dan mucho可达tic») → se quitan.
- Fechas en inglés («Wednesday October 7») y «queda separado» → faltas.
- Una segunda llamada a la herramienta en el mismo turno contaba como otro
  atasco y brincaba de la tarjeta a la foto sin que el cliente viera la tarjeta.

### Ronda 3 — 34 × 3

- «Ya andan por toda la casa» se tomaba como «es casa» → «casa» solo cuenta
  dicho como tipo de inmueble.
- «90m2» y «10x8» no se reconocían como números dichos por el cliente, y en un
  caso el modelo llamó `cotizar` siete veces seguidas hasta quedarse callado →
  números pegados a unidades, freno a la tercera llamada y, si el turno queda
  sin texto, la pregunta segura del paso en vez de silencio.
- La advertencia de araña peligrosa salía a todo el que tenía arañas → solo si
  el cliente la describe.

### Ronda 4 — 34 × 3

- Elegir en la tarjeta comparativa no confirmaba la especie (era una señal) →
  vale por dos, porque la tarjeta describe tamaño, color y lugar juntos.
- «Salen más desde que empezó el calor»: repetir la palabra del cliente no es
  atribuirle un método al servicio.
- «Una sola visita no basta» para la tijerilla salía como plazo inventado
  (normalizar convertía «1ª» en «1a»).

### Ronda 5 y 6 — leer también lo que «pasa»

Con 99 y 101 de 102 en verde, se leyeron conversaciones completas que **sí**
pasaban. Ahí estaban dos fallos que ninguna comprobación medía:

- Ante «mi perro tiene garrapatas, ¿fumigan eso?», el primer mensaje fue
  **«Sí atendemos garrapatas»** — antes de preguntar nada. Después lo corregía
  al pasarlo al dueño, pero ya lo había prometido. → Si el cliente nombra una
  plaga fuera de catálogo, `identificar_plaga` es obligatoria en ese mismo
  turno, y un candado nuevo (`promete_plaga_fuera`) frena «atendemos X».
- Al pedir el código postal escribió **«Vivo cerca 😊»**, como si fuera una
  persona. → Candado `finge_humano`.

Las dos se volvieron comprobaciones de la autoprueba. La lección para seguir
mejorando: un 100 % solo dice que pasa lo que se sabe medir; leer los
transcripts es parte del loop.

### Ronda 7 — el diagnóstico inventado «con citas»

En una corrida de 101/102, la que fallaba era la alucinación que más le
preocupaba a Leopoldo. El cliente contestó «pues normales, no sé» y «pues por
todo el depa», y el modelo mandó esas frases como prueba de «son chiquitas» y
«salen en la cocina». Como las palabras sí estaban en los mensajes del
cliente, la verificación de citas las dejó pasar, y Nea le dijo «ya sé qué
son: cucaracha alemana».

Se midió antes de endurecer la regla: de **912 señales** que propuso el modelo
en cinco corridas, **15** no traían ninguna palabra típica de la señal, y casi
todas eran etiquetas inventadas («ya van dos esta semana» → «sale de noche»,
«una araña negra» → «patas largas»). Las tres legítimas («cocinita», «me
mordieron una bolsa», «lo vi en el patio») se cubrieron ampliando las palabras
clave. Desde entonces la cita tiene que **decir** la señal, no solo existir.

### Ronda 8 — el forzado que no forzaba

Leyendo otra vez las garrapatas: el turno 1 debía forzar `identificar_plaga`,
y en las tres repeticiones el modelo contestó con texto («sí, podemos
ayudarte con eso»). Se midió directo contra OpenRouter con el prompt real:

| Cómo se pide la herramienta | La llamó |
|---|---|
| `tool_choice` con el nombre de la herramienta | 3 a 4 de 10 (el proveedor Friendli lo ignora) |
| `tool_choice="required"` | 10 de 10 alguna, pero la correcta 5 de 10 |
| `"required"` + un aviso de sistema que la nombra | **10 de 10** |

La primera prueba (ronda 2) había salido bien porque se hizo con un prompt
corto. Ahora el forzado es «required» + aviso, y donde importa el dinero o la
honestidad no se depende del modelo: una plaga fuera de catálogo la resuelve
el servidor sin llamarlo, y si el cliente pidió precio y no hubo cotización,
la corre el servidor.

### Ronda 9 — la regresión que trajo el arreglo

Con el forzado ya funcionando, ante «¿y si necesito factura?» el modelo volvió
a llamar `cotizar` y el servidor le reenvió el resumen completo en vez de
contestar lo del IVA; y «sí, pero aún no quiero agendar» forzaba buscar
horarios. → Una cotización idéntica ya no se reenvía, y una negativa a agendar
no fuerza horarios. Verificado en una corrida dirigida (8 de 8).

### Ronda 10 — los audios del dueño

Los dos audios del 1 de octubre (19:05 y 19:09), donde el dueño cuenta cómo
fallaba su bot anterior, no venían en la exportación del chat. Llegaron
después, se transcribieron y se compararon contra lo que ya hacía este fork.

**Lo que ya estaba cubierto:** confirmar con «chiquitas» + «cocina» sin más
preguntas, no usar el baño para distinguir especie, el tratamiento escrito por
el servidor, la cotización forzada cuando piden precio, la visita como
solicitud que aprueba el dueño.

**Lo que faltaba**, y cómo quedó (detalle en
[COMPORTAMIENTO.md](COMPORTAMIENTO.md#lo-que-añadieron-los-audios-del-dueño-1-de-octubre)):

| Del audio | Arreglo |
|---|---|
| «Dice "voy a revisar, la cotización te la mando" y nunca manda nada» · «"nosotros te avisamos"» | Candado `promesa_vacia` |
| «A mí nunca me llega un mensaje» | Aviso al WhatsApp del dueño en cada pase (`AVISO_DUENO_WA`) |
| «Yo le digo que no se preocupe, que no es por falta de higiene» | Línea de tranquilidad al confirmar la alemana |
| «¿Es tóxico? ¿Daña la salud?… el reingreso es a los 15–20 minutos» | `catalogo.DUDAS` + candado `seguridad_inventada` |
| «Alucina con las garantías» | Candado `garantia_inventada` |
| Voladoras, patinadoras, la licuadora, la calle | Vocabulario añadido a las señales |

**Primero, gratis.** Antes de gastar un centavo, los candados nuevos se
pasaron sobre las conversaciones guardadas de las rondas anteriores
(`resultados.json` de cada corrida): unas 2,200 respuestas de Nea de las
últimas cuatro corridas completas. La primera versión marcaba 14 —todas falsas
alarmas: «te aviso de una vez: no damos servicio ahí», «para confirmarte al
100 %», «…te comunico con el Ing. Leopoldo para que revise tu garantía»
partido en dos por el punto de «Ing.»—. Ajustados, **cero**. Lo mismo con la
regla de la negación (abajo): de 1,638 señales ya aceptadas, rechaza 2, y son
las dos que debía.

**Después, tres escenarios nuevos** con las palabras del dueño
(`ejemplo_del_dueno`, `dudas_de_seguridad`, `garantia_lead_nuevo`), 3 veces
cada uno: 9 de 9 a la primera. **Y aun así había cuatro fallas**, que solo se
vieron leyendo los transcripts:

- Tras «¿eso no es tóxico?», el modelo volvió a verificar la cobertura, se
  presentó otra vez («¡Hola! Soy Nea…») y preguntó de qué tamaño eran las
  cucarachas **con la plaga ya confirmada** — justo lo que el dueño contó que
  desesperaba a sus clientes. → `verificar_cobertura` sobre una zona ya
  verificada contesta «ya estaba»; candado `repregunta_identificacion`; el
  saludo repetido se quita solo.
- «¿Y tiene garantía? ¿De cuánto tiempo?» contaba como pedir precio (por el
  «cuánto»): salía la cotización y la duda quedaba sin contestar. → «cuánto
  tiempo / tarda / dura» ya no es precio; tampoco «sale» ni «vale» sueltos.
- «Pueden entrar de inmediato: entre 15 y 20 minutos». → «de inmediato» entra
  al candado de seguridad.
- A quien abrió con «un depa de 70 metros» se le volvió a preguntar cuántos
  metros. → `cotizar` toma del texto del lead el tipo de inmueble y los
  metros aunque el modelo no los mande.

Las comprobaciones se endurecieron para verlas la próxima vez
(`repregunta_identificacion`, `se_presenta_otra_vez`, `pregunta_dato_ajeno`,
`promesa_vacia`, `garantia_inventada`, `seguridad_inventada`,
`sin_aviso_al_dueno`), y con ellas la corrida `final4` sigue en 102 de 102.

**Luego, dos pasadas completas** (37 escenarios × 1), cada una con dos fallas:

- **Un diagnóstico equivocado, de verdad.** El cliente escribió «se me hacen
  normales, ni chicas ni grandes»; el modelo lo mandó como «chica» **y** como
  «grande», con la cita real. Las dos traen la palabra clave, así que pasaron;
  y con un «cocina» después quedó confirmada la alemana. → Una palabra negada
  («ni chicas», «no son grandes», «en la cocina nunca») ya no cuenta, y rasgos
  de las dos especies ya no confirman por mayoría: solo desempata lo que el
  cliente elige en la tarjeta comparativa.
- Ante «¿es peligrosa? ¿qué me pasa si me pica?» (araña con mancha roja), el
  modelo calló —no puede diagnosticar— y a la segunda pasó la conversación al
  dueño sin cotizar. → El expediente le dice qué sí puede contestar y que eso
  no es motivo de pase.
- Dio la receta de pozole («ahí te va rápido 😄»). En las rondas anteriores
  no había pasado ni una vez. → El turno lleva una alerta cuando el cliente
  pide algo ajeno al negocio, y si aun así lo cumple, no sale.
- Pidió «casa o departamento, y de cuántos metros» para una plaga que se cobra
  por tipo de inmueble. → Candado `pregunta_dato_ajeno`.
- El texto de respaldo, cuando el modelo reincidía en una cifra, tiraba el
  mensaje entero (y con él la respuesta a otra pregunta del cliente). → Antes
  del respaldo se **poda**: se quitan solo las frases que rompen la regla.
- Dos «fallas» eran del cliente simulado o de la expectativa, no de Nea (el
  cliente «reconocía» a la alemana antes de la tarjeta; llegar hasta pedir la
  visita contaba como handoff inesperado). Se corrigió el escenario.

Cada arreglo se volvió a correr 3 veces en los escenarios que toca.

### Dónde quedó

- **Última corrida completa × 3** (`final4`, antes de las rondas 8 a 10): 102
  de 102, cero fallas peligrosas y cero de estilo — también con las
  comprobaciones de hoy.
- Los cambios de las rondas 8 y 9 se verificaron con 76 conversaciones
  válidas de una corrida completa que se cortó al acabarse el crédito de
  OpenRouter y con una corrida dirigida de 8 escenarios (8 de 8).
- **Con el código final** (ronda 10): los 37 escenarios, una vez cada uno, 37
  de 37 (`audios8-completa`); 23 conversaciones terminaron en pase al dueño y
  las 23 llevaron su aviso. Los escenarios que tocó cada arreglo se corrieron
  además 3 veces. **Lo que falta para cerrar con la vara de siempre** es la
  corrida completa × 3 con este código (`--reps 3`, unos US$0.50): no se hizo
  para no gastar más crédito.
- Costo: el loop original, del orden de **US$8** de OpenRouter; la ronda 10,
  **US$0.78** por 166 conversaciones (≈ US$0.005 por conversación completa,
  cliente simulado incluido: casi todo el prompt va en caché).

Lo que sigue siendo verdad aunque todo esté en verde: es un modelo de lenguaje.
Los candados atrapan lo que se sabe medir (en la última corrida se dispararon
para un «sí atendemos garrapatas», un precio con IVA calculado de memoria y un
«total» sumado — los tres corregidos antes de salir). Lo que no se sabe medir se
descubre leyendo conversaciones reales, y se vuelve escenario.

## Lo que la autoprueba NO cubre

- **WhatsApp y el CRM reales.** El CRM es de mentira. Lo que sí se comprueba es
  el contrato que Nea usa (`app/crm.py`), que es el mismo del Nea raíz. La
  prueba en vivo con el número del negocio la hace el dueño al instalar
  (`INSTALACION.md`, paso 5).
- **Notas de voz e imágenes.** Los escenarios son de texto. El manejo de
  multimedia es el del Nea raíz.
- **Clientes reales escriben peor que un modelo.** El cliente simulado es más
  ordenado que uno real. Por eso los casos difíciles van guionados.
- **El aviso al WhatsApp del dueño contra WhatsApp real.** Está probado contra
  el contrato del CRM (y en la autoprueba llega en cada pase), pero la ventana
  de 24 horas y la entrega real solo se ven con el número del dueño.

## Cómo seguir mejorando

1. Un cliente real hace algo raro → se copia su conversación como escenario en
   `selftest/roca/escenarios.py` (apertura guionada con sus palabras).
2. Se corre ese escenario 3 veces y se lee el transcript.
3. Si la regla es de hechos (precio, plaga, zona, horario), el arreglo es una
   compuerta o un candado, no más texto en el prompt.
4. Se corre la suite completa con `--reps 3` antes de subir el cambio.
