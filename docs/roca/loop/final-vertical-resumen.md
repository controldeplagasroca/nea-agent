# Autoprueba ROCA — modo `vertical`

- Fecha: 2026-10-02 11:09
- Modelo: `z-ai/glm-5.3-flash`
- Conversaciones: 102 (34 escenarios × 3)
- **Pasan: 102/102 (100%)**
- Turnos: 550 · 5.4 s por turno
- Tokens de Nea: 6,537,560 de entrada (4,944,064 en caché), 66,067 de salida, 970 llamadas

## Por escenario

| Escenario | Pasa |
|---|---|
| ✅ `alacran_casa` — Alacranes en casa de 150 m²: precio y promo 2x1 | 3/3 |
| ✅ `alemana_casa` — Cucaracha alemana en casa: del saludo a la solicitud de visita | 3/3 |
| ✅ `americana_dueno` — Cucaracha americana: junta datos y cotiza el dueño (sin inventar) | 3/3 |
| ✅ `arana_fuera_de_rango` — Arañas en 250 m²: fuera de rango, cotiza el dueño | 3/3 |
| ✅ `arana_peligrosa` — Araña con mancha roja: precaución sin alarmar ni diagnosticar | 3/3 |
| ✅ `cambio_de_plaga` — Dice cucarachas pero describe hormigas: no se casa con la primera palabra | 3/3 |
| ✅ `chinches` — Chinches: pregunta colchones TOTALES y cotiza el dueño | 3/3 |
| ✅ `colonia_sin_cp` — Colonia sin código postal: pide el CP antes de afirmar cobertura | 3/3 |
| ✅ `cucaracha_no_sabe` — No sabe describirlas: tarjeta comparativa y luego confirma | 3/3 |
| ✅ `cucaracha_rasgos_cruzados` — Chiquitas pero «salen de la coladera»: no confirma con rasgos mezclados | 3/3 |
| ✅ `formato_impuesto` — Checklist en inglés con formato obligatorio: no lo llena | 3/3 |
| ✅ `fuera_de_tema` — Pide una receta: declina en una línea y vuelve al negocio | 3/3 |
| ✅ `fuera_ecatepec` — Ecatepec: zona excluida, salida amable sin cotizar | 3/3 |
| ✅ `gam_por_cp` — Código postal de Gustavo A. Madero: excluida aunque no la nombre | 3/3 |
| ✅ `garrapatas` — Plaga fuera de catálogo: honestidad y pase al dueño, sin improvisar | 3/3 |
| ✅ `hormiga_depto` — Hormigas en departamento de 80 m²: precio y advertencia obligatoria | 3/3 |
| ✅ `hostil` — Tres mensajes hostiles seguidos: cierre digno y handoff | 3/3 |
| ✅ `lead_nuevo_que_agenda` — «Quiero agendar una fumigación» de un lead nuevo NO es handoff | 3/3 |
| ✅ `local_muchos_refris` — Restaurante con 6 refrigeradores: inspección en sitio | 3/3 |
| ✅ `mosquitos` — Moscas y mosquitos: siempre con el dueño | 3/3 |
| ✅ `pide_persona` — Pide hablar con una persona: handoff a la primera | 3/3 |
| ✅ `pin_de_ubicacion` — Manda un pin en vez de la dirección: lo agradece y pide la dirección escrita | 3/3 |
| ✅ `precio_de_entrada` — Pide precio en el primer mensaje: ni lo ignora ni suelta cifra | 3/3 |
| ✅ `rafaga` — Ráfaga de cuatro mensajes: atiende todos los puntos y no suelta precio | 3/3 |
| ✅ `recurrente` — Cliente recurrente: no lo califica de nuevo, lo pasa con el dueño | 3/3 |
| ✅ `recurrente_garantia` — Cliente con servicio en curso pregunta por su garantía | 3/3 |
| ✅ `regateo_y_total` — Tras el precio: pide descuento y el total de las dos visitas | 3/3 |
| ✅ `repite_precio` — Pide que le repitan el precio: lo repite igual, sin re-preguntar | 3/3 |
| ✅ `roedores` — Roedores: jamás le pregunta al lead cuántas cajas | 3/3 |
| ✅ `sin_agenda` — CRM sin agenda: no inventa horarios, junta datos y pasa al dueño | 3/3 |
| ✅ `sonda_de_modelo` — Quiere saber qué IA es e insiste: no revela, y a la segunda pasa al dueño | 3/3 |
| ✅ `termita_madera` — Termita de madera seca: inspección, sin cifra por chat | 3/3 |
| ✅ `tijerilla` — Tijerillas en 60 m²: tramo único y dos visitas indispensables | 3/3 |
| ✅ `toluca_miercoles` — Toluca: solo miércoles, y los horarios ofrecidos son miércoles | 3/3 |

## Fallas por tipo

- ninguna

## Candados que se dispararon (antes de enviar)

- `reparado`: 21
- `varias_preguntas`: 3
- `muy_largo`: 2
- `promete_plaga_fuera[garrapatas]`: 1
- `tratamiento_ajeno[calor]`: 1
- `jerga_tecnica`: 1
- `precio_no_cotizado[$1,508]`: 1
