FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# [UNCONFIRMED: D6] supercronic runs the fetcher schedule in the `fetcher` compose service
# (see the crontab file). Pinned release, verified by SHA-256 before it is installed.
ARG TARGETARCH
ARG SUPERCRONIC_VERSION=v0.2.49
ARG SUPERCRONIC_SHA256_AMD64=a53ae236602c7338aba3fbaff40bda6300eae3b9fedb8261eb06cfe3724430c1
ARG SUPERCRONIC_SHA256_ARM64=02aa0cb229ba09050cba6638059dadb9eedc2276632ea43d6a57a2f8c1629dd5
RUN set -eu; \
    arch="${TARGETARCH:-$(dpkg --print-architecture)}"; \
    case "$arch" in \
      amd64) sha256="$SUPERCRONIC_SHA256_AMD64" ;; \
      arm64) sha256="$SUPERCRONIC_SHA256_ARM64" ;; \
      *) echo "supercronic: unsupported architecture $arch" >&2; exit 1 ;; \
    esac; \
    url="https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-${arch}"; \
    python -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" \
      "$url" /tmp/supercronic; \
    echo "${sha256}  /tmp/supercronic" | sha256sum -c -; \
    install -m 0755 /tmp/supercronic /usr/local/bin/supercronic; \
    rm /tmp/supercronic

WORKDIR /app

# Dependencies first (from the lockfile) so source edits keep this layer cached.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY crontab ./crontab

EXPOSE 8000

# Apply migrations so the schema is current on every boot, then serve the API.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn --factory src.main:create_app --host 0.0.0.0 --port 8000"]
