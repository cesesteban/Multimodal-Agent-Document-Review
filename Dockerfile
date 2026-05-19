# --- Stage 1: Dependency builder and cacher ---
FROM python:3.11-slim as builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# --- Stage 2: Clean and secure runtime stage ---
FROM python:3.11-slim as runtime

WORKDIR /workspace

# Create secure system group and user to run as non-root (security hardening)
RUN groupadd -g 1001 appgroup && useradd -r -u 1001 -g appgroup appuser

# Copy installed packages from the builder stage
COPY --from=builder /root/.local /home/appuser/.local
COPY ./app ./app
COPY ./main.py .

# Operational environment variables
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Adjust directory ownership and switch execution context to non-root user
RUN chown -R appuser:appgroup /workspace
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
