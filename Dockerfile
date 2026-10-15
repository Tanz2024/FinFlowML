FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
RUN groupadd --system finflow && useradd --system --gid finflow --home-dir /app finflow
COPY requirements-runtime.txt /app/requirements-runtime.txt
RUN pip install --no-cache-dir -r /app/requirements-runtime.txt
COPY backend /app/backend
COPY ml /app/ml
RUN mkdir -p /data/uploads && chown -R finflow:finflow /app /data
USER finflow
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
