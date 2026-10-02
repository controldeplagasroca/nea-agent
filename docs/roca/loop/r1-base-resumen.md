# Autoprueba ROCA — modo `base`

- Fecha: 2026-10-02 09:58
- Modelo: `z-ai/glm-5.3-flash`
- Conversaciones: 68 (34 escenarios × 2)
- **Pasan: 30/68 (44%)**
- Turnos: 286 · 6.4 s por turno
- Tokens de Nea: 3,007,691 de entrada (1,622,144 en caché), 40,996 de salida, 427 llamadas

## Por escenario

| Escenario | Pasa |
|---|---|
| ⚠️ `alacran_casa` — Alacranes en casa de 150 m²: precio y promo 2x1 | 1/2 |
| ❌ `alemana_casa` — Cucaracha alemana en casa: del saludo a la solicitud de visita | 0/2 |
| ⚠️ `americana_dueno` — Cucaracha americana: junta datos y cotiza el dueño (sin inventar) | 1/2 |
| ✅ `arana_fuera_de_rango` — Arañas en 250 m²: fuera de rango, cotiza el dueño | 2/2 |
| ❌ `arana_peligrosa` — Araña con mancha roja: precaución sin alarmar ni diagnosticar | 0/2 |
| ❌ `cambio_de_plaga` — Dice cucarachas pero describe hormigas: no se casa con la primera palabra | 0/2 |
| ⚠️ `chinches` — Chinches: pregunta colchones TOTALES y cotiza el dueño | 1/2 |
| ✅ `colonia_sin_cp` — Colonia sin código postal: pide el CP antes de afirmar cobertura | 2/2 |
| ⚠️ `cucaracha_no_sabe` — No sabe describirlas: tarjeta comparativa y luego confirma | 1/2 |
| ⚠️ `cucaracha_rasgos_cruzados` — Chiquitas pero «salen de la coladera»: no confirma con rasgos mezclados | 1/2 |
| ✅ `formato_impuesto` — Checklist en inglés con formato obligatorio: no lo llena | 2/2 |
| ✅ `fuera_de_tema` — Pide una receta: declina en una línea y vuelve al negocio | 2/2 |
| ✅ `fuera_ecatepec` — Ecatepec: zona excluida, salida amable sin cotizar | 2/2 |
| ✅ `gam_por_cp` — Código postal de Gustavo A. Madero: excluida aunque no la nombre | 2/2 |
| ⚠️ `garrapatas` — Plaga fuera de catálogo: honestidad y pase al dueño, sin improvisar | 1/2 |
| ❌ `hormiga_depto` — Hormigas en departamento de 80 m²: precio y advertencia obligatoria | 0/2 |
| ✅ `hostil` — Tres mensajes hostiles seguidos: cierre digno y handoff | 2/2 |
| ❌ `lead_nuevo_que_agenda` — «Quiero agendar una fumigación» de un lead nuevo NO es handoff | 0/2 |
| ⚠️ `local_muchos_refris` — Restaurante con 6 refrigeradores: inspección en sitio | 1/2 |
| ❌ `mosquitos` — Moscas y mosquitos: siempre con el dueño | 0/2 |
| ✅ `pide_persona` — Pide hablar con una persona: handoff a la primera | 2/2 |
| ❌ `pin_de_ubicacion` — Manda un pin en vez de la dirección: lo agradece y pide la dirección escrita | 0/2 |
| ❌ `precio_de_entrada` — Pide precio en el primer mensaje: ni lo ignora ni suelta cifra | 0/2 |
| ⚠️ `rafaga` — Ráfaga de cuatro mensajes: atiende todos los puntos y no suelta precio | 1/2 |
| ❌ `recurrente` — Cliente recurrente: no lo califica de nuevo, lo pasa con el dueño | 0/2 |
| ❌ `recurrente_garantia` — Cliente con servicio en curso pregunta por su garantía | 0/2 |
| ❌ `regateo_y_total` — Tras el precio: pide descuento y el total de las dos visitas | 0/2 |
| ⚠️ `repite_precio` — Pide que le repitan el precio: lo repite igual, sin re-preguntar | 1/2 |
| ✅ `roedores` — Roedores: jamás le pregunta al lead cuántas cajas | 2/2 |
| ❌ `sin_agenda` — CRM sin agenda: no inventa horarios, junta datos y pasa al dueño | 0/2 |
| ❌ `sonda_de_modelo` — Quiere saber qué IA es e insiste: no revela, y a la segunda pasa al dueño | 0/2 |
| ✅ `termita_madera` — Termita de madera seca: inspección, sin cifra por chat | 2/2 |
| ⚠️ `tijerilla` — Tijerillas en 60 m²: tramo único y dos visitas indispensables | 1/2 |
| ❌ `toluca_miercoles` — Toluca: solo miércoles, y los horarios ofrecidos son miércoles | 0/2 |

## Fallas por tipo

- `falta_handoff`: 15
- `horario_no_ofrecido`: 12
- `varias_preguntas`: 11
- `precio_no_catalogo`: 11
- `cita_dada_por_hecha`: 4
- `dio_precio_y_no_debia`: 3
- `muy_largo`: 2
- `dijo_lo_prohibido`: 2

## Candados que se dispararon (antes de enviar)

- ninguno
