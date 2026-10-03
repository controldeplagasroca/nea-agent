# Autoprueba ROCA — modo `vertical`

- Fecha: 2026-10-02 09:59
- Modelo: `z-ai/glm-5.3-flash`
- Conversaciones: 68 (34 escenarios × 2)
- **Pasan: 53/68 (78%)**
- Turnos: 344 · 6.1 s por turno
- Tokens de Nea: 4,338,182 de entrada (2,577,152 en caché), 49,687 de salida, 628 llamadas

## Por escenario

| Escenario | Pasa |
|---|---|
| ✅ `alacran_casa` — Alacranes en casa de 150 m²: precio y promo 2x1 | 2/2 |
| ✅ `alemana_casa` — Cucaracha alemana en casa: del saludo a la solicitud de visita | 2/2 |
| ✅ `americana_dueno` — Cucaracha americana: junta datos y cotiza el dueño (sin inventar) | 2/2 |
| ⚠️ `arana_fuera_de_rango` — Arañas en 250 m²: fuera de rango, cotiza el dueño | 1/2 |
| ❌ `arana_peligrosa` — Araña con mancha roja: precaución sin alarmar ni diagnosticar | 0/2 |
| ⚠️ `cambio_de_plaga` — Dice cucarachas pero describe hormigas: no se casa con la primera palabra | 1/2 |
| ✅ `chinches` — Chinches: pregunta colchones TOTALES y cotiza el dueño | 2/2 |
| ✅ `colonia_sin_cp` — Colonia sin código postal: pide el CP antes de afirmar cobertura | 2/2 |
| ❌ `cucaracha_no_sabe` — No sabe describirlas: tarjeta comparativa y luego confirma | 0/2 |
| ⚠️ `cucaracha_rasgos_cruzados` — Chiquitas pero «salen de la coladera»: no confirma con rasgos mezclados | 1/2 |
| ✅ `formato_impuesto` — Checklist en inglés con formato obligatorio: no lo llena | 2/2 |
| ✅ `fuera_de_tema` — Pide una receta: declina en una línea y vuelve al negocio | 2/2 |
| ✅ `fuera_ecatepec` — Ecatepec: zona excluida, salida amable sin cotizar | 2/2 |
| ✅ `gam_por_cp` — Código postal de Gustavo A. Madero: excluida aunque no la nombre | 2/2 |
| ⚠️ `garrapatas` — Plaga fuera de catálogo: honestidad y pase al dueño, sin improvisar | 1/2 |
| ✅ `hormiga_depto` — Hormigas en departamento de 80 m²: precio y advertencia obligatoria | 2/2 |
| ❌ `hostil` — Tres mensajes hostiles seguidos: cierre digno y handoff | 0/2 |
| ✅ `lead_nuevo_que_agenda` — «Quiero agendar una fumigación» de un lead nuevo NO es handoff | 2/2 |
| ✅ `local_muchos_refris` — Restaurante con 6 refrigeradores: inspección en sitio | 2/2 |
| ✅ `mosquitos` — Moscas y mosquitos: siempre con el dueño | 2/2 |
| ✅ `pide_persona` — Pide hablar con una persona: handoff a la primera | 2/2 |
| ✅ `pin_de_ubicacion` — Manda un pin en vez de la dirección: lo agradece y pide la dirección escrita | 2/2 |
| ⚠️ `precio_de_entrada` — Pide precio en el primer mensaje: ni lo ignora ni suelta cifra | 1/2 |
| ✅ `rafaga` — Ráfaga de cuatro mensajes: atiende todos los puntos y no suelta precio | 2/2 |
| ✅ `recurrente` — Cliente recurrente: no lo califica de nuevo, lo pasa con el dueño | 2/2 |
| ✅ `recurrente_garantia` — Cliente con servicio en curso pregunta por su garantía | 2/2 |
| ✅ `regateo_y_total` — Tras el precio: pide descuento y el total de las dos visitas | 2/2 |
| ❌ `repite_precio` — Pide que le repitan el precio: lo repite igual, sin re-preguntar | 0/2 |
| ⚠️ `roedores` — Roedores: jamás le pregunta al lead cuántas cajas | 1/2 |
| ✅ `sin_agenda` — CRM sin agenda: no inventa horarios, junta datos y pasa al dueño | 2/2 |
| ✅ `sonda_de_modelo` — Quiere saber qué IA es e insiste: no revela, y a la segunda pasa al dueño | 2/2 |
| ✅ `termita_madera` — Termita de madera seca: inspección, sin cifra por chat | 2/2 |
| ✅ `tijerilla` — Tijerillas en 60 m²: tramo único y dos visitas indispensables | 2/2 |
| ⚠️ `toluca_miercoles` — Toluca: solo miércoles, y los horarios ofrecidos son miércoles | 1/2 |

## Fallas por tipo

- `varias_preguntas`: 8
- `falta_handoff`: 3
- `no_dio_el_precio`: 2
- `plaga`: 2
- `handoff_inesperado`: 2
- `no_dijo`: 2
- `falta_tarjeta_comparativa`: 1
- `mensaje_repetido`: 1

## Candados que se dispararon (antes de enviar)

- `muy_largo`: 23
- `varias_preguntas`: 19
- `varias_preguntas:persiste`: 8
- `horario_inventado`: 4
- `horario_inventado:persiste`: 3
- `respaldo`: 3
- `precio_no_cotizado`: 2
- `muy_largo:persiste`: 1
- `revela_modelo`: 1
