# Autoprueba ROCA — modo `vertical`

- Fecha: 2026-10-02 11:35
- Modelo: `(re-evaluación de final6-dirigida)`
- Conversaciones: 8 (8 escenarios × 1)
- **Pasan: 8/8 (100%)**
- Turnos: 50 · 2.9 s por turno
- Tokens de Nea: 593,289 de entrada (471,552 en caché), 6,504 de salida, 86 llamadas

## Por escenario

| Escenario | Pasa |
|---|---|
| ✅ `alemana_casa` — Cucaracha alemana en casa: del saludo a la solicitud de visita | 1/1 |
| ✅ `cucaracha_no_sabe` — No sabe describirlas: tarjeta comparativa y luego confirma | 1/1 |
| ✅ `garrapatas` — Plaga fuera de catálogo: honestidad y pase al dueño, sin improvisar | 1/1 |
| ✅ `precio_de_entrada` — Pide precio en el primer mensaje: ni lo ignora ni suelta cifra | 1/1 |
| ✅ `regateo_y_total` — Tras el precio: pide descuento y el total de las dos visitas | 1/1 |
| ✅ `repite_precio` — Pide que le repitan el precio: lo repite igual, sin re-preguntar | 1/1 |
| ✅ `sin_agenda` — CRM sin agenda: no inventa horarios, junta datos y pasa al dueño | 1/1 |
| ✅ `toluca_miercoles` — Toluca: solo miércoles, y los horarios ofrecidos son miércoles | 1/1 |

## Fallas por tipo

- ninguna

## Candados que se dispararon (antes de enviar)

- `reparado`: 3
