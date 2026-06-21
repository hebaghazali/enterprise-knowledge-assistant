FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip --no-cache-dir

# Install torch CPU-only with platform-specific handling so the build stays fast on
# all architectures:
#   amd64 — the default PyPI wheel bundles CUDA (~2 GB) and caused build timeouts
#            (see commit 88cc39c); the PyTorch CPU index serves a small ~200 MB wheel.
#   arm64  — the PyTorch CPU index has no aarch64 wheels; the PyPI wheel for this arch
#            has no CUDA binaries, so it is already CPU-only and similarly sized.
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "amd64" ]; then \
        pip install --no-cache-dir --timeout 120 --retries 5 \
            --extra-index-url https://download.pytorch.org/whl/cpu \
            "torch==2.4.1+cpu"; \
    else \
        pip install --no-cache-dir --timeout 120 --retries 5 \
            "torch>=2.4.1,<3.0.0"; \
    fi

# Install remaining dependencies (torch already satisfied, pip will skip it)
RUN pip install --no-cache-dir \
        --timeout 120 \
        --retries 5 \
        -r requirements.txt

COPY pyproject.toml .
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
