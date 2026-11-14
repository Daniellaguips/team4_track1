# Harbor environment: pallets/click pinned at release 8.5.1 (feature absent).
# Every task package copies this file to environment/Dockerfile unchanged.
# The build leaves /app as a git working tree at base_commit, so solve.sh and
# the test patch apply with `git apply`.
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates bash less \
    && rm -rf /var/lib/apt/lists/*

ARG BASE_COMMIT=cf19179e8e2fd54c601378cec9e0d21bb12b6fb1
WORKDIR /app
RUN git init --quiet \
    && git remote add origin https://github.com/pallets/click.git \
    && git fetch --quiet --depth 1 origin ${BASE_COMMIT} \
    && git checkout --quiet FETCH_HEAD \
    && git config user.email bench@local && git config user.name bench \
    && git config core.autocrlf false \
    && git config --global --add safe.directory /app \
    && git remote remove origin \
    && test "$(git rev-parse HEAD)" = "${BASE_COMMIT}"

RUN python -m venv /app/.venv \
    && /app/.venv/bin/pip install -e . "pytest==8.4.2" \
    && /app/.venv/bin/python -c "import click; print('click', click.__version__)"
ENV PATH="/app/.venv/bin:${PATH}"
CMD ["/bin/bash"]
