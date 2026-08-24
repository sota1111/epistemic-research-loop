FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 10001 erl
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
USER erl
ENTRYPOINT ["erlctl"]
