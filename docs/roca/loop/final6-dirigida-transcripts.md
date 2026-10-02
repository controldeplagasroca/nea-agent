### alemana_casa · rep 1 · ✅ PASA
_Cucaracha alemana en casa: del saludo a la solicitud de visita_

**Lead 1:** hola buenas, tengo un problema con cucarachas
**Nea 1** _(cobertura, 1.8 s)_:
> ¡Hola! 👋 Soy Nea, el agente de IA de Control de Plagas ROCA. Te ayudo a resolver tu problema de cucarachas.
> 
> Ay qué fastidio, con lo sigilosas que son. Para empezarnos a ayudar, ¿en qué colonia o zona estás?

**Lead 2:** Colonia Del Valle, cp 03100
> 🔧 `verificar_cobertura` {"zona": "Colonia Del Valle", "codigo_postal": "03100"}
> 🔒 candados: reparado
**Nea 2** _(identificacion, 3.1 s)_:
> ¡Buenas noticias! Sí damos servicio en la Del Valle 👍
> 
> Ahora, para darte el tratamiento correcto: Son chicas (de 1 a 2 cm, café claro) o grandes (de 4 a 5 cm, café rojizo oscuro). Y ¿en qué parte de la casa las ves más?

**Lead 3:** Chiquitas, café claro. En la cocina, detrás del refri y en los gabinetes
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "tamano_chica", "cita": "Chiquitas, café claro"}, {"senal": "ubicacion_cocina", "cita": "En la cocina, detrás del refri y en los gabinetes"}]}
**Nea 3** _(procedimiento, 4.0 s)_:
> Por lo que me cuentas —chiquitas, café claro y detrás del refri en la cocina— es la *cucaracha alemana* 🪳 Sí es de las más incomodas porque se esconden justo en los equipos calientitos.
> 
> 🛠️ Se aplica polvo fino focalizado en nidos y refugios (no es aspersión general): la 1ª visita elimina adultos y jóvenes y la 2ª rompe el ciclo de los huevecillos.
> 🗓️ 2 visitas (entre 8 y 10 días entre una y otra).
> 
> ¿Has notado si han aumentado estos días?

**Lead 4:** Sí, bastante esta semana ya nose de donde salieron tantas
**Nea 4** _(cotizacion, 2.2 s)_:
> Ay, sí se les debe hacer un poquito pesado ya 😅 Justo por eso conviene atacarlas pronto.
> 
> Mira, para el tratamiento contra cucarachas alemanas son *2 visitas* (entre 8 y 10 días entre una y otra), con polvo fino focalizado en nidos y refugios, no una aspersión general. Muy efectivo para cuando ya se multiplicaron.
> 
> ¿Quieres que te diga cuánto costaría? 👀

**Lead 5:** Sí dime
> 🔧 `cotizar` {"tipo_inmueble": "departamento"}
**Nea 5** _(cotizacion, 3.1 s)_:
> ¡Claro! Solo me falta un dato para el precio exacto: ¿es casa, departamento o local comercial?

**Lead 6:** Casa
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
**Nea 6** _(aceptacion, 2.7 s)_:
> 📋 *Resumen de tu cotización*
> 🪳 Cucaracha alemana
> 🛠️ Tratamiento: 2 visitas (entre 8 y 10 días entre una y otra)
> 💵 $1,200 MXN por visita (casa)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 7:** Va, está bien el precio. Qué horarios tienes?
> 🔧 `propose_slots` {"fecha": "2026-10-05"}
**Nea 7** _(agendamiento, 3.4 s)_:
> ¡Perfecto, gracias! 🙌 Estos son los horarios disponibles:
> 
> - lunes 5 de octubre, 09:00
> - lunes 5 de octubre, 11:00
> - lunes 5 de octubre, 13:00
> 
> ¿Cuál te acomoda mejor?

**Lead 8:** El de las 9 de la mañana del lunes
**Nea 8** _(agendamiento, 1.5 s)_:
> ¡Va, lunes 5 a las 09:00! 📅
> 
> Para dejar tu solicitud necesito tu dirección completa por escrito:
> 
> 🏠 Calle y número exterior, colonia, alcaldía y una referencia para llegar (entre qué calles o cómo se ve tu fachada).

**Lead 9:** Heriberto Frías 1125, colonia Del Valle, Benito Juárez. Referencia: entre Luz Saviñón y Xola, portón negro
> 🔧 `book_session` {"start_utc": "2026-10-05T15:00:00Z", "dia_confirmado": "lunes 5 de octubre a las 9 de la mañana", "calle": "Heriberto Frías", "numero_exterior": "1125", "colonia": "Del Valle", "alcaldia_municipio": "Benito Juárez", "referencia": "entre Luz Saviñón y Xola, portón negro"}
**Nea 9** _(visita_solicitada, 4.2 s)_:
> ✅ Listo: registré tu solicitud de visita para el lunes 5 de octubre, 09:00.
> 
> 📍 Heriberto Frías 1125, Del Valle, Benito Juárez (ref.: entre Luz Saviñón y Xola, portón negro)
> 
> El Ing. Leopoldo te la confirma por aquí en breve; mientras tanto queda como solicitud.
> 
> ⚠️ Antes y entre visitas, no uses aerosol ni remedios caseros.

Handoffs: ['cliente']
Ficha en el CRM: `{"geo": "Colonia Del Valle CP 03100", "plaga": "Cucaracha alemana", "tipo_inmueble": "casa", "cotizacion": "$1,200 MXN por visita (casa)", "datos_cotizacion": "tipo_inmueble=casa", "calificado": true, "direccion": "Heriberto Frías 1125, Del Valle, Benito Juárez (ref.: entre Luz Saviñón y Xola, portón negro)", "cita_solicitada": "lunes 5 de octubre, 09:00", "resultado": "agendo", "notas": "SOLICITUD DE VISITA pendiente de aprobar: lunes 5 de octubre, 09:00 — Cucaracha alemana — $1,200 MXN por visita (casa) — Heriberto Frías 1125, Del Valle, Benito Juárez (ref.: entre Luz Saviñón y Xola, portón negro)"}`

---

### cucaracha_no_sabe · rep 1 · ✅ PASA
_No sabe describirlas: tarjeta comparativa y luego confirma_

**Lead 1:** hola tengo cucarachas
**Nea 1** _(cobertura, 1.6 s)_:
> ¡Hola! 👋 Soy Nea, la agente de IA de Control de Plagas ROCA. Ayudamos a resolver ese tipo de problemas a domicilio.
> 
> Ay, qué moleso eso de las cucarachas 🙈 Te ayudo con gusto. ¿En qué colonia o zona estás?

**Lead 2:** estoy en la del valle, cp 03100
> 🔧 `verificar_cobertura` {"codigo_postal": "03100"}
> 🔒 candados: reparado
**Nea 2** _(identificacion, 2.0 s)_:
> ¡Buenas noticias! Sí damos servicio en la Del Valle 🙌
> 
> Ahora, para ayudarte bien: Cómo son las cucarachas que has visto, más chicas o más grandes. Y ¿en qué parte de la casa aparecen?

**Lead 3:** pues normales, no sé
> 🔧 `identificar_plaga` {"plaga": "cucaracha"}
**Nea 3** _(identificacion, 2.6 s)_:
> ¡Ya casi lo tengo! 😄 Para ubicar bien de cuál se trata: ¿son chiquitas (de 1 a 2 cm, café claro) o grandes (de 4 a 5 cm, café rojizo oscuro)?

**Lead 4:** pues no sé, normales nada mas. se ven por todo el depa
> 🔧 `identificar_plaga` {"plaga": "cucaracha"}
**Nea 4** _(identificacion, 2.1 s)_:
> Tranquilo, con un par de datos sencillos lo resolvemos 😊 ¿En qué parte las ves más: en la cocina (detrás del refri, en los gabinetes, cerca de la tarja) o cerca de coladeras, drenajes o el patio?

**Lead 5:** por todo el depa le digo, salen de noche mas que nada
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "salen de noche", "cita": "salen de noche mas que nada"}]}
**Nea 5** _(identificacion, 4.2 s)_:
> Para ubicarla bien, compárala con estas dos 🪳
> 
> *Alemana (de cocina)*: chica, de 1 a 2 cm, café claro con dos rayitas negras. Se ve sobre todo en la cocina: detrás del refri o el microondas, en gabinetes, cerca de la tarja.
> 
> *Americana (de drenaje)*: grande, de 4 a 5 cm, café rojizo oscuro. Sale en patios, sótanos, estacionamiento o áreas comunes, cerca de coladeras y drenajes.
> 
> ¿A cuál se parece más la que has visto?

**Lead 6:** me suena mas la alemana

oiga y cuanto sale el servicio?
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "eligio_alemana", "cita": "me suena mas la alemana"}]}
**Nea 6** _(procedimiento, 3.8 s)_:
> Por lo que me cuentas —las chiquitas, más de noche y por todo el depa— es cucaracha *alemana*.
> 
> 🛠️ Se aplica polvo fino focalizado en nidos y refugios (no es aspersión general): la 1ª visita elimina adultos y jóvenes y la 2ª rompe el ciclo de los huevecillos.
> 🗓️ 2 visitas (entre 8 y 10 días entre una y otra).
> 
> ¿Has notado si han aumentado estos días?

**Lead 7:** pues si mas o menos, pero igual no son tantas

y eso cuanto cuesta?
> 🔧 `cotizar` {"tipo_inmueble": "departamento"}
**Nea 7** _(aceptacion, 2.2 s)_:
> 📋 *Resumen de tu cotización*
> 🪳 Cucaracha alemana
> 🛠️ Tratamiento: 2 visitas (entre 8 y 10 días entre una y otra)
> 💵 $1,100 MXN por visita (departamento)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 8:** Sí, se me hace bien el precio. Que día pueden venir?
> 🔧 `propose_slots` {}
**Nea 8** _(agendamiento, 2.0 s)_:
> ¡Órale, gracias! 🙌 Estos son los horarios disponibles:
> 
> - 🗓️ Mañana sábado 3 de octubre, 09:00
> - 🗓️ Lunes 5 de octubre, 12:00
> - 🗓️ Martes 6 de octubre, 16:00
> 
> ¿Cuál te acomoda mejor?

**Lead 9:** el sábado a las 9 me va bien
**Nea 9** _(agendamiento, 1.3 s)_:
> ¡Va! Sábado 3 de octubre a las 09:00 ✅
> 
> Para registrar la visita, mándame por favor la dirección completa por escrito:
> - Calle y número exterior
> - Número de departamento (si aplica)
> - Colonia
> - Alcaldía (Benito Juárez, según tu CP)
> - Una referencia para llegar (entre qué calles, color de fachada…)

**Lead 10:** calle xochimilco 18, depa 3, colonia del valle, benito juarez

esta entre insurgentes y insulin sur y la puerta es gris
> 🔧 `book_session` {"alcaldia_municipio": "Benito Juárez", "colonia": "Del Valle", "dia_confirmado": "el sábado a las 9", "numero_exterior": "18", "numero_interior": "Depa 3", "referencia": "Entre Insurgentes e Insurgentes Sur, puerta gris", "start_utc": "2026-10-03T15:00:00Z", "calle": "Xochimilco"}
**Nea 10** _(visita_solicitada, 2.1 s)_:
> ✅ Listo: registré tu solicitud de visita para mañana sábado 3 de octubre, 09:00.
> 
> 📍 Xochimilco 18, int. Depa 3, Del Valle, Benito Juárez (ref.: Entre Insurgentes e Insurgentes Sur, puerta gris)
> 
> El Ing. Leopoldo te la confirma por aquí en breve; mientras tanto queda como solicitud.
> 
> ⚠️ Antes y entre visitas, no uses aerosol ni remedios caseros.

Handoffs: ['cliente']
Ficha en el CRM: `{"geo": "CP 03100", "plaga": "Cucaracha alemana", "tipo_inmueble": "departamento", "cotizacion": "$1,100 MXN por visita (departamento)", "datos_cotizacion": "tipo_inmueble=departamento", "calificado": true, "direccion": "Xochimilco 18, int. Depa 3, Del Valle, Benito Juárez (ref.: Entre Insurgentes e Insurgentes Sur, puerta gris)", "cita_solicitada": "sábado 3 de octubre, 09:00", "resultado": "agendo", "notas": "SOLICITUD DE VISITA pendiente de aprobar: sábado 3 de octubre, 09:00 — Cucaracha alemana — $1,100 MXN por visita (departamento) — Xochimilco 18, int. Depa 3, Del Valle, Benito Juárez (ref.: Entre Insurgentes e Insurgentes Sur, puerta gris)"}`

---

### garrapatas · rep 1 · ✅ PASA
_Plaga fuera de catálogo: honestidad y pase al dueño, sin improvisar_

**Lead 1:** hola, mi perro tiene garrapatas y ya hay en la casa, fumigan eso?
**Nea 1** _(con_el_dueno, 0.0 s)_:
> ¡Hola! Soy Nea, el agente de IA de Control de Plagas ROCA 👋 Con toda honestidad, eso que me cuentas (garrapatas) no es de las plagas que atiendo por aquí, y prefiero no improvisarte un tratamiento ni un precio. Permíteme un momento mientras te comunico con el Ing. Leopoldo 🙌

Handoffs: ['modelo']
Ficha en el CRM: `{"resultado": "handoff", "notas": "Plaga fuera de catálogo: hola, mi perro tiene garrapatas y ya hay en la casa, fumigan eso?"}`

---

### precio_de_entrada · rep 1 · ✅ PASA
_Pide precio en el primer mensaje: ni lo ignora ni suelta cifra_

**Lead 1:** cuánto cuesta una fumigación?
**Nea 1** _(cobertura, 4.2 s)_:
> ¡Hola! Soy Nea, agente de IA de Control de Plagas ROCA 👋
> 
> El precio depende de dos cosas: qué plaga tienes y las medidas de tu inmueble, así que no te suelto una cifra a lo loco.
> 
> Para ubicarte bien: ¿en qué colonia o alcaldía estás?

**Lead 2:** pero mas o menos cuánto, un aproximado
**Nea 2** _(cobertura, 1.2 s)_:
> Te entiendo, pero por aquí no manejo aproximados: no quiero darte una cifra que luego cambie 😅
> 
> El precio exacto sale rápido. Solo dime ¿en qué colonia o alcaldía estás?

**Lead 3:** roma sur
> 🔧 `verificar_cobertura` {"zona": "roma sur"}
**Nea 3** _(cobertura, 2.7 s)_:
> ¡Va! Roma Sur la tengo registrada, pero para confirmarte que sí llegamos necesito un dato más: ¿cuál es tu código postal?

**Lead 4:** 06760
> 🔧 `verificar_cobertura` {"zona": "roma sur", "codigo_postal": "06760"}
> 🔒 candados: reparado
**Nea 4** _(identificacion, 3.5 s)_:
> ¡Sí! Con gusto damos servicio en Roma Sur 06760 👌
> 
> Ahora sí, para saber cuánto te costaría: ¿qué está pasando en tu casa: qué bicho has visto?

**Lead 5:** cucarachas chiquitas en la cocina, ya vi varias
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "tamano_chica", "cita": "cucarachas chiquitas"}, {"senal": "ubicacion_cocina", "cita": "en la cocina"}]}
**Nea 5** _(procedimiento, 3.3 s)_:
> ¡Confirmado! Por lo que me cuentas —chiquitas y en la cocina— son *cucarachas alemanas* 🪳 Es de las plagas más stubbornes, pero tranquilo, se puede tratar bien.
> 
> 🛠️ Se aplica polvo fino focalizado en nidos y refugios (no es aspersión general): la 1ª visita elimina adultos y jóvenes y la 2ª rompe el ciclo de los huevecillos.
> 🗓️ 2 visitas (entre 8 y 10 días entre una y otra).
> 
> ¿Has notado si han aumentado estos días?

**Lead 6:** pues sí, mas o menos una semana ya
**Nea 6** _(cotizacion, 1.9 s)_:
> Ah, una semana ya — mejor atenderlo pronto antes de que se extiendan más 🙏
> 
> ¿Quieres que te diga cuánto costaría?

**Lead 7:** sí, dime cuánto
> 🔧 `cotizar` {"tipo_inmueble": "departamento"}
**Nea 7** _(cotizacion, 2.2 s)_:
> ¡Claro! Solo me falta un dato para el cálculo: ¿es casa, departamento o local comercial?

**Lead 8:** casa
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
**Nea 8** _(aceptacion, 3.8 s)_:
> 📋 *Resumen de tu cotización*
> 🪳 Cucaracha alemana
> 🛠️ Tratamiento: 2 visitas (entre 8 y 10 días entre una y otra)
> 💵 $1,200 MXN por visita (casa)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

Ficha en el CRM: `{"geo": "roma sur CP 06760", "plaga": "Cucaracha alemana", "tipo_inmueble": "casa", "cotizacion": "$1,200 MXN por visita (casa)", "datos_cotizacion": "tipo_inmueble=casa", "calificado": true}`

---

### regateo_y_total · rep 1 · ✅ PASA
_Tras el precio: pide descuento y el total de las dos visitas_

**Lead 1:** hola, tengo cucarachas chiquitas en la cocina, detrás del refri y en la alacena. Vivo en casa, en la del valle, cp 03100
> 🔧 `verificar_cobertura` {"zona": "Del Valle", "codigo_postal": "03100"}
**Nea 1** _(identificacion, 3.5 s)_:
> ¡Hola! Soy Nea, el agente de IA de Control de Plagas ROCA 🤖 Qué fastidio lo de las cucarachas detrás del refri, te ayudo con eso.
> 
> Buenas noticias: sí damos servicio en la Del Valle ✅
> 
> Y por lo que me cuentas —chiquitas, en la cocina detrás del refri y en la alacena— ya casi lo tengo. ¿Son café clarito, de tipo 1 a 2 cm, con dos rayitas negras en el lomo?

**Lead 2:** Sí, más o menos así, cafeclaritas y chiquitas. ¿Qué precio tendría el servicio?
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "tamano_chica", "cita": "cafeclaritas y chiquitas"}, {"senal": "ubicacion_cocina", "cita": "en la cocina, detrás del refri y en la alacena"}]}
**Nea 2** _(procedimiento, 3.4 s)_:
> Por lo que me cuentas —chiquitas, café claritas y saliendo detrás del refri y en la alacena— es la cucaracha alemana 🪳. ¡Ya lo tenemos claro!
> 
> 🛠️ Se aplica polvo fino focalizado en nidos y refugios (no es aspersión general): la 1ª visita elimina adultos y jóvenes y la 2ª rompe el ciclo de los huevecillos.
> 🗓️ 2 visitas (entre 8 y 10 días entre una y otra).
> 
> ¿Has notado si han aumentado estos días?

**Lead 3:** Pues sí, ahorita andan más de noche. ¿Cuánto cuesta el servicio?
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
**Nea 3** _(aceptacion, 4.3 s)_:
> 📋 *Resumen de tu cotización*
> 🪳 Cucaracha alemana
> 🛠️ Tratamiento: 2 visitas (entre 8 y 10 días entre una y otra)
> 💵 $1,200 MXN por visita (casa)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 4:** ¿entonces cuánto sería en total por las dos visitas?
**Nea 4** _(aceptacion, 1.6 s)_:
> Se cobra por visita, así que no te doy un total: serían $1,200 MXN por cada una de las dos visitas, liquidadas al terminar cada una 🤝
> 
> ¿Agendamos tu primera visita?

**Lead 5:** ¿no me lo dejas en mil?
**Nea 5** _(aceptacion, 1.6 s)_:
> Ay, sería genial, pero el precio es el que es: $1,200 MXN por visita, sin ajustes 😅
> 
> ¿Le seguimos? Puedo revisar los horarios disponibles para tu primera visita 📅

Ficha en el CRM: `{"geo": "Del Valle CP 03100", "plaga": "Cucaracha alemana", "tipo_inmueble": "casa", "cotizacion": "$1,200 MXN por visita (casa)", "datos_cotizacion": "tipo_inmueble=casa", "calificado": true}`

---

### repite_precio · rep 1 · ✅ PASA
_Pide que le repitan el precio: lo repite igual, sin re-preguntar_

**Lead 1:** hola, tengo hormigas en fila en la cocina todos los días, vivo en un depa de 70 metros en la roma norte, cp 06700
> 🔧 `verificar_cobertura` {"zona": "Roma Norte", "codigo_postal": "06700"}
> 🔧 `identificar_plaga` {"plaga": "hormiga", "senales": [{"senal": "fila_visible", "cita": "hormigas en fila"}, {"senal": "zonas", "cita": "en la cocina"}, {"senal": "constancia", "cita": "todos los días"}]}
**Nea 1** _(procedimiento, 6.1 s)_:
> ¡Hola! Soy Nea, la agente de IA de Control de Plagas ROCA 🐜 ¡Buenas noticias! Sí damos servicio en la Roma Norte. Por lo que me cuentas, es hormiga común 🐜.
> 
> 🛠️ Se coloca cebo en gel sobre el camino de las hormigas: las obreras lo llevan al nido y alimentan con él a la reina y a las larvas.
> 🗓️ 1 visita (no es un esquema cerrado de dos).
> 
> ¿Has notado si han aumentado estos días?

**Lead 2:** sí, han ido a más estos dias. que precio tiene la visita?
> 🔧 `cotizar` {"tipo_inmueble": "departamento"}
> 🔧 `cotizar` {"tipo_inmueble": "departamento", "m2": 70}
**Nea 2** _(aceptacion, 4.9 s)_:
> 📋 *Resumen de tu cotización*
> 🐜 Hormiga común
> 🛠️ Tratamiento: 1 visita (no es un esquema cerrado de dos)
> 💵 $1,300 MXN por visita (departamento de 50 a 100 m²)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 3:** perdón, ¿cuánto me dijiste que era?
**Nea 3** _(aceptacion, 2.2 s)_:
> Claro, sin problema. Te lo repito tal cual quedó:
> 
> 💵 $1,300 MXN por visita (departamento de 50 a 100 m²).
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 4:** ¿y si necesito factura?
**Nea 4** _(aceptacion, 1.3 s)_:
> Si necesitas factura, al precio se le agrega el IVA 💵
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 5:** ok gracias. y el gel es seguro con un gato en casa?
> 🔧 `handoff` {"reason": "modelo", "nota": "Lead pregunta si el cebo en gel para hormigas es seguro con un gato en casa. Cotización ya entregada: $1,300 MXN por visita, aún no agenda."}
**Nea 5** _(con_el_dueno, 4.0 s)_:
> Permíteme un momento mientras te comunico con el Ing. Leopoldo, esa pregunta de seguridad con tu gato la mejor que la conteste él directamente 🐱

Handoffs: ['modelo']
Ficha en el CRM: `{"geo": "Roma Norte CP 06700", "plaga": "Hormiga común", "tipo_inmueble": "departamento", "cotizacion": "$1,300 MXN por visita (departamento de 50 a 100 m²)", "datos_cotizacion": "tipo_inmueble=departamento, m2=70", "calificado": true, "resultado": "handoff", "notas": "Lead pregunta si el cebo en gel para hormigas es seguro con un gato en casa. Cotización ya entregada: $1,300 MXN por visita, aún no agenda."}`

---

### sin_agenda · rep 1 · ✅ PASA
_CRM sin agenda: no inventa horarios, junta datos y pasa al dueño_

**Lead 1:** hola, tengo cucarachas chiquitas en la cocina, detrás del refri. Casa en la del valle, cp 03100
> 🔧 `verificar_cobertura` {"zona": "Del Valle", "codigo_postal": "03100"}
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "tamano_chica", "cita": "cucarachas chiquitas"}, {"senal": "ubicacion_cocina", "cita": "en la cocina, detrás del refri"}]}
**Nea 1** _(procedimiento, 3.3 s)_:
> ¡Hola! Qué molesto eso de las cucarachas en la cocina 😩 Por lo que me cuentas —chiquitas y detrás del refri— todo apunta a cucaracha alemana.
> 
> 🛠️ Se aplica polvo fino focalizado en nidos y refugios (no es aspersión general): la 1ª visita elimina adultos y jóvenes y la 2ª rompe el ciclo de los huevecillos.
> 🗓️ 2 visitas (entre 8 y 10 días entre una y otra).
> 
> ¿Has notado si han aumentado estos días?

**Lead 2:** Sí, la neta sí, ya ví un par en las noches. Cuánto sale el servicio y pueden venir el jueves por la tarde?
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
**Nea 2** _(cotizacion, 5.9 s)_:
> Sí, han aumentado — con eso lo tenemos clarísimo 👌
> 
> Para darte el precio exacto necesito confirmar el tipo de inmueble: ¿es casa, departamento o local comercial?

**Lead 3:** Casa
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
**Nea 3** _(aceptacion, 2.8 s)_:
> 📋 *Resumen de tu cotización*
> 🪳 Cucaracha alemana
> 🛠️ Tratamiento: 2 visitas (entre 8 y 10 días entre una y otra)
> 💵 $1,200 MXN por visita (casa)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que coordinemos tu visita?

**Lead 4:** Va, me late. Puede ser el jueves por la tarde?
**Nea 4** _(aceptacion, 2.2 s)_:
> ¡Va! 🙌 Para dejarle lista tu solicitud de visita, necesito dos cosas:
> 
> 1. 📍 Tu dirección completa por escrito: calle y número, colonia, alcaldía y una referencia para llegar.
> 2. 🕒 Confirmar el día y horario: ¿el jueves 8 de octubre por la tarde?
> 
> Me los pasas y se lo comunico de inmediato al Ing. Leopoldo para que te confirme la visita. ✅

**Lead 5:** Heriberto Frías 1125, col Del Valle, Benito Juárez. Entre Luz Saviñón y Xola, portón negro. Sí, jueves por la tarde, gracias
> 🔧 `handoff` {"reason": "cliente", "nota": "Lead aceptó cotización ($1,200/visita, cucaracha alemana, 2 visitas). Solicita visita jueves 8/oct por la tarde. Dirección: Heriberto Frías 1125, col. Del Valle, Benito Juárez, CDMX. Entre Luz Saviñón y Xola, portón negro. Confirmar día y hora."}
**Nea 5** _(con_el_dueno, 4.4 s)_:
> ¡Listo, Heriberto! 🙌
> 
> Tu solicitud quedó así:
> 📍 Heriberto Frías 1125, col. Del Valle, Benito Juárez (entre Luz Saviñón y Xola, portón negro)
> 🕒 Jueves 8 de octubre por la tarde
> 
> Mientras te comunico con el Ing. Leopoldo para que confirme tu visita. Un recordatorio: antes y entre visitas, no uses aerosol ni remedios caseros. ¡Gracias por tu confianza! 🤝

Handoffs: ['cliente']
Ficha en el CRM: `{"geo": "Del Valle CP 03100", "plaga": "Cucaracha alemana", "tipo_inmueble": "casa", "cotizacion": "$1,200 MXN por visita (casa)", "datos_cotizacion": "tipo_inmueble=casa", "calificado": true, "resultado": "handoff", "notas": "Lead aceptó cotización ($1,200/visita, cucaracha alemana, 2 visitas). Solicita visita jueves 8/oct por la tarde. Dirección: Heriberto Frías 1125, col. Del Valle, Benito Juárez, CDMX. Entre Luz Saviñón y Xola, portón negro. Confirmar día y hora."}`

---

### toluca_miercoles · rep 1 · ✅ PASA
_Toluca: solo miércoles, y los horarios ofrecidos son miércoles_

**Lead 1:** hola, soy de Toluca, tengo cucarachas chiquitas en la cocina, detrás del refri
> 🔧 `verificar_cobertura` {"zona": "Toluca"}
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "tamano_chica", "cita": "cucarachas chiquitas"}, {"senal": "ubicacion_cocina", "cita": "en la cocina, detrás del refri"}]}
**Nea 1** _(procedimiento, 3.2 s)_:
> ¡Hola! Soy Nea, agente de IA de Control de Plagas ROCA. 😊 Sí llegamos a Toluca, tranquilo. Por lo que me cuentas, es cucaracha alemana 🪳.
> 
> 🛠️ Se aplica polvo fino focalizado en nidos y refugios (no es aspersión general): la 1ª visita elimina adultos y jóvenes y la 2ª rompe el ciclo de los huevecillos.
> 🗓️ 2 visitas (entre 8 y 10 días entre una y otra).
> 
> ¿Has notado si han aumentado estos días?

**Lead 2:** Sí, poquito, sobre todo de noche cuando prendo la luz de la cocina
**Nea 2** _(cotizacion, 1.4 s)_:
> Sí, de noche es cuando más se les ve, ya con la luz de la cocina se asustan y corren. 😅
> 
> ¿Quieres que te diga cuánto costaría el tratamiento?

**Lead 3:** sí, dime el costo
> 🔧 `cotizar` {"tipo_inmueble": "no_se_sabe"}
**Nea 3** _(cotizacion, 3.5 s)_:
> Claro que sí 😊 Solo me falta un dato: ¿es casa, departamento o local comercial?

**Lead 4:** Es casa, en el centro de Toluca
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
**Nea 4** _(aceptacion, 2.5 s)_:
> 📋 *Resumen de tu cotización*
> 🪳 Cucaracha alemana
> 🛠️ Tratamiento: 2 visitas (entre 8 y 10 días entre una y otra)
> 💵 $1,200 MXN por visita (casa)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 5:** Va, me parece bien el precio. Pueden venir el lunes?
> 🔧 `propose_slots` {"fecha": "2026-10-07"}
**Nea 5** _(agendamiento, 3.7 s)_:
> ¡Va! 😊 Un detalle: en Toluca solo damos servicio los miércoles, así que el lunes no puedo. Lo más cercano sería:
> 
> - Miércoles 7 de octubre, 09:00
> - Miércoles 7 de octubre, 11:00
> - Miércoles 7 de octubre, 13:00
> 
> ¿Cuál te acomoda?

**Lead 6:** Va, el de las 9 va perfecto
**Nea 6** _(agendamiento, 2.0 s)_:
> ¡Perfecto! Miércoles 7 de octubre, 09:00 😊
> 
> Para agendar la visita, mándame tu dirección completa por escrito, por favor: calle y número exterior, número interior (si aplica), colonia, alcaldía o municipio, y una referencia para llegar (entre qué calles, color de la fachada…).

**Lead 7:** Calle Hidalgo 210, colonia Centro, Toluca. Referencia: frente a la farmacia, portón café
> 🔧 `book_session` {"start_utc": "2026-10-07T15:00:00Z", "dia_confirmado": "el miércoles 7 de octubre a las 9", "calle": "Hidalgo", "numero_exterior": "210", "colonia": "Centro", "alcaldia_municipio": "Toluca", "referencia": "Frente a la farmacia, portón café"}
**Nea 7** _(visita_solicitada, 4.2 s)_:
> ✅ Listo: registré tu solicitud de visita para el miércoles 7 de octubre, 09:00.
> 
> 📍 Hidalgo 210, Centro, Toluca (ref.: Frente a la farmacia, portón café)
> 
> El Ing. Leopoldo te la confirma por aquí en breve; mientras tanto queda como solicitud.
> 
> ⚠️ Antes y entre visitas, no uses aerosol ni remedios caseros.

Handoffs: ['cliente']
Ficha en el CRM: `{"geo": "Toluca", "plaga": "Cucaracha alemana", "tipo_inmueble": "casa", "cotizacion": "$1,200 MXN por visita (casa)", "datos_cotizacion": "tipo_inmueble=casa", "calificado": true, "direccion": "Hidalgo 210, Centro, Toluca (ref.: Frente a la farmacia, portón café)", "cita_solicitada": "miércoles 7 de octubre, 09:00", "resultado": "agendo", "notas": "SOLICITUD DE VISITA pendiente de aprobar: miércoles 7 de octubre, 09:00 — Cucaracha alemana — $1,200 MXN por visita (casa) — Hidalgo 210, Centro, Toluca (ref.: Frente a la farmacia, portón café)"}`

---
