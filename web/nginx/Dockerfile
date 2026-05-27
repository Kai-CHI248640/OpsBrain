# ============================================================================
# OpsBrain Web — Nginx Reverse Proxy + Frontend
#
# 架构：
#   用户 → http://host/opsbrain/ → Nginx（端口 80）
#       ├── /opsbrain/          → 前端静态文件（index.html）
#       └── /opsbrain/api/      → proxy_pass http://web:8000/api/ （去前缀）
# ============================================================================

# ── Stage 1: Build Vue frontend ──────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /build
COPY frontend/package.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Nginx ───────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# 删除默认配置
RUN rm -f /etc/nginx/conf.d/default.conf

# Nginx 配置
COPY nginx/opsbrain.conf /etc/nginx/conf.d/opsbrain.conf

# 前端构建产物
COPY --from=builder /build/dist/ /usr/share/nginx/html/opsbrain/

# 运行用户
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/opsbrain/ || exit 1
