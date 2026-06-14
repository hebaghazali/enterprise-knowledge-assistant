FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so this layer is cached independently of app code changes
COPY requirements.txt .
RUN pip install --upgrade pip --no-cache-dir && \
    pip install --no-cache-dir \
        --timeout 120 \
        --retries 5 \
        -r requirements.txt

COPY pyproject.toml .
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
