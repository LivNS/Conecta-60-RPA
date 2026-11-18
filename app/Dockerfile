FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src \
    DATABASE_PATH=/app/dados/alertas.db DADOS_INICIAIS=/app/dados_iniciais/alertas_publicados.json
WORKDIR /app
RUN pip install --no-cache-dir "fastapi>=0.110" "uvicorn>=0.29" "jinja2>=3.1" "python-multipart>=0.0.9" \
    && useradd --create-home --uid 1001 appuser && mkdir -p /app/dados && chown appuser /app/dados
COPY src ./src
COPY dados_iniciais ./dados_iniciais
USER appuser
EXPOSE 8000
# PORT é definido pela plataforma (o Render usa 10000); localmente cai em 8000
CMD ["sh", "-c", "uvicorn app_alertas.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
