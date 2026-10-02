# syntax=docker/dockerfile:1
# Portable backend image: same image for API (uvicorn) and worker (celery).

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app
WORKDIR /app

FROM base AS deps
COPY pyproject.toml ./
# Install only third-party dependencies (read from pyproject) for layer caching.
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install --prefix=/install -r /tmp/requirements.txt

FROM base AS runtime
RUN groupadd --system app && useradd --system --gid app --home /app app
COPY --from=deps /install /usr/local
COPY --chown=app:app . .
RUN chmod +x scripts/entrypoint.sh
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/v1/health', timeout=3)" || exit 1
ENTRYPOINT ["scripts/entrypoint.sh"]
CMD ["api"]
