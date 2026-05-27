# OpsBrain — AI 网络运维平台

面向中小企业的开源网络运维 Agent 框架，自动发现网络拓扑、智能分析故障、主动备份配置。

[![Python](https://img.shields.io/badge/Python-3.12+-brightgreen?logo=python)](https://python.org)
[![Vue 3](https://img.shields.io/badge/Vue-3.x-brightgreen?logo=vue.js)](https://vuejs.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)](https://docs.docker.com/compose/)
[![License](https://img.shields.io/badge/License-BSL_1.1-blue)](LICENSE)

---

## 核心能力

- 🔍 **4 种网络发现模式** — 种子设备（LLDP/CDP）、主机嗅探（ARP/SNMP）、串口服务器（Console）、Excel 表格导入
- 🗺️ **交互式拓扑图** — Vue 3 + Canvas 实现，拖拽缩放，点击查看设备详情
- 🤖 **AI Agent 运维助手** — LLM 驱动的自然语言交互，支持设备 SSH 操作、配置备份、故障分析
- 🚀 **Docker Compose 一键部署** — Web 前端 + FastAPI 后端 + Nginx，开箱即用
- 📱 **飞书 Bot 集成** — 移动端查看拓扑、接收告警

---

## 架构总览

```
┌──────────────────────────────────────────┐
│               浏览器 (Vue 3 SPA)           │
│     控制台 / 拓扑图 / 知识库 / Agent 对话  │
└────────────────┬─────────────────────────┘
                 │ HTTP (nginx)
┌────────────────▼─────────────────────────┐
│              FastAPI 后端                  │
│  设备管理 | 拓扑引擎 | 配置中心 | AI Agent │
└────────────────┬─────────────────────────┘
                 │
     ┌───────────┼───────────┬─────────────┐
     ▼           ▼           ▼             ▼
 ┌───────┐  ┌───────┐  ┌────────┐  ┌──────────┐
 │种子发现│  │主机嗅探│  │Console │  │Excel导入  │
 │LLDP/CDP│  │ARP/SNMP│  │Server │  │台账导入   │
 └───────┘  └───────┘  └────────┘  └──────────┘
```

---

## 项目结构

```
opsbrain/
├── web/                     # Web 前后端
│   ├── frontend/            # Vue 3 + Vite
│   │   ├── src/
│   │   │   ├── views/       # Dashboard / 拓扑 / 知识库 / Agent / 设置
│   │   │   ├── components/  # TopologyGraph / AgentPanel / AppLayout
│   │   │   └── stores/      # Pinia 状态管理
│   │   └── index.html
│   ├── backend/             # FastAPI
│   │   ├── app/
│   │   │   ├── routes/      # auth / dashboard / topology / agents / settings
│   │   │   ├── discovery/   # 种子发现 / 串口采集
│   │   │   ├── scanner/     # 主机扫描 / Console 采集器
│   │   │   └── models/      # Pydantic + SQLAlchemy
│   │   └── Dockerfile
│   └── nginx/               # Nginx 反向代理
│       └── opsbrain.conf
├── oobm-topology/           # OOBM 拓扑采集 Python 包
│   ├── src/opsbrain_oobm/
│   │   ├── collector/       # SSH 采集引擎
│   │   ├── parser/          # CLI 输出解析 (TextFSM)
│   │   ├── topology/        # 拓扑构建 + 双向端口确认
│   │   └── orchestrator/    # 流程编排 Pipeline
│   └── docker-compose.yml
├── agent/                   # AI Agent 定义
│   └── oobm-topology-skill.md
├── docs/                    # 设计文档
│   └── opsbrain-v2-design.md
└── README.md
```

## 四种网络发现模式

| 模式 | 原理 | 适用场景 |
|------|------|---------|
| 🌱 **种子发现** | SSH 登录核心设备，LLDP/CDP 递归发现全网 | 有设备密码，要准确拓扑 |
| 🔭 **主机嗅探** | ARP + TCP + SNMP 扫描本地子网 | 无凭证，想知道网上有什么 |
| 🔌 **Console Server** | 通过串口服务器 Console 口访问设备 | 带外管理，网络故障时也能用 |
| 📋 **Excel 导入** | 上传设备台账，自动验证可达性 | 已有台账，直接导入 |

四种模式可**任意组合**——先导入 Excel 台账，再用种子发现补全 LLDP 链路。

## 支持的厂商

| 厂商 | LLDP | CDP | ARP | MAC | 路由 | 接口 |
|------|------|-----|-----|-----|------|------|
| Cisco IOS/NX-OS | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 华为 VRP | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| H3C Comware | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| Juniper JunOS | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| FortiGate | ✅ | — | ✅ | — | ✅ | ✅ |
| 锐捷 | ✅ | — | ✅ | ✅ | ✅ | ✅ |

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/zhangxiangyue/opsbrain.git
cd opsbrain

# 2. 启动 Web 平台
cd web
docker compose up -d

# 3. 访问
# 前端: http://localhost:3000
# API:  http://localhost:8000/docs

# 4. (可选) 运行 OOBM 拓扑采集
cd oobm-topology
make init && make run
```

## 技术栈

| 层 | 技术 | 说明 |
|---|------|------|
| 前端 | Vue 3 + Vite + Pinia | SPA 单页应用 |
| 拓扑图 | Canvas 自研渲染 | 拖拽缩放，交互式 |
| 后端 | FastAPI + SQLAlchemy | 异步 API，Swagger 文档 |
| 数据库 | SQLite | 轻量，零运维 |
| AI Agent | LLM + Tool Calling | 自然语言运维 |
| 部署 | Docker Compose | 单机一键部署 |
| SSH | paramiko | 设备命令行采集 |

---

## License

BSL 1.1 → MIT (2029-05-27) © zhangxiangyue
