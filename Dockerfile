FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY incopilot ./incopilot
RUN pip install --no-cache-dir . && useradd --create-home --uid 10001 incopilot

USER incopilot
WORKDIR /work
ENTRYPOINT ["incopilot"]
CMD ["--help"]
