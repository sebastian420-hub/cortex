# Cortex in a container: the project you mount at /work is the only thing the agent can reach
# on disk by default (see docs/SECURITY.md for what a container does and does not isolate).
#
#   docker build -t cortex .
#   docker run --rm -it -v "$PWD":/work -e OPENROUTER_API_KEY cortex

# Pinned by digest so a rebuild gets the same base. To update: pull the tag, copy its digest.
FROM python:3.11-slim-bookworm@sha256:2333bd330d12de02514770b3585cad313644316047cdee24a7acfdece6de6efb

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# git and ripgrep are used by the agent's tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Install the package from source (the base install, no optional extras)
WORKDIR /opt/cortex
COPY pyproject.toml setup.py README.md LICENSE ./
COPY cortex ./cortex
RUN pip install .

# Run as an ordinary user, in the mounted project
RUN useradd -m -u 1000 cortex && mkdir /work && chown cortex:cortex /work
USER cortex
WORKDIR /work

ENTRYPOINT ["cortex"]
CMD ["--help"]

LABEL org.opencontainers.image.title="Cortex" \
      org.opencontainers.image.description="A terminal coding agent" \
      org.opencontainers.image.source="https://github.com/sebastian420-hub/cortex" \
      org.opencontainers.image.licenses="MIT"
