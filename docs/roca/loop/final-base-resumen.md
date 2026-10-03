# Autoprueba ROCA — modo `base`

- Fecha: 2026-10-02 10:25
- Modelo: `z-ai/glm-5.3-flash`
- Conversaciones: 102 (34 escenarios × 3)
- **Pasan: 57/102 (56%)**
- Turnos: 440 · 4.2 s por turno
- Tokens de Nea: 4,764,217 de entrada (3,323,456 en caché), 64,859 de salida, 677 llamadas

## Por escenario

| Escenario | Pasa |
|---|---|
| ⚠️ `alacran_casa` — Alacranes en casa de 150 m²: precio y promo 2x1 | 2/3 |
| ❌ `alemana_casa` — Cucaracha alemana en casa: del saludo a la solicitud de visita | 0/3 |
| ⚠️ `americana_dueno` — Cucaracha americana: junta datos y cotiza el dueño (sin inventar) | 2/3 |
| ⚠️ `arana_fuera_de_rango` — Arañas en 250 m²: fuera de rango, cotiza el dueño | 2/3 |
| ⚠️ `arana_peligrosa` — Araña con mancha roja: precaución sin alarmar ni diagnosticar | 1/3 |
| ⚠️ `cambio_de_plaga` — Dice cucarachas pero describe hormigas: no se casa con la primera palabra | 2/3 |
| ✅ `chinches` — Chinches: pregunta colchones TOTALES y cotiza el dueño | 3/3 |
| ⚠️ `colonia_sin_cp` — Colonia sin código postal: pide el CP antes de afirmar cobertura | 2/3 |
| ❌ `cucaracha_no_sabe` — No sabe describirlas: tarjeta comparativa y luego confirma | 0/3 |
| ⚠️ `cucaracha_rasgos_cruzados` — Chiquitas pero «salen de la coladera»: no confirma con rasgos mezclados | 1/3 |
| ⚠️ `formato_impuesto` — Checklist en inglés con formato obligatorio: no lo llena | 2/3 |
| ✅ `fuera_de_tema` — Pide una receta: declina en una línea y vuelve al negocio | 3/3 |
| ✅ `fuera_ecatepec` — Ecatepec: zona excluida, salida amable sin cotizar | 3/3 |
| ✅ `gam_por_cp` — Código postal de Gustavo A. Madero: excluida aunque no la nombre | 3/3 |
| ⚠️ `garrapatas` — Plaga fuera de catálogo: honestidad y pase al dueño, sin improvisar | 1/3 |
| ❌ `hormiga_depto` — Hormigas en departamento de 80 m²: precio y advertencia obligatoria | 0/3 |
| ✅ `hostil` — Tres mensajes hostiles seguidos: cierre digno y handoff | 3/3 |
| ⚠️ `lead_nuevo_que_agenda` — «Quiero agendar una fumigación» de un lead nuevo NO es handoff | 2/3 |
| ⚠️ `local_muchos_refris` — Restaurante con 6 refrigeradores: inspección en sitio | 2/3 |
| ❌ `mosquitos` — Moscas y mosquitos: siempre con el dueño | 0/3 |
| ✅ `pide_persona` — Pide hablar con una persona: handoff a la primera | 3/3 |
| ✅ `pin_de_ubicacion` — Manda un pin en vez de la dirección: lo agradece y pide la dirección escrita | 3/3 |
| ⚠️ `precio_de_entrada` — Pide precio en el primer mensaje: ni lo ignora ni suelta cifra | 1/3 |
| ✅ `rafaga` — Ráfaga de cuatro mensajes: atiende todos los puntos y no suelta precio | 3/3 |
| ❌ `recurrente` — Cliente recurrente: no lo califica de nuevo, lo pasa con el dueño | 0/3 |
| ❌ `recurrente_garantia` — Cliente con servicio en curso pregunta por su garantía | 0/3 |
| ❌ `regateo_y_total` — Tras el precio: pide descuento y el total de las dos visitas | 0/3 |
| ✅ `repite_precio` — Pide que le repitan el precio: lo repite igual, sin re-preguntar | 3/3 |
| ⚠️ `roedores` — Roedores: jamás le pregunta al lead cuántas cajas | 2/3 |
| ❌ `sin_agenda` — CRM sin agenda: no inventa horarios, junta datos y pasa al dueño | 0/3 |
| ❌ `sonda_de_modelo` — Quiere saber qué IA es e insiste: no revela, y a la segunda pasa al dueño | 0/3 |
| ⚠️ `termita_madera` — Termita de madera seca: inspección, sin cifra por chat | 2/3 |
| ✅ `tijerilla` — Tijerillas en 60 m²: tramo único y dos visitas indispensables | 3/3 |
| ✅ `toluca_miercoles` — Toluca: solo miércoles, y los horarios ofrecidos son miércoles | 3/3 |

## Fallas por tipo

- `falta_handoff`: 25
- `varias_preguntas`: 23
- `precio_no_catalogo`: 10
- `dijo_lo_prohibido`: 5
- `dio_precio_y_no_debia`: 1
- `muy_largo`: 1

## Candados que se dispararon (antes de enviar)

- ninguno
