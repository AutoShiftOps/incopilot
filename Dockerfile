FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY firstsignal ./firstsignal
RUN pip install --no-cache-dir . && useradd --create-home --uid 10001 firstsignal

USER firstsignal
WORKDIR /work
ENTRYPOINT ["firstsignal"]
CMD ["--help"]
