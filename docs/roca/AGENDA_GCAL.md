# Agenda en Google Calendar, aprobación del dueño y OPS

Portado de la Nea anterior de ROCA. Todo se enciende con variables; sin ellas la
Nea se comporta como antes de este cambio (usa la agenda del CRM).

| Variable | Para qué |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` y `GOOGLE_CALENDAR_ID` | Con las dos, los horarios que Nea ofrece salen de ese calendario (duración y ventanas por plaga: `app/gcal.py`). |
| `OWNER_WA_ID` (o `AVISO_DUENO_WA`) | WhatsApp del dueño. Recibe cada solicitud como «Cita #N por aprobar» y la resuelve con «sí N» o «no N». |
| `BOOKING_REMINDER_MINUTES` (10) | Cada cuánto se revisa una solicitud sin resolver. |
| `APPROVAL_REMINDER_REENVIAR` (false) | `true` = reenviar la solicitud en cada revisión aunque el dueño ya la tenga. |
| `BOOKING_LEAD_HOURS` (24) | Anticipación mínima para ofrecer un horario. |
| `ROCA_OPS_SYNC_SECRET` | Secreto de `POST /roca-ops/sync` (ROCA OPS → ficha del CRM). Vacío = el endpoint responde 503. |

## Cómo fluye una visita

1. El cliente acepta la cotización y elige un horario de los que salen del calendario.
2. Nea registra la solicitud (ficha + pase al dueño) **y** crea una solicitud con folio.
3. El dueño recibe «Cita #N por aprobar» en su WhatsApp. Responde `sí N` o `no N`.
   - Cualquier otra cosa **no** aprueba: la solicitud sigue pendiente.
   - **Aprobada:** se crea el evento en Google Calendar (con costo, dirección y
     teléfono en la descripción, para ROCA Ops) y se le avisa al cliente.
   - **Rechazada:** se le avisa al cliente con horarios alternativos reales.
4. «Recordatorios» aquí son los del **dueño**: mientras haya una solicitud sin
   resolver, el worker la revisa cada `BOOKING_REMINDER_MINUTES` (reenvía solo si
   el aviso original nunca llegó). No son recordatorios de cita al cliente.

## Lo que hay que saber

- La ventana de 24 h de WhatsApp aplica a los avisos al dueño: un «hola» suyo al
  número del negocio la mantiene abierta.
- Tras el pase al dueño, la IA de esa conversación queda en pausa. Si el CRM
  rechaza el aviso al cliente, a quien aprueba le sale una nota para que le
  escriba él desde la bandeja.
- Termitas y moscas/mosquitos no tienen regla de agenda: no se ofrecen horarios,
  se pasan al dueño. La tijerilla se agenda como la alemana (90 min): **suposición,
  confirmar** en `app/gcal.py::SERVICE_RULES`.
- Las reglas de Lerma/Toluca (solo miércoles) siguen aplicándose encima de los
  horarios del calendario.
- `app/horarios.py`: antes de apartar un horario compara la hora que escribió el
  lead con la del horario elegido («9:30 pm» vs 09:30 am → pregunta antes).

## Regla del horario

- **Si el cliente propone su día u hora**, no se agenda ni se le contradice: la
  conversación se pasa al dueño con lo que escribió, para que lo verifique.
  Elegir una hora de las ya ofrecidas no cuenta como proponer.
- **Si no propone ninguno**, Nea ofrece los suyos: desde 24 h después del momento
  en que escribe (`BOOKING_LEAD_HOURS`), dentro del horario laboral (lun-vie
  9:00-18:00, sáb 9:00-14:00; hormiga solo 9:00-11:30 y 16:00-18:30). Si ese
  momento cae fuera de horario, ofrece el siguiente horario laboral inmediato.
- Duración que bloquea cada visita (interna, no se le dice al cliente): cucaracha
  alemana y americana 90 min (60 de aplicación + 30 de traslado).

## Técnicos en paralelo y zonas de un solo día

- **Capacidad:** `BOOKING_MAX_PARALELO` (2 por defecto: 3 técnicos, uno de colchón).
  Un horario sigue libre mientras coincidan menos visitas de las permitidas.
  Se cuentan los **eventos** del calendario compartido (no freeBusy, que fusiona
  los traslapes). Un evento de día completo (feriado, cierre) cierra ese día;
  los cancelados y los marcados «disponible» no ocupan.
- **Nea no asigna técnico:** solo sabe cuántas visitas caben a la vez.
- **Toluca y Lerma (solo miércoles):** como no todos los técnicos van, que el
  horario esté libre no basta. La solicitud te llega con la nota «⚠️ Zona Toluca
  (solo miércoles): confirma que haya un técnico que vaya ese día antes de
  aprobar», y al cliente se le dice que se verifica la disponibilidad.

## Continuidad y avisos cuando Nea se detiene

Nea ya no se calla sin que nadie se entere:

| Qué pasa | Qué recibe el cliente | Qué recibes tú |
|---|---|---|
| El modelo de IA falla tras reintentos, o su respuesta no sirve dos veces | «Tuve un problema para responderte… ya avisé al equipo» | ⚠️ *Nea se detuvo con un cliente* + qué pasó + su último mensaje |
| El turno revienta por un error interno | (la red de seguridad apaga la IA) | ⚠️ el mismo aviso |
| La IA de esa conversación está apagada y el cliente sigue escribiendo | nada (Nea respeta el interruptor) | ⚠️ aviso, **una vez cada 30 min por cliente** |
| El cliente manda una imagen que el modelo no puede ver | «No pude ver tu foto, ¿me describes…?» (se reintenta sin la imagen) | nada: la conversación sigue |

El aviso sale a `AVISO_DUENO_WA` (o `OWNER_WA_ID`). Sigue la regla de WhatsApp de
las 24 h: si no le has escrito al número del negocio en el último día, el aviso
no sale y solo queda la bandeja de Vocero. Un «hola» cada mañana lo mantiene abierto.
