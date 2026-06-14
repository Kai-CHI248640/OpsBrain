# OpsBrain — AI 网络运维平台

面向中小企业的开源网络运维 Agent 框架，自动发现网络拓扑、智能分析故障、主动备份配置。

## 快速开始

### 环境要求

- Node.js >= 18
- Python >= 3.11
- Git

### Windows 部署（推荐开发）

```powershell
# 1. 克隆仓库
git clone https://github.com/Kai-CHI248640/OpsBrain.git
cd OpsBrain

# 2. 一键初始化（创建虚拟环境 + 安装所有依赖）
npm run init

# 3. 启动开发环境（前端 + 后端）
npm run dev

# 4. 访问
# 前端: http://localhost:3000
# API:  http://localhost:8000/docs
```

### Linux/Mac 部署

```bash
# 1. 克隆仓库
git clone https://github.com/Kai-CHI248640/OpsBrain.git
cd OpsBrain

# 2. 一键初始化（创建虚拟环境 + 安装所有依赖）
npm run init

# 3. 启动
npm run dev
```

### Docker 部署（生产环境）

```bash
cd oobm-topology
docker compose up -d

# 访问
# 前端: http://localhost
# API:  http://localhost/opsbrain/api/v1/auth/setup-required
```

## 项目结构

```
opsbrain/
├── package.json              # 根 package.json（npm 部署入口）
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
│   │   ├── platform_info.py  # 跨平台系统信息工具
│   │   └── requirements.txt
│   └── nginx/                # Nginx 反向代理
├── oobm-topology/            # OOBM 拓扑采集引擎
└── docs/                     # 设计文档
```

## 核心功能

- **4 种网络发现模式** — 种子设备（LLDP/CDP）、主机嗅探（ARP/SNMP）、串口服务器（Console）、Excel 导入
- **交互式拓扑图** — Vue 3 + vis-network，拖拽缩放，点击查看设备详情
- **AI Agent 运维助手** — LLM 驱动的自然语言交互，支持设备 SSH 操作、配置备份、故障分析
- **知识库管理** — 配置模板存储，支持 CSV/XLSX 导入
- **飞书集成** — 群聊消息自动路由到 Agent 处理

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

| 变量 | Windows 默认值 | Linux 默认值 | 说明 |
|------|---------------|-------------|------|
| `OPSBRAIN_JWT_SECRET` | change-me-in-production | 同左 | JWT 密钥 |
| `OPSBRAIN_HOME` | ~/.opsbrain | /var/lib/opsbrain | 数据目录 |
| `OPSBRAIN_LOG_FORMAT` | json | 同左 | 日志格式 |

## 平台支持

| 平台 | 状态 |
|------|------|
| Windows | ✅ 支持 |
| Linux | 🔄 计划中 |
| macOS | 🔄 计划中 |

## 更新日志

### v3.0.0 (2026-06-14)

**Windows npm 化 + 跨平台适配**

- 跨平台系统信息工具 `platform_info.py`（CPU/内存/磁盘/网络/子网检测）
- 修复所有 Linux 系统调用为 Windows 兼容实现（`/proc/*`、`os.statvfs`、`hostname -I`）
- 统一所有默认路径为跨平台（`~/.opsbrain` on Windows，`/var/lib/opsbrain` on Linux）
- 局域网嗅探扫描范围扩展到 256 个 IP，支持 HTTP/HTTPS/SNMP 端口检测
- 拓扑图设备间连线生成（星形拓扑：设备→网关）
- 拓扑图设备图标按类型显示（路由器🌐、交换机🔀、防火墙🛡️、服务器🖥️、AP📶、未知❓）
- 拓扑图背景色和连线颜色适配白天/夜间模式
- API 管理支持 7 个厂商（OpenAI/DeepSeek/SiliconFlow/Anthropic/MiMo/Ollama/自定义）
- 各模型上下文窗口和输出限制配置
- 知识库下载模板功能
- 去掉 Docker 相关字段，前端适配 npm 版本

## License

BSL 1.1 → MIT (2029-05-27) © zhangxiangyue
