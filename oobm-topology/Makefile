# =============================================================================
# OpsBrain OOBM — Makefile
# =============================================================================
# Docker 风格开发工具
# =============================================================================

SHELL := /bin/bash

# ── Variables ───────────────────────────────────────────────────────────────
NAME        := opsbrain-oobm
VERSION     := 0.1.0
IMAGE       := opsbrain/$(NAME)
CONTAINER   := opsbrain-oobm
ENV_FILE    := .env
DATA_DIR    := $(PWD)/data
CONFIG_DIR  := $(PWD)/config

# ── Colors ─────────────────────────────────────────────────────────────────
BLUE := \033[34;1m
GREEN := \033[32;1m
YELLOW := \033[33;1m
RESET := \033[0m

.DEFAULT_GOAL := help

# ── Phony ──────────────────────────────────────────────────────────────────
.PHONY: help init build run dev shell clean logs stop status test lint

# ═══════════════════════════════════════════════════════════════════════════
# Targets
# ═══════════════════════════════════════════════════════════════════════════

help: ## 显示帮助信息
	@printf "$(BLUE)━━━ OpsBrain OOBM — Makefile ━━━$(RESET)\n"
	@printf "$(YELLOW)Usage:$(RESET) make <target>\n\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'

# ── Setup ──────────────────────────────────────────────────────────────────

init: ## 初始化项目（创建目录 + 复制 .env）
	@mkdir -p $(DATA_DIR)/{inventory,collected,parsed,topology} config inventory
	@if [ ! -f $(ENV_FILE) ]; then \
		cp .env.example $(ENV_FILE); \
		echo "$(GREEN)✓$(RESET) Created $(ENV_FILE) — Edit with your settings"; \
	else \
		echo "$(YELLOW)•$(RESET) $(ENV_FILE) already exists"; \
	fi
	@echo "$(GREEN)✓$(RESET) Project initialized"

# ── Build ──────────────────────────────────────────────────────────────────

build: ## 构建 Docker 镜像
	docker build -t $(IMAGE):$(VERSION) -t $(IMAGE):latest .
	@echo "$(GREEN)✓$(RESET) Built $(IMAGE):$(VERSION)"

# ── Run ────────────────────────────────────────────────────────────────────

run: ## 运行全流程（docker compose）
	docker compose --env-file $(ENV_FILE) up --build

run-full: ## 运行全量采集+拓扑
	docker compose --env-file $(ENV_FILE) run --rm collector run --pipeline full

run-collect: ## 仅执行采集
	docker compose --env-file $(ENV_FILE) run --rm collector run --pipeline collect

run-topology: ## 仅构建拓扑（基于现有采集数据）
	docker compose --env-file $(ENV_FILE) run --rm topology-builder run --pipeline topology

run-incremental: ## 增量运行
	docker compose --env-file $(ENV_FILE) run --rm collector run --pipeline incremental

# ── Development / Local ────────────────────────────────────────────────────

dev: ## 本地开发模式（不在 Docker 内）
	@echo "$(YELLOW)Running in development mode...$(RESET)"
	@mkdir -p $(DATA_DIR)/{inventory,collected,parsed,topology}
	@export OPSBRAIN_HOME=$(DATA_DIR) && \
	 export OPSBRAIN_CONFIG=$(CONFIG_DIR) && \
	 export OPSBRAIN_LOG_FORMAT=text && \
	 opsbrain-oobm run --pipeline full

shell: ## 进入容器 Shell
	docker compose --env-file $(ENV_FILE) run --rm --entrypoint /bin/bash collector

# ── Inventory ──────────────────────────────────────────────────────────────

inventory-load: ## 加载设备清单
	docker compose --env-file $(ENV_FILE) run --rm collector inventory load --show

inventory-validate: ## 校验设备清单
	docker compose --env-file $(ENV_FILE) run --rm collector inventory load --strict

# ── Service Management ─────────────────────────────────────────────────────

up: ## 启动所有服务
	docker compose --env-file $(ENV_FILE) up -d

down: ## 停止所有服务
	docker compose --env-file $(ENV_FILE) down

logs: ## 查看日志
	docker compose logs -f

status: ## 查看状态
	docker compose ps

stop: ## 停止容器
	docker compose stop

# ── Utilities ──────────────────────────────────────────────────────────────

clean: ## 清理数据目录和 Docker 产物
	@rm -rf $(DATA_DIR)
	@docker compose down -v 2>/dev/null || true
	@echo "$(GREEN)✓$(RESET) Cleaned"

clean-all: clean ## 全清理（包括镜像）
	-docker rmi $(IMAGE):$(VERSION) $(IMAGE):latest 2>/dev/null
	@echo "$(GREEN)✓$(RESET) Full cleanup done"

# ── Testing ────────────────────────────────────────────────────────────────

test: ## 运行测试
	python -m pytest tests/ -v --tb=short

test-coverage: ## 测试并生成覆盖率报告
	python -m pytest tests/ --cov=opsbrain_oobm --cov-report=html

lint: ## 代码检查
	ruff check src/
	mypy src/ --ignore-missing-imports

# ── Version ────────────────────────────────────────────────────────────────

version: ## 显示版本信息
	@echo "$(NAME) v$(VERSION)"
	@python --version 2>&1
	@docker --version 2>&1
