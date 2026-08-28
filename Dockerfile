# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.12
ARG NODE_VERSION=20.20.2

# Keep the Node toolchain separate so the small runtime image does not inherit it.
FROM node:${NODE_VERSION}-bookworm-slim AS node-toolchain

FROM python:${PYTHON_VERSION}-slim AS development

ARG UV_VERSION=0.11.32
ARG CLAUDE_CODE_VERSION=2.1.241
ARG CODEX_VERSION=0.149.1
ARG ZAI_CLI_VERSION=0.3.5

COPY --from=node-toolchain /usr/local/ /usr/local/

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        curl \
        git \
        jq \
        make \
        procps \
        ripgrep \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir "uv==${UV_VERSION}" \
    && npm install --global \
        "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
        "@openai/codex@${CODEX_VERSION}" \
        "@guizmo-ai/zai-cli@${ZAI_CLI_VERSION}" \
    && npm cache clean --force \
    && useradd --create-home --uid 1000 --shell /bin/bash vscode \
    && install -d --owner=vscode --group=vscode /workspace /home/vscode/.local/bin

ENV PATH="/workspace/.venv/bin:/home/vscode/.local/bin:${PATH}" \
    UV_LINK_MODE=copy \
    ZAI_BASE_URL=https://api.z.ai/api/coding/paas/v4 \
    ZAI_MODEL=glm-5.3

WORKDIR /workspace

# Cache the complete development environment. The source tree is bind-mounted by
# the dev container, so secrets such as .env are never copied into the image.
COPY --chown=vscode:vscode pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --extra dev --extra llm --extra solver \
    && chown -R vscode:vscode /workspace/.venv

COPY --chown=vscode:vscode scripts/glm-cli /home/vscode/.local/bin/glm
RUN chmod 0755 /home/vscode/.local/bin/glm

USER vscode
CMD ["bash"]


FROM python:${PYTHON_VERSION}-slim AS runtime

RUN useradd --create-home --uid 10001 erl
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
USER erl
ENTRYPOINT ["erlctl"]
