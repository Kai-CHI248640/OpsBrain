# =============================================================================
# OpsBrain OOBM — 单阶段构建镜像
# =============================================================================
# 与 Docker Compose 配合使用，支持 collector 和 topology-builder 两种角色
# =============================================================================

FROM python:3.12-slim AS base

# ── 系统依赖 ───────────────────────────────────────────────────────────────
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
        openssh-client \
        sshpass \
        netcat-openbsd \
        libssl-dev \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/share/doc /usr/share/man

# ── 应用用户 ───────────────────────────────────────────────────────────────
ARG APP_UID=1001
ARG APP_GID=1001
RUN groupadd --gid ${APP_GID} opsbrain && \
    useradd --uid ${APP_UID} --gid ${APP_GID} \
            --create-home --shell /sbin/nologin opsbrain

# ── Python 依赖 ────────────────────────────────────────────────────────────
COPY --link pyproject.toml /tmp/
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    cd /tmp && pip install --no-cache-dir . && \
    rm -rf /tmp/*

# ── 应用代码 ───────────────────────────────────────────────────────────────
COPY --link src/opsbrain_oobm/ /usr/local/lib/python3.12/site-packages/opsbrain_oobm/
COPY --link scripts/ /usr/local/share/opsbrain/scripts/

# ── 运行时目录 ─────────────────────────────────────────────────────────────
ENV OPSBRAIN_HOME=/var/lib/opsbrain
ENV OPSBRAIN_CONFIG=/etc/opsbrain

RUN mkdir -p ${OPSBRAIN_HOME}/{inventory,collected,parsed,topology} \
             ${OPSBRAIN_CONFIG} && \
    chown -R opsbrain:opsbrain ${OPSBRAIN_HOME} ${OPSBRAIN_CONFIG}

# ── Entrypoint ─────────────────────────────────────────────────────────────
COPY --chmod=755 <<"SHELL" /usr/local/bin/entrypoint.sh
#!/bin/bash
set -euo pipefail

# ── Signal forwarding ───────────────────────────────────────────────
trap 'echo "[ENTRYPOINT] SIGTERM → forwarding"; kill -TERM $PID 2>/dev/null; wait $PID; exit 143' SIGTERM
trap 'echo "[ENTRYPOINT] SIGINT → forwarding";  kill -INT  $PID 2>/dev/null; wait $PID; exit 130' SIGINT

# ── Configuration ───────────────────────────────────────────────────
if [ -f "${OPSBRAIN_CONFIG}/config.yml" ]; then
    echo "[ENTRYPOINT] Loading config file"
fi

echo "[ENTRYPOINT] Starting: opsbrain-oobm $@"
exec opsbrain-oobm "$@" &
PID=$!
wait $PID
SHELL

RUN chmod 755 /usr/local/bin/entrypoint.sh

USER opsbrain:opsbrain
WORKDIR ${OPSBRAIN_HOME}

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["run", "--pipeline", "full"]

# ── Health ──────────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD nc -z 127.0.0.1 9100 || exit 1

LABEL org.opencontainers.image.title="OpsBrain OOBM Topology"
LABEL org.opencontainers.image.description="Network topology auto-discovery via OOBM console server"
LABEL org.opencontainers.image.version="0.1.0"
