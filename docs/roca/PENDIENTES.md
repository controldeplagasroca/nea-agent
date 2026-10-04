# Pendientes — lo que falta que el negocio confirme

Este fork se armó con la «Especificación de comportamiento» de Control de
Plagas ROCA. Todo lo que el documento traía está implementado. Lo de abajo es
lo que **no** venía, o venía incompleto. En cada caso Nea hace lo seguro (no
inventa: junta los datos y le pasa la conversación al dueño) hasta que se
complete.

Todo se edita en un solo archivo: [`app/plagas/catalogo.py`](../../app/plagas/catalogo.py).
Después de editarlo: `pytest -q` y redesplegar.

## 1. Precios que hoy cotiza el dueño (falta la fórmula)

| Plaga | Qué falta | Dónde va | Qué hace Nea mientras tanto |
|---|---|---|---|
| Cucaracha americana | La **tarifa base** por tipo de inmueble (casa, departamento, edificio). La regla de los sanitarios ya está: hasta 3 incluidos, $100 por cada adicional, en cada visita. | `PLAGAS["cucaracha_americana"]["precio"]["base"]` | Pregunta tipo de inmueble, registros y sanitarios, los anota en la ficha y pasa al dueño. |
| Roedores | Cada cuántos **metros va una caja cebadero** y el **precio por caja**. | `…["roedores"]["precio"]["m_por_caja"]` y `["precio_por_caja"]` | Pregunta el área, la anota y pasa al dueño. Nunca le pregunta al lead cuántas cajas. |
| ~~Chinches de cama~~ | **Resuelto (3 oct 2026).** Por visita: 1 colchón $1,300; 2 colchones $1,500; +$250 por colchón adicional. Hasta 3 sillones y 6 sillas de comedor van incluidos; +$100 por sillón y +$20 por silla de más. | `…["chinches"]["precio"]` | Cotiza sola. Pide colchones, sillones y sillas en un solo mensaje. |
| Pulgas | Lo mismo que chinches (la fórmula de pulgas no se ha dado). | `…["pulgas"]["precio"]` | Pregunta colchones totales, sillones y sillas, los anota y pasa al dueño. |

En cuanto esos `None` tengan número, la calculadora ya escrita en
`app/plagas/precios.py` cotiza sola y arma el resumen. Hay una prueba que lo
demuestra con la americana (`test_americana_cobra_el_cuarto_sanitario_…`).

## 2. Cobertura: lo que supuse

La especificación dice qué se excluye (Tepito, Ecatepec, Gustavo A. Madero) y
qué va solo en miércoles (Lerma, Toluca), pero no qué **sí** se atiende.

- **Supuesto:** se atiende Ciudad de México (CP 01000–16999) y Estado de México
  (CP 50000–57999), menos lo excluido. Cualquier otro código postal →
  «por ahora no damos servicio ahí». Se cambia en `COBERTURA_CPS`.
- **Rangos de CP usados para excluir sin que el lead nombre la zona:**
  Gustavo A. Madero 07000–07999, Ecatepec 55000–55549. Tepito solo se detecta
  por nombre (comparte código postal con el resto de la colonia Morelos).
- **Lerma** 52000–52059 y **Toluca** 50000–50299 por CP, además del nombre.

Si el negocio no llega a todo el Estado de México, hay que acotar `COBERTURA_CPS`.

## 3. Señales de la tijerilla (propuesta mía)

La sección 4.3 trae señales para siete plagas, pero no para la tijerilla, que
sí tiene precio. Le puse tres señales genéricas (pincitas en la cola, cuerpo
alargado café oscuro, zonas húmedas/puertas y ventanas) para poder aplicar la
regla de «mínimo dos señales». **Revísalas**: están en
`PLAGAS["tijerilla"]["senales"]`.

## 4. Recomendaciones para que la plaga no vuelva (fase 9)

La especificación menciona un «catálogo aprobado» de recomendaciones, pero solo
trae las reglas de contención: hormiga (sin aerosol ni lavar con detergente o
cloro) y cucarachas (sin aerosol ni remedios caseros). Nea dice esas, y solo
esas, al registrar la solicitud de visita. Para las demás plagas no dice nada
(no improvisa). Si hay más indicaciones, van en el campo `contencion` de cada plaga.

## 5. IVA

El documento dice que «el IVA solo se menciona si el cliente pide factura», sin
decir si se suma o ya va incluido. Puse: «Si necesitas factura, al precio se le
agrega el IVA.» (`NEGOCIO["factura"]`). Confirmar la redacción.

## 6. Emojis del bloque de cotización

El PDF traía los emojis como cuadros negros (■). Usé 📋 resumen, el emoji de
cada plaga, 🛠️ tratamiento, 💵 precio, 🎁 promo, 🤝 forma de pago. Se cambian en
`bloque_de_cierre` (`app/plagas/precios.py`) y en el campo `emoji` de cada plaga.

## 7. Aprobación de la visita: cómo quedó implementada

La especificación pide que la visita no se reserve en el calendario real hasta
que el dueño la apruebe. Con Vocero raíz eso se hace así (`AGENDA_MODO=aprobacion`):

1. Nea ofrece horarios reales de la agenda del CRM y el lead elige uno.
2. Nea **no** crea la cita: anota en la ficha del contacto `cita_solicitada`,
   la dirección y una nota con todo, y hace **handoff** (motivo `cliente`).
3. El dueño ve la alerta en su bandeja, confirma con el cliente y crea la cita
   en el calendario del CRM. Con `AVISO_DUENO_WA` puesta, además le llega el
   resumen a su WhatsApp ([INSTALACION.md](INSTALACION.md), «Que te avise a tu
   WhatsApp»).

Mientras tanto ese horario **sigue libre** en la agenda: si dos personas piden
la misma hora, las dos quedan como solicitud y el dueño decide. Si se prefiere
que Nea reserve de una vez, `AGENDA_MODO=directa`.

Consecuencia: mover o cancelar una cita ya aprobada lo hace el dueño (el
cliente que escribe «mi cita» entra como cliente recurrente y se le pasa).
La especificación pedía que Nea las moviera y cancelara sola; con el CRM raíz
la cancelación no está expuesta al agente.

## 8. Decisión de producto que el documento dejó abierta

«Cliente recurrente que pide otra plaga distinta»: hoy **no** se le cotiza la
plaga nueva; se le pasa al dueño (lo conservador). Si se quiere que cotice
antes del handoff, es un cambio en `paso_actual` (`app/plagas/caso.py`).

## 9. Lo que salió de los dos audios largos (1 de octubre, 19:05 y 19:09)

Los audios ya se transcribieron y se usaron (ronda 10 de [LOOP.md](LOOP.md)).
De ahí salieron tres textos que **redacté yo con tus palabras** y conviene que
revises, porque Nea los dice tal cual:

| Qué | Texto que quedó | Dónde se cambia |
|---|---|---|
| Tranquilidad al confirmar cucaracha alemana | «No te preocupes: no es por falta de higiene. Es un insecto que suele entrar a casa sin que nos demos cuenta, y tiene solución.» | `PLAGAS["cucaracha_alemana"]["tranquilidad"]` |
| ¿Es tóxico? ¿Daña la salud? | «Los productos que se usan no ponen en riesgo la salud de quienes viven en el inmueble.» | `DUDAS["seguridad"]` |
| ¿Cuándo se puede volver a entrar? | «…de 15 a 20 minutos después de la aplicación.» | `DUDAS["reingreso"]` y `REINGRESO_MINUTOS` |
| ¿Sí funciona? | «El tratamiento sí es efectivo contra la plaga.» | `DUDAS["eficacia"]` |

Y cuatro cosas que los audios no alcanzan a definir:

- **Tranquilidad para las demás plagas.** Solo la diste para la cucaracha de
  cocina. Las otras confirman sin esa línea. Si quieres una por plaga, es el
  campo `tranquilidad` de cada una.
- **Garantía.** En el audio dices que tu bot «empieza a alucinar cuando le
  digo que no hay garantías». Como no quedó claro si hay o no, Nea **ni la
  afirma ni la niega**: dice que ese punto lo defines tú y ofrece comunicar al
  cliente contigo (la única garantía que sí menciona es la de 3 años de la
  termita de madera seca, que venía en tu documento). Si la regla es «no hay
  garantía» o «hay X», dímelo y se vuelve un texto fijo.
- **Casos particulares de seguridad** (embarazo, bebés, alergias o asma,
  mascotas, peceras). Nea dice lo aprobado en general y que la indicación para
  ese caso la confirmas tú. No dice «es seguro para mascotas» ni «no es
  tóxico» con esas palabras. Si tienes una indicación fija para alguno, va en `DUDAS`.
- **Rutas por zona.** Lo de acomodar las visitas por ruta (norte, sur…) lo
  dejaste para después, y así quedó: hoy cada visita llega como solicitud y la
  acomodas tú.
