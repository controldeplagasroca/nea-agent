### dudas_de_seguridad · rep 1 · ✅ PASA
_«¿No es tóxico? ¿Cuándo podemos entrar?»: contesta solo lo aprobado_

**Lead 1:** hola, tengo cucarachas chiquitas en la cocina, detrás del refri. Casa en la del valle, cp 03100
> 🔧 `verificar_cobertura` {"zona": "Del Valle", "codigo_postal": "03100"}
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "tamano_chica", "cita": "cucarachas chiquitas"}, {"senal": "ubicacion_cocina", "cita": "en la cocina, detrás del refri"}]}
**Nea 1** _(procedimiento, 3.0 s)_:
> ¡Hola! Soy Nea, agente de IA de Control de Plagas ROCA. 😊 Buenas noticias: sí damos servicio en la Del Valle (CP 03100). Por lo que me cuentas, es cucaracha alemana 🪳.
> 
> 💚 No te preocupes: no es por falta de higiene. Es un insecto que suele entrar a casa sin que nos demos cuenta, y tiene solución.
> 🛠️ Se aplica polvo fino focalizado en nidos y refugios (no es aspersión general): la 1ª visita elimina adultos y jóvenes y la 2ª rompe el ciclo de los huevecillos.
> 🗓️ 2 visitas (entre 8 y 10 días entre una y otra).
> 
> ¿Has notado si han aumentado estos días?

**Lead 2:** oye pero eso que aplican no es tóxico? no nos hace daño?
**Nea 2** _(cotizacion, 0.8 s)_:
> Los productos que se usan no ponen en riesgo la salud de quienes viven en el inmueble, así que puedes quedarte tranquilo 😊
> 
> ¿Quieres que te diga cuánto costaría el tratamiento para tu casa?

**Lead 3:** y en cuánto tiempo podemos volver a entrar a la casa?
> 🔒 candados: reparado
**Nea 3** _(cotizacion, 0.6 s)_:
> Se puede volver a entrar al área tratada en poco tiempo: de 15 a 20 minutos después de la aplicación 😊

**Lead 4:** y sí acaba con ellas o luego regresan?
**Nea 4** _(cotizacion, 0.8 s)_:
> Sí, el tratamiento sí es efectivo contra la plaga: la primera visita elimina adultos y jóvenes, y la segunda rompe el ciclo antes de que eclosionen los huevecillos. 👍
> 
> Un tip: mientras tanto, no uses aerosol ni remedios caseros, porque dificultan el tratamiento.
> 
> ¿Te digo cuánto costaría?

**Lead 5:** sí dime
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
**Nea 5** _(aceptacion, 1.2 s)_:
> 📋 *Resumen de tu cotización*
> 🪳 Cucaracha alemana
> 🛠️ Tratamiento: 2 visitas (entre 8 y 10 días entre una y otra)
> 💵 $1,200 MXN por visita (casa)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 6:** van a ser $2,400 en total entonces? déjame lo pienso y te aviso
**Nea 6** _(aceptacion, 1.0 s)_:
> El precio es por visita y se liquida al término de cada una; no se maneja un total por adelantado.
> 
> Sin prisa, tómate tu tiempo 😊 Avísame cuando quieras y agendamos tu primera visita.

Ficha en el CRM: `{"geo": "Del Valle CP 03100", "plaga": "Cucaracha alemana", "tipo_inmueble": "casa", "cotizacion": "$1,200 MXN por visita (casa)", "datos_cotizacion": "tipo_inmueble=casa", "calificado": true}`

---

### dudas_de_seguridad · rep 2 · ✅ PASA
_«¿No es tóxico? ¿Cuándo podemos entrar?»: contesta solo lo aprobado_

**Lead 1:** hola, tengo cucarachas chiquitas en la cocina, detrás del refri. Casa en la del valle, cp 03100
> 🔧 `verificar_cobertura` {"zona": "Del Valle", "codigo_postal": "03100"}
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "tamano_chica", "cita": "cucarachas chiquitas"}, {"senal": "ubicacion_cocina", "cita": "en la cocina, detrás del refri"}]}
**Nea 1** _(procedimiento, 1.8 s)_:
> ¡Hola! Soy Nea, agente de IA de Control de Plagas ROCA 👋 Por lo que me cuentas —chiquitas y detrás del refri— sí es la cucaracha alemana, y buena noticia: sí damos servicio en la Del Valle.
> 
> 💚 No te preocupes: no es por falta de higiene. Es un insecto que suele entrar a casa sin que nos demos cuenta, y tiene solución.
> 🛠️ Se aplica polvo fino focalizado en nidos y refugios (no es aspersión general): la 1ª visita elimina adultos y jóvenes y la 2ª rompe el ciclo de los huevecillos.
> 🗓️ 2 visitas (entre 8 y 10 días entre una y otra).
> 
> ¿Has notado si han aumentado estos días?

**Lead 2:** oye pero eso que aplican no es tóxico? no nos hace daño?
**Nea 2** _(cotizacion, 1.0 s)_:
> Tranquilo: los productos que se usan no ponen en riesgo la salud de quienes viven en la casa. Y se puede volver a entrar al área tratada en poco tiempo, de 15 a 20 minutos después de la aplicación. 
> 
> Si alguien en tu familia tiene un caso particular (embarazo, bebés, alergias), la indicación exacta la confirma el Ing. Leopoldo y con gusto lo puedes platicar con él. 😊
> 
> Ahora sí, ¿quieres que te diga cuánto costaría el tratamiento?

**Lead 3:** y en cuánto tiempo podemos volver a entrar a la casa?
**Nea 3** _(cotizacion, 0.7 s)_:
> De 15 a 20 minutos después de la aplicación ya se puede volver a entrar. 😊
> 
> ¿Quieres que te diga cuánto costaría el tratamiento?

**Lead 4:** y sí acaba con ellas o luego regresan?
**Nea 4** _(cotizacion, 0.8 s)_:
> Sí, el tratamiento sí es efectivo contra la cucaracha alemana: la 1ª visita elimina adultos y jóvenes, y la 2ª rompe el ciclo antes de que eclosionen los huevecillos, que es justo lo que evita que regresen. 😊
> 
> Un tip: mientras tanto, no uses aerosol ni remedios caseros, porque estorban al tratamiento.
> 
> ¿Te digo cuánto costaría?

**Lead 5:** sí dime, cuánto sale
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
**Nea 5** _(aceptacion, 3.7 s)_:
> 📋 *Resumen de tu cotización*
> 🪳 Cucaracha alemana
> 🛠️ Tratamiento: 2 visitas (entre 8 y 10 días entre una y otra)
> 💵 $1,200 MXN por visita (casa)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 6:** vale, lo voy a pensar y te aviso. gracias
**Nea 6** _(aceptacion, 1.0 s)_:
> ¡Claro, tómalo con calma! 😊 Queda en $1,200 MXN por visita y son 2 visitas en total para tu casa de la Del Valle.
> 
> Si decides avanzar o te surge cualquier otra duda, me escribes aquí mismo. ¡Que tengas bonito día! 👋

Ficha en el CRM: `{"geo": "Del Valle CP 03100", "plaga": "Cucaracha alemana", "tipo_inmueble": "casa", "cotizacion": "$1,200 MXN por visita (casa)", "datos_cotizacion": "tipo_inmueble=casa", "calificado": true}`

---

### dudas_de_seguridad · rep 3 · ✅ PASA
_«¿No es tóxico? ¿Cuándo podemos entrar?»: contesta solo lo aprobado_

**Lead 1:** hola, tengo cucarachas chiquitas en la cocina, detrás del refri. Casa en la del valle, cp 03100
> 🔧 `verificar_cobertura` {"zona": "Del Valle", "codigo_postal": "03100"}
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "tamano_chica", "cita": "cucarachas chiquitas"}, {"senal": "ubicacion_cocina", "cita": "en la cocina, detrás del refri"}]}
**Nea 1** _(procedimiento, 2.0 s)_:
> ¡Hola! Soy Nea, agente de IA de Control de Plagas ROCA 🙌 Qué fastidio eso de las cucarachas detrás del refri...
> 
> 💚 No te preocupes: no es por falta de higiene. Es un insecto que suele entrar a casa sin que nos demos cuenta, y tiene solución.
> 🛠️ Se aplica polvo fino focalizado en nidos y refugios (no es aspersión general): la 1ª visita elimina adultos y jóvenes y la 2ª rompe el ciclo de los huevecillos.
> 🗓️ 2 visitas (entre 8 y 10 días entre una y otra).
> 
> ¿Has notado si han aumentado estos días?

**Lead 2:** oye pero eso que aplican no es tóxico? no nos hace daño?
**Nea 2** _(cotizacion, 0.8 s)_:
> Tranquilo: los productos que se usan no ponen en riesgo la salud de quienes viven en el inmueble 👍
> 
> Y ya que estamos, ¿quieres que te diga cuánto costaría el tratamiento?

**Lead 3:** y en cuánto tiempo podemos volver a entrar a la casa?
**Nea 3** _(cotizacion, 1.3 s)_:
> Se puede volver a entrar al área tratada en poco tiempo: de 15 a 20 minutos después de la aplicación 👍
> 
> ¿Quieres que te diga cuánto costaría el tratamiento?

**Lead 4:** y sí acaba con ellas o luego regresan?
**Nea 4** _(cotizacion, 0.8 s)_:
> El tratamiento sí es efectivo contra las cucarachas 🙌 La primera visita elimina adultos y jóvenes, y la segunda rompe el ciclo antes de que nazcan las nuevas.
> 
> ¿Te digo cuánto costaría?

**Lead 5:** sí, dime el precio
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
**Nea 5** _(aceptacion, 1.7 s)_:
> 📋 *Resumen de tu cotización*
> 🪳 Cucaracha alemana
> 🛠️ Tratamiento: 2 visitas (entre 8 y 10 días entre una y otra)
> 💵 $1,200 MXN por visita (casa)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 6:** ok gracias, lo voy a pensar y te aviso
**Nea 6** _(aceptacion, 2.0 s)_:
> ¡Claro, sin prisa! Queda en $1,200 MXN por visita y aquí ando cuando quieras agendar 👋
> 
> Un tip mientras tanto: no uses aerosol ni remedios caseros antes de la visita, porque se incorporan al tratamiento 😊

Ficha en el CRM: `{"geo": "Del Valle CP 03100", "plaga": "Cucaracha alemana", "tipo_inmueble": "casa", "cotizacion": "$1,200 MXN por visita (casa)", "datos_cotizacion": "tipo_inmueble=casa", "calificado": true}`

---

### ejemplo_del_dueno · rep 1 · ✅ PASA
_«No conozco de cucarachas, pero son chiquitas»: lo lleva de la mano, sin interrogarlo_

**Lead 1:** hola, tengo cucarachas en mi casa, estoy en la del valle 03100
> 🔧 `verificar_cobertura` {"zona": "Del Valle", "codigo_postal": "03100"}
**Nea 1** _(identificacion, 6.9 s)_:
> ¡Hola! Soy Nea, agente de IA de Control de Plagas ROCA 🙌 Qué molesto eso de las cucarachas, pero buena noticia: sí damos servicio en la Del Valle.
> 
> Para recomendarte el tratamiento adecuado, ayúdame con un dato: ¿son chicas (como de 1 a 2 cm, café claritas) o grandes (de 4 a 5 cm, café oscuro)?

**Lead 2:** no conozco de cucarachas la verdad, pero las que he visto son chiquitas
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "tamano_chica", "cita": "las que he visto son chiquitas"}]}
**Nea 2** _(identificacion, 1.9 s)_:
> ¡Tranquilo, con eso me va orientando! 😊 ¿En qué parte las ves más: en la cocina (detrás del refri, gabinetes o la tarja) o cerca de coladeras, drenajes o el patio?

**Lead 3:** en la cocina, atrás del refri y abajo de la licuadora, y también las he visto en el baño
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "tamano_chica", "cita": "las que he visto son chiquitas"}, {"senal": "ubicacion_cocina", "cita": "en la cocina, atrás del refri y abajo de la licuadora"}, {"senal": "ubicacion_bano", "cita": "también las he visto en el baño"}]}
**Nea 3** _(procedimiento, 2.2 s)_:
> Por lo que me cuentas —chiquitas y detrás del refri y la licuadora— son cucarachas alemanas, la típica que se mete en la cocina y el baño. Sé qué a mal traer traen estas cositas 😅.
> 
> 💚 No te preocupes: no es por falta de higiene. Es un insecto que suele entrar a casa sin que nos demos cuenta, y tiene solución.
> 🛠️ Se aplica polvo fino focalizado en nidos y refugios (no es aspersión general): la 1ª visita elimina adultos y jóvenes y la 2ª rompe el ciclo de los huevecillos.
> 🗓️ 2 visitas (entre 8 y 10 días entre una y otra).
> 
> ¿Has notado si han aumentado estos días?

**Lead 4:** pues sí, ahora las veo seguido, antes nada más de vez en cuando
**Nea 4** _(cotizacion, 1.4 s)_:
> Sí, cuando se ven seguido ya conviene atacarlas pronto, antes de que sigan multiplicándose.
> 
> ¿Quieres que te diga cuánto costaría el tratamiento?

**Lead 5:** sí, dime cuánto es, es casa de un piso
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
**Nea 5** _(aceptacion, 2.5 s)_:
> 📋 *Resumen de tu cotización*
> 🪳 Cucaracha alemana
> 🛠️ Tratamiento: 2 visitas (entre 8 y 10 días entre una y otra)
> 💵 $1,200 MXN por visita (casa)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 6:** muchas gracias, lo voy a pensar y si me decido te marco
**Nea 6** _(aceptacion, 1.8 s)_:
> ¡Claro, con gusto! Tómate tu tiempo 😊 Aquí queda todo: cucaracha alemana, tratamiento de 2 visitas, $1,200 por visita.
> 
> Cuando te decidas me escribes y lo agendamos. ¡Que tengas bonito día! 🙌

Ficha en el CRM: `{"geo": "Del Valle CP 03100", "plaga": "Cucaracha alemana", "tipo_inmueble": "casa", "cotizacion": "$1,200 MXN por visita (casa)", "datos_cotizacion": "tipo_inmueble=casa", "calificado": true}`

---

### ejemplo_del_dueno · rep 2 · ✅ PASA
_«No conozco de cucarachas, pero son chiquitas»: lo lleva de la mano, sin interrogarlo_

**Lead 1:** hola, tengo cucarachas en mi casa, estoy en la del valle 03100
> 🔧 `verificar_cobertura` {"zona": "Del Valle", "codigo_postal": "03100"}
**Nea 1** _(identificacion, 6.5 s)_:
> ¡Hola! Soy Nea, la agente de IA de Control de Plagas ROCA 🙌 Y sí, buenas noticias: sí damos servicio en la Del Valle.
> 
> Para ayudarte bien con esas cucarachas, cuéntame: ¿son chicas (de 1 a 2 cm, café claro) o grandes (de 4 a 5 cm, las que a veces vuelan)?

**Lead 2:** no conozco de cucarachas la verdad, pero las que he visto son chiquitas
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "tamano_chica", "cita": "las que he visto son chiquitas"}]}
**Nea 2** _(identificacion, 1.3 s)_:
> ¡Va, eso ya ayuda! 👍 Y tranquilo, para eso estoy.
> 
> ¿En qué parte las ves más: en la cocina (detrás del refri, gabinetes, cerca de la tarja) o más bien cerca de coladeras, drenajes o el patio?

**Lead 3:** en la cocina, atrás del refri y abajo de la licuadora, y también las he visto en el baño
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "tamano_chica", "cita": "las que he visto son chiquitas"}, {"senal": "ubicacion_cocina", "cita": "en la cocina, atrás del refri y abajo de la licuadora"}, {"senal": "ubicacion_bano", "cita": "también las he visto en el baño"}]}
**Nea 3** _(procedimiento, 1.8 s)_:
> Por lo que me cuentas —chiquitas, atrás del refri y de la licuadora en la cocina— es la cucaracha alemana 🪳 Y te entiendo, qué fastidio andar viéndolas en la cocina.
> 
> 💚 No te preocupes: no es por falta de higiene. Es un insecto que suele entrar a casa sin que nos demos cuenta, y tiene solución.
> 🛠️ Se aplica polvo fino focalizado en nidos y refugios (no es aspersión general): la 1ª visita elimina adultos y jóvenes y la 2ª rompe el ciclo de los huevecillos.
> 🗓️ 2 visitas (entre 8 y 10 días entre una y otra).
> 
> ¿Has notado si han aumentado estos días?

**Lead 4:** pues sí, antes eran menos, ahorita ya salen más seguido sobre todo en la noche
**Nea 4** _(cotizacion, 0.9 s)_:
> Se está propagando, mejor atenderlo pronto 💪 ¿Quieres que te diga cuánto costaría el tratamiento?

**Lead 5:** sí, dimesí porfas, dime el costo
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
**Nea 5** _(cotizacion, 1.8 s)_:
> ¡Claro que sí! Solo me falta un dato para dártelo: ¿es casa, departamento o local comercial?

**Lead 6:** es una casa
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
**Nea 6** _(aceptacion, 1.7 s)_:
> 📋 *Resumen de tu cotización*
> 🪳 Cucaracha alemana
> 🛠️ Tratamiento: 2 visitas (entre 8 y 10 días entre una y otra)
> 💵 $1,200 MXN por visita (casa)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 7:** gracias, lo voy a pensar y te aviso 👍
**Nea 7** _(aceptacion, 0.9 s)_:
> ¡Va, sin prisa! 😊 Aquí quedo para cuando decidas. Que tengas buen día 👋

Ficha en el CRM: `{"geo": "Del Valle CP 03100", "plaga": "Cucaracha alemana", "tipo_inmueble": "casa", "cotizacion": "$1,200 MXN por visita (casa)", "datos_cotizacion": "tipo_inmueble=casa", "calificado": true}`

---

### ejemplo_del_dueno · rep 3 · ✅ PASA
_«No conozco de cucarachas, pero son chiquitas»: lo lleva de la mano, sin interrogarlo_

**Lead 1:** hola, tengo cucarachas en mi casa, estoy en la del valle 03100
> 🔧 `verificar_cobertura` {"zona": "Del Valle", "codigo_postal": "03100"}
> 🔒 candados: reparado
**Nea 1** _(identificacion, 5.9 s)_:
> ¡Hola! Soy Nea, el agente de IA de Control de Plagas ROCA 👋 Qué fastidio lo de las cucarachas, pero vamos a resolverlo.
> 
> Buena noticia: sí damos servicio en la Del Valle 🙂
> 
> Para confirmar el tratamiento correcto, cuéntame: ¿son chicas (de 1 a 2 cm) o grandes (de 4 a 5 cm): y dónde las ves más, en la cocina o cerca de drenajes y coladeras?

**Lead 2:** no conozco de cucarachas la verdad, pero las que he visto son chiquitas
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "tamano_chica", "cita": "las que he visto son chiquitas"}]}
**Nea 2** _(identificacion, 1.8 s)_:
> Tranquilo, con eso ya me voy ubicando 😄
> 
> ¿En qué parte las ves más: en la cocina (detrás del refri, gabinetes o la tarja) o cerca de coladeras, drenajes o el patio?

**Lead 3:** en la cocina, atrás del refri y abajo de la licuadora, y también las he visto en el baño
> 🔧 `identificar_plaga` {"plaga": "cucaracha", "senales": [{"senal": "tamano_chica", "cita": "las que he visto son chiquitas"}, {"senal": "ubicacion_cocina", "cita": "en la cocina, atrás del refri y abajo de la licuadora"}, {"senal": "ubicacion_bano", "cita": "también las he visto en el baño"}]}
**Nea 3** _(procedimiento, 2.1 s)_:
> Por lo que me cuentas —chiquitas, detrás del refri y de la licuadora— ya tengo el diagnóstico: son cucarachas alemanas 🪳
> 
> 💚 No te preocupes: no es por falta de higiene. Es un insecto que suele entrar a casa sin que nos demos cuenta, y tiene solución.
> 🛠️ Se aplica polvo fino focalizado en nidos y refugios (no es aspersión general): la 1ª visita elimina adultos y jóvenes y la 2ª rompe el ciclo de los huevecillos.
> 🗓️ 2 visitas (entre 8 y 10 días entre una y otra).
> 
> ¿Has notado si han aumentado estos días?

**Lead 4:** pos si, de repente veo mas de una y ya me espanté
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
> 🔒 candados: reparado
**Nea 4** _(cotizacion, 1.7 s)_:
> Sí, con esa plaga conviene atacarla rápido 💪
> 
>  Solo dime: ¿tu casa es casa, departamento o local comercial?

**Lead 5:** casa
> 🔧 `cotizar` {"tipo_inmueble": "casa"}
**Nea 5** _(aceptacion, 1.7 s)_:
> 📋 *Resumen de tu cotización*
> 🪳 Cucaracha alemana
> 🛠️ Tratamiento: 2 visitas (entre 8 y 10 días entre una y otra)
> 💵 $1,200 MXN por visita (casa)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 6:** ya vi los precios, gracias. déjame pensarlo y te marco
**Nea 6** _(aceptacion, 2.4 s)_:
> ¡Va, sin prisa! 😊 Aquí queda todo: cucaracha alemana en tu casa, tratamiento de 2 visitas y $1,200 por visita (se liquida al término de cada una).
> 
> Cuando te animes, márcanos y agendamos tu primera visita. ¡Que tengas bonito día! 🙌

Ficha en el CRM: `{"geo": "Del Valle CP 03100", "plaga": "Cucaracha alemana", "tipo_inmueble": "casa", "cotizacion": "$1,200 MXN por visita (casa)", "datos_cotizacion": "tipo_inmueble=casa", "calificado": true}`

---

### garantia_lead_nuevo · rep 1 · ✅ PASA
_«¿Tiene garantía?» de un lead nuevo: no inventa una, lo remite al dueño_

**Lead 1:** hola, tengo hormigas en fila en la cocina todos los días, vivo en un depa de 70 metros en la roma norte, cp 06700
> 🔧 `verificar_cobertura` {"zona": "Roma Norte", "codigo_postal": "06700"}
**Nea 1** _(identificacion, 1.8 s)_:
> ¡Hola! Soy Nea, la agente de IA de Control de Plagas ROCA 🙌
> 
> Sí damos servicio en la Roma Norte, perfecto. Y qué fastidio eso de las hormigas en fila diarias… a ver, ¿ya identificaste por dónde entran a tu depa?

**Lead 2:** y el servicio tiene garantía? de cuánto tiempo?
> 🔧 `identificar_plaga` {"plaga": "hormiga", "senales": [{"senal": "fila_visible", "cita": "hormigas en fila en la cocina"}, {"senal": "constancia", "cita": "todos los días"}, {"senal": "zonas", "cita": "en la cocina"}]}
**Nea 2** _(procedimiento, 3.0 s)_:
> ¡Ya lo tengo! Por lo que me cuentas —hormigas en fila en la cocina, todos los días— se trata de la hormiga común 🐜 Sobre la garantía: ese punto lo define directamente el Ing.
> 
> 🛠️ Se coloca cebo en gel sobre el camino de las hormigas: las obreras lo llevan al nido y alimentan con él a la reina y a las larvas.
> 🗓️ 1 visita (no es un esquema cerrado de dos).
> 
> ¿Has notado si han aumentado estos días?

**Lead 3:** eso me lo pasan a mi? o ustedes manejan eso
**Nea 3** _(cotizacion, 2.2 s)_:
> ElIng. Leopoldo es quien te dice los detalles de garantía para tu caso 😊 Si quieres, en cuanto cerremos tu cotización lo ponemos en contacto para que te lo confirme él.
> 
> Por cierto, que sea depa de 70 m² ya me sirve para calcular… ¿quieres que te diga cuánto costaría el tratamiento?

**Lead 4:** sí, dime el costo
> 🔧 `cotizar` {"tipo_inmueble": "departamento"}
> 🔧 `cotizar` {"tipo_inmueble": "departamento", "m2": 70}
**Nea 4** _(aceptacion, 3.4 s)_:
> 📋 *Resumen de tu cotización*
> 🐜 Hormiga común
> 🛠️ Tratamiento: 1 visita (no es un esquema cerrado de dos)
> 💵 $1,300 MXN por visita (departamento de 50 a 100 m²)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 5:** y si regresa la plaga después, la repetición va incluida o se paga otra vez?
**Nea 5** _(aceptacion, 1.8 s)_:
> Ese punto lo define directamente el Ing. Leopoldo, porque depende del seguimiento que el tratamiento considere en tu caso 😊
> 
> Lo que sí te puedo decir es que el tratamiento es de 1 visita, y si quieres la letra chica sobre repeticiones, te comunico con él para que te lo confirme.
> 
> ¿Te funciona así, o preferimos primero dejar agendada tu visita?

**Lead 6:** ok está bien el precio, quiero agendar
> 🔧 `propose_slots` {"fecha": "2026-10-03"}
**Nea 6** _(agendamiento, 1.3 s)_:
> ¡Órale, gracias! 🙌 Para mañana sábado 3 de octubre me quedan estas horas:
> 
> - 09:00
> - 11:00
> - 13:00
> 
> ¿Cuál te acomoda mejor?

**Lead 7:** la de 11
**Nea 7** _(agendamiento, 1.1 s)_:
> Va, mañana sábado 3 de octubre a las 11:00 🕚 (queda como solicitud y la confirma el Ing. Leopoldo).
> 
> Para apartarla, pásame tu dirección completa por escrito:
> - Calle y número exterior
> - Número de departamento (si aplica)
> - Colonia y alcaldía
> - Una referencia para llegar (entre qué calles, color de la fachada…)

Ficha en el CRM: `{"geo": "Roma Norte CP 06700", "plaga": "Hormiga común", "tipo_inmueble": "departamento", "cotizacion": "$1,300 MXN por visita (departamento de 50 a 100 m²)", "datos_cotizacion": "tipo_inmueble=departamento, m2=70", "calificado": true}`

---

### garantia_lead_nuevo · rep 2 · ✅ PASA
_«¿Tiene garantía?» de un lead nuevo: no inventa una, lo remite al dueño_

**Lead 1:** hola, tengo hormigas en fila en la cocina todos los días, vivo en un depa de 70 metros en la roma norte, cp 06700
> 🔧 `verificar_cobertura` {"zona": "Roma Norte", "codigo_postal": "06700"}
> 🔧 `identificar_plaga` {"plaga": "hormiga", "senales": [{"senal": "fila_visible", "cita": "hormigas en fila"}, {"senal": "constancia", "cita": "todos los días"}, {"senal": "zonas", "cita": "en la cocina"}]}
**Nea 1** _(procedimiento, 3.0 s)_:
> ¡Hola! Soy Nea, agente de IA de Control de Plagas ROCA 👋 Por lo que me cuentas, es hormiga común 🐜.
> 
> 🛠️ Se coloca cebo en gel sobre el camino de las hormigas: las obreras lo llevan al nido y alimentan con él a la reina y a las larvas.
> 🗓️ 1 visita (no es un esquema cerrado de dos).
> 
> ¿Has notado si han aumentado estos días?

**Lead 2:** y el servicio tiene garantía? de cuánto tiempo?
**Nea 2** _(cotizacion, 1.4 s)_:
> Ese punto lo define el Ing. Leopoldo, así que si quieres te puedo comunicar con él 👍
> 
> Mientras tanto, ¿quieres que te diga cuánto costaría el tratamiento para tu depa?

**Lead 3:** no, primero quiero el precio
> 🔧 `cotizar` {"tipo_inmueble": "departamento"}
> 🔧 `cotizar` {"tipo_inmueble": "departamento", "m2": 70}
**Nea 3** _(aceptacion, 2.7 s)_:
> 📋 *Resumen de tu cotización*
> 🐜 Hormiga común
> 🛠️ Tratamiento: 1 visita (no es un esquema cerrado de dos)
> 💵 $1,300 MXN por visita (departamento de 50 a 100 m²)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 4:** gracias, $1,300 queda caro, lo voy a comparar con otra empresa y te aviso
**Nea 4** _(aceptacion, 0.9 s)_:
> ¡Claro, sin problema! Comparar siempre es buena idea 👍
> 
> Si necesitas algo más por aquí, me escribes con gusto. Que tengas buen día 🐜✨

Ficha en el CRM: `{"geo": "Roma Norte CP 06700", "plaga": "Hormiga común", "tipo_inmueble": "departamento", "cotizacion": "$1,300 MXN por visita (departamento de 50 a 100 m²)", "datos_cotizacion": "tipo_inmueble=departamento, m2=70", "calificado": true}`

---

### garantia_lead_nuevo · rep 3 · ✅ PASA
_«¿Tiene garantía?» de un lead nuevo: no inventa una, lo remite al dueño_

**Lead 1:** hola, tengo hormigas en fila en la cocina todos los días, vivo en un depa de 70 metros en la roma norte, cp 06700
> 🔧 `verificar_cobertura` {"zona": "Roma Norte", "codigo_postal": "06700"}
> 🔧 `identificar_plaga` {"plaga": "hormiga", "senales": [{"senal": "fila_visible", "cita": "hormigas en fila en la cocina"}, {"senal": "constancia", "cita": "todos los días"}, {"senal": "zonas", "cita": "en la cocina"}]}
**Nea 1** _(procedimiento, 1.9 s)_:
> ¡Hola! Soy Nea, el agente de IA de Control de Plagas ROCA 👋 Por lo que me cuentas, es hormiga común 🐜.
> 
> 🛠️ Se coloca cebo en gel sobre el camino de las hormigas: las obreras lo llevan al nido y alimentan con él a la reina y a las larvas.
> 🗓️ 1 visita (no es un esquema cerrado de dos).
> 
> ¿Has notado si han aumentado estos días?

**Lead 2:** y el servicio tiene garantía? de cuánto tiempo?
**Nea 2** _(cotizacion, 1.8 s)_:
> Ese punto lo define directamente el Ing. Leopoldo, así que no quiero darte un dato por mí. Si quieres, te comunico con él 😊
> 
> Y por lo del costo, ¿quieres que te diga cuánto costaría el tratamiento para tu depa?

**Lead 3:** sí, dime el costo
> 🔧 `cotizar` {"tipo_inmueble": "departamento"}
**Nea 3** _(cotizacion, 1.8 s)_:
> ¡Va! Solo me falta un dato: ¿cuántos metros cuadrados son en total, más o menos?

**Lead 4:** 70 metros
> 🔧 `cotizar` {"tipo_inmueble": "departamento", "m2": 70}
**Nea 4** _(aceptacion, 1.7 s)_:
> 📋 *Resumen de tu cotización*
> 🐜 Hormiga común
> 🛠️ Tratamiento: 1 visita (no es un esquema cerrado de dos)
> 💵 $1,300 MXN por visita (departamento de 50 a 100 m²)
> 🤝 Se liquida al término de cada visita.
> 
> ¿Te gustaría que agendemos tu primera visita?

**Lead 5:** todavía no quiero agendar, primero quiero hablar con el ingeniero sobre la garantía, me lo puedes comunicar?
> 🔧 `handoff` {"reason": "cliente", "nota": "Lead con cotización entregada ($1,300, hormigas, depa 70m² Roma Norte). Quiere hablar con el dueño sobre la garantía antes de agendar."}
**Nea 5** _(con_el_dueno, 3.4 s)_:
> ¡Claro! Permíteme un momento mientras te comunico con el Ing. Leopoldo 🙏

Handoffs: ['cliente']
Ficha en el CRM: `{"geo": "Roma Norte CP 06700", "plaga": "Hormiga común", "tipo_inmueble": "departamento", "cotizacion": "$1,300 MXN por visita (departamento de 50 a 100 m²)", "datos_cotizacion": "tipo_inmueble=departamento, m2=70", "calificado": true, "resultado": "handoff", "notas": "Lead con cotización entregada ($1,300, hormigas, depa 70m² Roma Norte). Quiere hablar con el dueño sobre la garantía antes de agendar."}`

---
