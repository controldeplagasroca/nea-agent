"""Vertical de control de plagas (Control de Plagas ROCA).

El chasis de Nea decide CÓMO se conversa; este paquete pone los HECHOS del
negocio y los candados que impiden que el modelo los invente:

- `catalogo.py`   — los datos del negocio (plagas, señales, tratamientos,
                    precios, zonas). Es lo ÚNICO que se edita para cambiar un
                    precio o una zona.
- `cobertura.py`  — ¿se atiende esa zona? (determinista)
- `diagnostico.py`— ¿qué plaga es? Mínimo dos señales, cada una con la cita de
                    lo que escribió el lead.
- `precios.py`    — cuánto cuesta. La única fuente de una cifra.
- `caso.py`       — el expediente de la conversación y el PASO ACTUAL.
- `candados.py`   — lo que se revisa del texto del modelo antes de enviarlo.
- `herramientas.py` — las herramientas que ve el modelo, con sus compuertas.
- `prompt.py`     — el chasis conversacional de este negocio.
- `aviso.py`      — el resumen al WhatsApp del dueño cuando se le pasa una
                    conversación (opcional, `AVISO_DUENO_WA`).

Se enciende con `VERTICAL=plagas` (el Dockerfile de este fork ya lo trae).
"""
