FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY presets ./presets
RUN pip install --no-cache-dir .

ENTRYPOINT ["replay"]
