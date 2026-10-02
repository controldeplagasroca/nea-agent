# Instalar esta Nea en tu Vocero

Para quien ya tiene **Vocero CRM + Nea** corriendo en Coolify (instalado con el
Vocero Starter) y quiere cambiar su Nea por esta. No se reinstala nada: es la
misma app de Coolify apuntando a otro repositorio. Tu CRM, tu número de
WhatsApp y tu base de datos no se tocan.

Con Claude Code abierto en tu carpeta del Vocero Starter, basta con decirle:

> Cambia mi app de Nea para que construya desde el repositorio
> `https://github.com/TU_USUARIO/roca-nea` (rama `main`), agrégale la variable
> `AGENDA_MODO=aprobacion`, redespliega y verifica `/health`.

Si prefieres hacerlo a mano, son estos pasos.

## 1. Ten el código en tu cuenta

Haz **fork** de este repositorio a tu cuenta de GitHub (botón *Fork*), o si te
lo compartieron como colaborador, clónalo y súbelo a un repositorio tuyo:

```bash
gh repo fork kevinrivm/roca-nea --clone
```

Si lo dejas **público**, Coolify lo construye sin nada más. Si lo quieres
**privado**, conecta tu GitHub a Coolify con su GitHub App (Sources → GitHub).

> Ojo: el catálogo trae los precios reales del negocio. Público significa que
> cualquiera puede leerlos.

## 2. Apunta tu app de Nea al repositorio nuevo

En Coolify → tu proyecto → la app de Nea → **General**:

- **Git Repository**: `https://github.com/TU_USUARIO/roca-nea`
- **Branch**: `main`
- **Build Pack**: `Dockerfile` (igual que antes)
- Puerto `8000`. **Healthcheck de Coolify apagado** (el Dockerfile trae el suyo).

Si tu Nea se instaló como *Docker Image* (`ghcr.io/kevinrivm/nea-agent:…`),
crea una app nueva tipo *Public Repository* con esos datos, copia las mismas
variables y pásale el dominio.

## 3. Variables

Las que ya tenías se quedan **todas** igual (`VERIFY_TOKEN`, `META_APP_SECRET`,
`CRM_BASE_URL`, `CRM_WEBHOOK_URL`, `CRM_BOT_API_KEY`, `LLM_*` u `OPENAI_*`,
`DATABASE_URL`, `ALLOWED_WA_IDS`, `TESTER_WA_IDS`…). Lo nuevo:

| Variable | Valor | Para qué |
|---|---|---|
| `AGENDA_MODO` | `aprobacion` | La visita queda como solicitud y la confirmas tú. `directa` si quieres que reserve sola. |
| `AVISO_DUENO_WA` | tu WhatsApp personal, con lada (`5215512345678`) | Opcional. Cada vez que Nea te pasa una conversación, te manda el resumen a ese número. Ver abajo. |

### Que te avise a tu WhatsApp (opcional)

Cuando Nea te pasa una conversación —una solicitud de visita, una cotización
que tienes que dar tú, alguien que pide hablar contigo— **siempre** queda en
la bandeja de Vocero: la conversación sale de la IA, aparece marcada para
atención humana y la ficha del contacto trae la plaga, los datos del
inmueble, la cotización, la dirección y una nota con el motivo.

Si además pones `AVISO_DUENO_WA`, te llega esto a tu WhatsApp:

```
🔔 Nea te pasó una conversación
👤 Ana · 525511112222
🗓️ Pide visita: sábado 3 de octubre, 09:00 — pendiente de que la confirmes
🪳 Cucaracha alemana
🗺️ Del Valle CP 03100
🏠 tipo_inmueble: casa
💵 $1,200 MXN por visita (casa)
📍 Heriberto Frías 1125, Del Valle, Benito Juárez (ref.: portón negro)
Contéstale desde la bandeja de Vocero: en esa conversación Nea ya no escribe.
```

Tres cosas que debes saber, porque son reglas de WhatsApp y no de Nea:

1. **Escríbele una vez al número del negocio desde ese WhatsApp** (un «hola»
   basta). WhatsApp solo deja escribirte durante las 24 horas siguientes a tu
   último mensaje. Si pasan más de 24 horas sin que escribas, el aviso no
   sale y te queda solo la bandeja. Un «hola» cada mañana lo mantiene abierto.
2. **En tu conversación (la del dueño) deja la IA encendida** en Vocero. Con
   la IA en pausa el CRM no deja que Nea te escriba.
3. **A ese número Nea no lo atiende como cliente.** No le contesta ni lo
   califica. Para probar el bot usa otro teléfono.

No hace falta poner `VERTICAL`, `HISTORY_WINDOW` ni `STALL_MAX_TURNS`: la
imagen de este fork ya las trae (`plagas`, `24`, `24`).

Modelo recomendado (con el que se hizo la autoprueba):

```
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=z-ai/glm-5.3-flash
LLM_REASONING_EFFORT=minimal
LLM_PROVIDER_SORT=throughput
```

Para que entienda notas de voz con OpenRouter, pon además un modelo que oiga:
`LLM_TRANSCRIBE_MODEL=google/gemini-2.5-flash` (los GLM no oyen).

## 4. En el CRM

- **Agenda encendida** (`AGENDA=on` en las variables del CRM y redeploy) y tus
  horarios de atención cargados en el calendario: de ahí salen los horarios que
  Nea ofrece. Sin agenda, Nea no inventa horarios: junta la dirección y el día
  que prefiere el cliente y te pasa la conversación.
- **El agente incluido de Vocero, apagado** (el CRM sin `OPENROUTER_API_TOKEN`).
  Si contestan los dos, el cliente recibe dos respuestas.
- Pantalla **Agente**: el nombre del agente sale de ahí. El conocimiento que
  cargues ahí (horario de atención, formas de pago, datos del negocio) Nea lo
  usa para contestar dudas. **Los precios y tratamientos NO van ahí**: viven en
  `app/plagas/catalogo.py`, donde el modelo no los puede cambiar. Si en tu
  perfil del CRM tienes instrucciones viejas con precios o con el flujo de
  venta, bórralas: dos fuentes de verdad es como empieza a inventar.

## 5. Redespliega y prueba

**Redeploy** (no restart: las variables y el código nuevo solo entran con un
deploy). La migración `009_caso.sql` se aplica sola al arrancar.

```bash
curl -s https://TU_DOMINIO_DE_NEA/health
```

Debe dar `200`. Después, desde tu WhatsApp de pruebas (sigues en la allowlist):

1. `/reset`
2. «hola, tengo cucarachas» → te pregunta tu zona.
3. Dale tu colonia y CP → sigue con el tamaño y dónde las ves.
4. Contesta → te dice qué plaga es y el tratamiento.
5. «¿cuánto cuesta?» → te pregunta casa o departamento → te manda el resumen
   con el precio del catálogo.
6. «sí, agéndame» → horarios reales → dirección → «registré tu solicitud…» y
   en tu bandeja aparece el aviso con todo en la ficha del contacto.

Prueba también lo que no debe hacer: pregúntale el precio de entrada (no debe
soltar cifra), dile que estás en Ecatepec (debe despedirse), pregúntale por
garrapatas (debe pasarte con el dueño sin inventar tratamiento).

Y lo que contaste en tus audios:

- Dile «no conozco de cucarachas, pero son chiquitas» y luego «en la cocina, y
  también en el baño»: debe decirte que es la alemana, que no es por falta de
  higiene y que son dos visitas — sin volver a preguntarte el color ni el baño.
- Ya con la plaga confirmada, pregúntale «¿eso no es tóxico?» y «¿en cuánto
  tiempo podemos volver a entrar?»: debe contestar lo aprobado (15 a 20
  minutos) y no ponerse a preguntarte otra vez cómo son.
- Pregúntale «¿tiene garantía?»: no debe inventar una.
- Pídele el precio de algo que cotizas tú (cucaracha grande de drenaje): no
  debe decirte «te la mando luego». Te pide los datos, te dice que ya te los
  pasó y la conversación aparece en tu bandeja (y en tu WhatsApp, si pusiste
  `AVISO_DUENO_WA`).

## Cambiar un precio o una zona

Todo está en `app/plagas/catalogo.py`. Edita, corre las pruebas y sube:

```bash
pip install -r requirements-dev.txt
pytest -q
git commit -am "catalogo: nuevo precio de hormiga" && git push
```

y redespliega. Las pruebas de `tests/test_plagas_negocio.py` traen los precios
de tu especificación: si cambias uno a propósito, actualiza también la prueba.

Lo que todavía falta que definas está en [PENDIENTES.md](PENDIENTES.md).

## Volver a probar el comportamiento (el «improvement loop»)

Sin WhatsApp y sin tocar tu CRM: conversaciones simuladas contra el modelo real.

```bash
python -m selftest.roca --env-file .env --reps 3
```

Detalle en [LOOP.md](LOOP.md).
