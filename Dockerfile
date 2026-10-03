# Nea — agente de agendamiento para WhatsApp
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY scripts/live-security-test.py ./scripts/live-security-test.py

RUN groupadd --gid 10001 nea && useradd --uid 10001 --gid nea --no-create-home --shell /usr/sbin/nologin nea
USER 10001:10001

# Qué versión corre, para /health (app/version.py). Van después del
# `pip install` para no invalidar su caché en cada commit. El commit se
# guarda en NEA_BUILD_COMMIT y no en SOURCE_COMMIT a propósito: la
# plataforma puede poner SOURCE_COMMIT en el entorno al arrancar y lo
# pisaría, y /health ya no sabría si salió del build (verificado) o no.
#   docker build --build-arg NEA_VERSION=1.0.0 \
#     --build-arg SOURCE_COMMIT=$(git rev-parse HEAD) .
ARG NEA_VERSION=dev
ARG SOURCE_COMMIT=
ENV NEA_VERSION=${NEA_VERSION} \
    NEA_BUILD_COMMIT=${SOURCE_COMMIT}

# Este fork es la Nea de Control de Plagas ROCA: el vertical viene encendido
# (app/plagas/). Una conversación de plagas es más larga que una de agenda
# —zona, señales, datos del inmueble, dirección—, así que el modelo ve más
# historial y el candado de cierre aguanta más mensajes. Las tres se pueden
# pisar con variables del contenedor; VERTICAL vacía devuelve la Nea genérica.
ENV VERTICAL=plagas \
    HISTORY_WINDOW=24 \
    STALL_MAX_TURNS=24

EXPOSE 8000

# Las migraciones se aplican al arranque (lifespan de app/main.py).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4); sys.exit(0 if r.status==200 else 1)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
