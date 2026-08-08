# syntax=docker/dockerfile:1

# The egress proxy re-terminates TLS, so the build needs its CA to verify HTTPS.
# scripts/docker-bootstrap.sh copies the bundle next to this Dockerfile as ca-bundle.crt.
ARG PYTHON_IMAGE=python:3.12-slim

FROM ${PYTHON_IMAGE} AS builder

COPY ca-bundle.crt /usr/local/share/ca-certificates/ccr-proxy.crt
ENV PIP_CERT=/usr/local/share/ca-certificates/ccr-proxy.crt \
    SSL_CERT_FILE=/usr/local/share/ca-certificates/ccr-proxy.crt \
    REQUESTS_CA_BUNDLE=/usr/local/share/ca-certificates/ccr-proxy.crt

WORKDIR /build
COPY app/requirements.txt .
# BuildKit cache mount keeps the wheel cache across rebuilds in this session.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r requirements.txt

FROM ${PYTHON_IMAGE} AS runtime

COPY ca-bundle.crt /usr/local/share/ca-certificates/ccr-proxy.crt
ENV SSL_CERT_FILE=/usr/local/share/ca-certificates/ccr-proxy.crt \
    REQUESTS_CA_BUNDLE=/usr/local/share/ca-certificates/ccr-proxy.crt \
    PYTHONUNBUFFERED=1

COPY --from=builder /install /usr/local
WORKDIR /srv
COPY app/ /srv/

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
