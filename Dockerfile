# Build multi-etapa: las dependencias se instalan en un entorno virtual que se
# copia a una imagen final sin toolchain de compilacion.
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt


FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# La API no ejecuta como root.
RUN useradd --create-home --uid 1000 signmed

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=signmed:signmed app ./app
COPY --chown=signmed:signmed artifacts ./artifacts

RUN mkdir -p /app/uploads/documents && chown -R signmed:signmed /app/uploads

USER signmed

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
