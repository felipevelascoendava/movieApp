FROM python:3.10-slim

ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="Movie App API" \
      org.opencontainers.image.version="${APP_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./

# Manual image configuration: run the service as an unprivileged user.
RUN useradd --system --no-create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

ENTRYPOINT ["python", "app.py"]
