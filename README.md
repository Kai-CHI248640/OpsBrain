# OpsBrain — AI 网络运维平台

面向中小企业的开源网络运维 Agent 框架，自动发现网络拓扑、智能分析故障、主动备份配置。

## 快速开始（Windows）

### 环境要求

- Node.js >= 18
- Python >= 3.11
- Git

### 安装与启动

```powershell
# 1. 克隆仓库
git clone https://github.com/Kai-CHI248640/OpsBrain.git
cd OpsBrain

# 2. 创建 Python 虚拟环境(可选)
python -m venv venv
.\venv\Scripts\activate

# 3. 安装所有依赖（Node + Python）
npm run setup

# 4. 启动开发环境（前端 + 后端）
npm run dev

# 5. 访问
# 前端: http://localhost:3000
# API:  http://localhost:8000/opsbrain/docs
```

首次启动后会进入初始化页面，设置管理员账号即可使用。

## 项目结构

```
opsbrain/
├── package.json              # npm 部署入口
├── web/
│   ├── frontend/             # Vue 3 + Vite + Element Plus
│   │   ├── src/
│   │   │   ├── views/        # 控制台 / 拓扑 / 知识库 / 设置
│   │   │   ├── components/   # AppLayout / AgentPanel / TopologyGraph
│   │   │   ├── stores/       # Pinia 状态管理
│   │   │   └── assets/       # 样式 / 图标
│   │   └── package.json
│   ├── backend/              # FastAPI 后端
│   │   ├── app/
│   │   │   ├── routes/       # API 路由
│   │   │   ├── discovery/    # 种子发现
│   │   │   ├── scanner/      # 主机扫描
│   │   │   └── models.py     # 数据模型
│   │   ├── platform_info.py  # 系统信息工具
│   │   └── requirements.txt
│   └── nginx/                # Nginx 反向代理
├── oobm-topology/            # OOBM 拓扑采集引擎
└── docs/                     # 设计文档
```

## 核心功能

- **4 种网络发现模式** — 种子设备（LLDP/CDP）、局域网嗅探（TCP 端口扫描）、串口服务器（Console）、Excel 导入
- **交互式拓扑图** — Vue 3 + vis-network，设备按类型显示不同图标，支持拖拽缩放
- **AI Agent 运维助手** — LLM 驱动的自然语言交互，通过知识库命令模板 + SSH 执行实现设备运维
- **知识库管理** — 配置模板存储，支持 CSV/XLSX 导入，提供模板下载
- **API 多厂商管理** — 支持 OpenAI/DeepSeek/SiliconFlow/Anthropic/MiMo/Ollama/自定义

## 技术栈

| 层 | 技术 | 说明 |
|---|------|------|
| 前端 | Vue 3 + Vite + Element Plus | SPA 单页应用 |
| 拓扑图 | vis-network | 交互式拓扑渲染 |
| 后端 | FastAPI + SQLAlchemy | 异步 API |
| 数据库 | SQLite | 轻量，零运维 |
| AI Agent | LLM + Function Calling | 自然语言运维 |
| SSH | paramiko | 设备命令行采集 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPSBRAIN_JWT_SECRET` | change-me-in-production | JWT 密钥 |
| `OPSBRAIN_HOME` | ~/.opsbrain | 数据目录 |
| `OPSBRAIN_LOG_FORMAT` | json | 日志格式 |

## 平台支持

| 平台 | 状态 |
|------|------|
| Windows | ✅ v3.0.0 已支持 |
| Linux | 🔄 计划中 |
| macOS | 🔄 计划中 |

## 更新日志

### v3.0.0 (2026-06-14)

**Windows npm 化首发版**

- npm 化改造：支持 `npm run dev` / `npm run setup` 一键启动
- 新增 `platform_info.py` 系统信息工具
- 修复所有 Linux 系统调用为 Windows 兼容实现
- 默认数据目录：`~/.opsbrain`
- 局域网嗅探扫描范围 256 个 IP，支持 HTTP/HTTPS/SNMP 端口检测
- 拓扑图设备图标按类型显示，背景色适配白天/夜间模式
- API 管理支持 7 个厂商，显示模型上下文窗口配置
- 知识库新增下载模板功能
- 去掉 Docker 相关字段

## License

BSL 1.1 → MIT (2029-05-27) © zhangxiangyue
