# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first: this layer is cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini gunicorn.conf.py ./
COPY alembic ./alembic
COPY app ./app

# Never run as root.
RUN useradd --create-home --uid 10001 bearly && chown -R bearly:bearly /app
USER bearly

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4).status==200 else 1)"

# Migrations run before the server starts, so a deploy can never serve against
# a schema older than the code expects.
CMD ["sh", "-c", "alembic upgrade head && exec gunicorn -c gunicorn.conf.py app.main:app"]
