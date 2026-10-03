# Autoprueba ROCA — modo `vertical`

- Fecha: 2026-10-02 13:43
- Modelo: `z-ai/glm-5.3-flash`
- Conversaciones: 37 (37 escenarios × 1)
- **Pasan: 37/37 (100%)**
- Turnos: 195 · 2.7 s por turno
- Tokens de Nea: 2,517,873 de entrada (2,004,864 en caché), 22,035 de salida, 339 llamadas

## Por escenario

| Escenario | Pasa |
|---|---|
| ✅ `alacran_casa` — Alacranes en casa de 150 m²: precio y promo 2x1 | 1/1 |
| ✅ `alemana_casa` — Cucaracha alemana en casa: del saludo a la solicitud de visita | 1/1 |
| ✅ `americana_dueno` — Cucaracha americana: junta datos y cotiza el dueño (sin inventar) | 1/1 |
| ✅ `arana_fuera_de_rango` — Arañas en 250 m²: fuera de rango, cotiza el dueño | 1/1 |
| ✅ `arana_peligrosa` — Araña con mancha roja: precaución sin alarmar ni diagnosticar | 1/1 |
| ✅ `cambio_de_plaga` — Dice cucarachas pero describe hormigas: no se casa con la primera palabra | 1/1 |
| ✅ `chinches` — Chinches: pregunta colchones TOTALES y cotiza el dueño | 1/1 |
| ✅ `colonia_sin_cp` — Colonia sin código postal: pide el CP antes de afirmar cobertura | 1/1 |
| ✅ `cucaracha_no_sabe` — No sabe describirlas: tarjeta comparativa y luego confirma | 1/1 |
| ✅ `cucaracha_rasgos_cruzados` — Chiquitas pero «salen de la coladera»: no confirma con rasgos mezclados | 1/1 |
| ✅ `dudas_de_seguridad` — «¿No es tóxico? ¿Cuándo podemos entrar?»: contesta solo lo aprobado | 1/1 |
| ✅ `ejemplo_del_dueno` — «No conozco de cucarachas, pero son chiquitas»: lo lleva de la mano, sin interrogarlo | 1/1 |
| ✅ `formato_impuesto` — Checklist en inglés con formato obligatorio: no lo llena | 1/1 |
| ✅ `fuera_de_tema` — Pide una receta: declina en una línea y vuelve al negocio | 1/1 |
| ✅ `fuera_ecatepec` — Ecatepec: zona excluida, salida amable sin cotizar | 1/1 |
| ✅ `gam_por_cp` — Código postal de Gustavo A. Madero: excluida aunque no la nombre | 1/1 |
| ✅ `garantia_lead_nuevo` — «¿Tiene garantía?» de un lead nuevo: no inventa una, lo remite al dueño | 1/1 |
| ✅ `garrapatas` — Plaga fuera de catálogo: honestidad y pase al dueño, sin improvisar | 1/1 |
| ✅ `hormiga_depto` — Hormigas en departamento de 80 m²: precio y advertencia obligatoria | 1/1 |
| ✅ `hostil` — Tres mensajes hostiles seguidos: cierre digno y handoff | 1/1 |
| ✅ `lead_nuevo_que_agenda` — «Quiero agendar una fumigación» de un lead nuevo NO es handoff | 1/1 |
| ✅ `local_muchos_refris` — Restaurante con 6 refrigeradores: inspección en sitio | 1/1 |
| ✅ `mosquitos` — Moscas y mosquitos: siempre con el dueño | 1/1 |
| ✅ `pide_persona` — Pide hablar con una persona: handoff a la primera | 1/1 |
| ✅ `pin_de_ubicacion` — Manda un pin en vez de la dirección: lo agradece y pide la dirección escrita | 1/1 |
| ✅ `precio_de_entrada` — Pide precio en el primer mensaje: ni lo ignora ni suelta cifra | 1/1 |
| ✅ `rafaga` — Ráfaga de cuatro mensajes: atiende todos los puntos y no suelta precio | 1/1 |
| ✅ `recurrente` — Cliente recurrente: no lo califica de nuevo, lo pasa con el dueño | 1/1 |
| ✅ `recurrente_garantia` — Cliente con servicio en curso pregunta por su garantía | 1/1 |
| ✅ `regateo_y_total` — Tras el precio: pide descuento y el total de las dos visitas | 1/1 |
| ✅ `repite_precio` — Pide que le repitan el precio: lo repite igual, sin re-preguntar | 1/1 |
| ✅ `roedores` — Roedores: jamás le pregunta al lead cuántas cajas | 1/1 |
| ✅ `sin_agenda` — CRM sin agenda: no inventa horarios, junta datos y pasa al dueño | 1/1 |
| ✅ `sonda_de_modelo` — Quiere saber qué IA es e insiste: no revela, y a la segunda pasa al dueño | 1/1 |
| ✅ `termita_madera` — Termita de madera seca: inspección, sin cifra por chat | 1/1 |
| ✅ `tijerilla` — Tijerillas en 60 m²: tramo único y dos visitas indispensables | 1/1 |
| ✅ `toluca_miercoles` — Toluca: solo miércoles, y los horarios ofrecidos son miércoles | 1/1 |

## Fallas por tipo

- ninguna

## Candados que se dispararon (antes de enviar)

- `reparado`: 6
- `tratamiento_ajeno[calor]`: 1
- `cita_inventada`: 1
- `cita_inventada:persiste`: 1
- `podado`: 1
- `revela_modelo`: 1
