# ============================================================================
# OpsBrain Web — 多阶段构建
# Stage 1: Node.js 构建前端
# Stage 2: Python 运行后端 + 静态文件
# ============================================================================

# ── Stage 1: Build frontend ──────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /build
COPY frontend/package.json /build/
RUN npm install

COPY frontend/ /build/
RUN npm run build

# ── Stage 2: Python backend ──────────────────────────────────────────────
FROM python:3.12-slim

RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends tini curl && \
    rm -rf /var/lib/apt/lists/*

# ── Python deps ──────────────────────────────────────────────────────────
COPY backend/requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm -rf /tmp/*

# ── Application ──────────────────────────────────────────────────────────
WORKDIR /app
COPY backend/app/ /app/app/

# ── Static files (built frontend) ────────────────────────────────────────
RUN mkdir -p /app/static
COPY --from=frontend-builder /build/dist/ /app/static/

# ── Runtime directories ──────────────────────────────────────────────────
ENV OPSBRAIN_HOME=/var/lib/opsbrain
RUN mkdir -p ${OPSBRAIN_HOME} && \
    useradd --create-home --shell /sbin/nologin opsbrain && \
    chown -R opsbrain:opsbrain /app ${OPSBRAIN_HOME}

USER opsbrain:opsbrain
EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.__init__:app", "--host", "0.0.0.0", "--port", "8000"]
