# OpsBrain — AI Network Operations Platform

[![License](https://img.shields.io/badge/license-BSL%201.1-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/Kai-CHI248640/OpsBrain)](https://github.com/Kai-CHI248640/OpsBrain/releases)

[中文](README_CN.md) | **English**

An open-source network operations Agent framework for SMBs. Automatically discovers network topology, intelligently analyzes faults, and proactively backs up configurations.

## Quick Start

### Requirements

- Node.js >= 18
- Python >= 3.11
- Git

### Windows Deployment

```powershell
# 1. Clone repository
git clone https://github.com/Kai-CHI248640/OpsBrain.git
cd OpsBrain

# 2. One-click init (create venv + install all dependencies)
npm run init

# 3. Start development (frontend + backend)
npm run dev

# 4. Access
# Frontend: http://localhost:3000
# API:      http://localhost:8000/docs
```

### Linux / macOS Deployment

```bash
# 1. Clone repository
git clone https://github.com/Kai-CHI248640/OpsBrain.git
cd OpsBrain

# 2. One-click init (create venv + install all dependencies)
npm run init

# 3. Start
npm run dev
```

## Project Structure

```
opsbrain/
├── package.json              # Root package.json (npm entry point)
├── scripts/                  # Cross-platform scripts
│   ├── init.js               # Project initialization
│   ├── run-backend.js        # Start backend
│   └── install-python.js     # Install Python dependencies
├── web/
│   ├── frontend/             # Vue 3 + Vite + Element Plus
│   │   ├── src/
│   │   │   ├── views/        # Dashboard / Topology / Knowledge Base / Settings
│   │   │   ├── components/   # AppLayout / AgentPanel / TopologyGraph
│   │   │   ├── stores/       # Pinia state management
│   │   │   └── assets/       # Styles / Icons
│   │   └── package.json
│   └── backend/              # FastAPI backend
│       ├── app/
│       │   ├── routes/       # API routes
│       │   ├── discovery/    # Seed discovery
│       │   ├── scanner/      # Host scanning
│       │   └── models.py     # Data models
│       ├── platform_info.py  # Cross-platform system info utilities
│       └── requirements.txt
├── oobm-topology/            # OOBM topology collection engine
└── docs/                     # Design documents
```

## Core Features

- **4 Network Discovery Modes** — Seed devices (LLDP/CDP), LAN scan (ARP/SNMP), Serial Server (Console), Excel import
- **Interactive Topology Map** — Vue 3 + vis-network, drag & zoom, click to view device details
- **AI Agent Assistant** — LLM-driven natural language interaction, supports SSH operations, config backup, fault analysis
- **Knowledge Base** — Configuration template storage, CSV/XLSX import support
- **Feishu Integration** — Group chat messages auto-routed to Agent processing

## Tech Stack

| Layer | Technology | Description |
|-------|------------|-------------|
| Frontend | Vue 3 + Vite + Element Plus | SPA single-page application |
| Topology | vis-network | Interactive topology rendering |
| Backend | FastAPI + SQLAlchemy | Async API |
| Database | SQLite | Lightweight, zero maintenance |
| AI Agent | LLM + Function Calling | Natural language operations |
| SSH | paramiko | Device CLI data collection |

## Environment Variables

| Variable | Windows Default | Linux Default | Description |
|----------|----------------|---------------|-------------|
| `OPSBRAIN_JWT_SECRET` | change-me-in-production | Same | JWT secret key |
| `OPSBRAIN_HOME` | ~/.opsbrain | /var/lib/opsbrain | Data directory |
| `OPSBRAIN_LOG_FORMAT` | json | Same | Log format |

## Platform Support

| Platform | Status |
|----------|--------|
| Windows | ✅ Supported |
| Linux | ✅ Supported |
| macOS | ✅ Supported |

## Changelog

### v3.0.2 (2026-06-17)

**SNMP/LLDP/CDP 拓扑发现集成 + 工作流功能**

- 新增 `/api/v1/topology/snmp-discover` 接口，支持基于 SNMP 的拓扑发现
- 集成 LLDP 和 CDP 协议支持，可用于企业内网设备发现
- 新增 `scanner/snmp_lldp.py` 模块，封装 SNMP 查询逻辑
- 支持递归发现（最大深度可配置）
- 自动创建 Subagent 绑定到发现的拓扑
- **工作流功能**: 参考 ITOps Agent Platform 实现可视化工作流编排
  - 后端: Workflow/WorkflowExecution 模型 + CRUD API + 执行引擎
  - 前端: 工作流列表页 + 可视化流程设计器 (拖拽式)
  - 支持节点类型: Agent/条件/延迟/开始/结束
  - 支持工作流模板、导入导出、执行记录查看
  - 左侧导航新增"工作流"入口

### v3.0.1 (2026-06-14)

**Cross-platform compatibility + Scan optimization + Init fixes**

- `package.json` scripts now work on Linux/Mac/Windows
- New `scripts/run-backend.js` for cross-platform backend startup
- New `scripts/install-python.js` for cross-platform Python dependency installation
- LAN scan uses concurrent ping detection, filters VPN/WSL virtual adapters
- `npm run init` auto-stops backend + deletes database for one-click reset
- Backend auto-initializes database tables on startup
- Fix missing `__init__.py` preventing backend startup
- Remove Docker deployment content

### v3.0.0 (2026-06-14)

**Windows npm + Cross-platform adaptation**

- Cross-platform system info utilities (`platform_info.py`)
- All Linux system calls adapted for Windows compatibility
- Unified default paths for cross-platform (`~/.opsbrain` on Windows, `/var/lib/opsbrain` on Linux)
- LAN scan expanded to 256 IPs with HTTP/HTTPS/SNMP port detection
- Topology links generation (star topology: device → gateway)
- Device icons by type in topology view
- API management supports 7 vendors
- Knowledge base download template feature

## License

BSL 1.1 → MIT (2029-05-27) © zhangxiangyue
