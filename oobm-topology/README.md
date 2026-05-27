# OpsBrain — OOBM 网络拓扑自动发现

通过串口服务器 **自动发现企业网络拓扑**，无需登录每一台设备。

[![Docker](https://img.shields.io/badge/Docker-Containerized-blue?logo=docker)](https://docs.docker.com/compose/)
[![Python](https://img.shields.io/badge/Python-3.12-brightgreen?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 核心概念

运维人员将所有网络设备的 **Console 口** 接入串口服务器，Agent 通过 SSH 连入串口服务器各端口，直接与设备 Console 交互（**带外管理**），自动采集 LLDP/CDP/ARP/MAC 等信息，等待全量数据汇聚后生成拓扑关系图。

**为什么需要等待？**
- 设备 A 说自己的 `gi1/0/1` 口连着 B
- 但端口号需要 B 自己来说
- 只有等 **A 和 B 都采集完**才能双向确认

```
Phase 1: Excel → 设备清单
       ↓
Phase 2: SSH Console → 采集 (Worker N 并行)
       ↓
Phase 3: 等待收敛 ← 新发现设备继续采 ← 最多 3 轮
       ↓
Phase 4: 双向关联 LLDP 端口
       ↓
Phase 5: 输出拓扑 (JSON / Mermaid / Graphviz)
```

---

## 架构

```
┌──────────────────────────────────────────────────────────┐
│                    OpsBrain OOBM                          │
├──────────────┬─────────────────────┬─────────────────────┤
│              │                     │                     │
│  inventory/  │    collector/       │    topology/        │
│  Excel 加载   │    SSH 采集引擎      │    关联 + 渲染       │
│  模型校验     │    Worker 池         │    端口确认          │
│  JSON 输出   │    重试+退避          │    终端发现          │
│              │    增量发现          │    差异对比          │
└──────────────┴─────────────────────┴─────────────────────┘
```

### 模块结构

```
src/opsbrain_oobm/
├── cli.py              ← CLI 入口（opsbrain-oobm 命令）
├── config.py           ← 12-Factor 配置（环境变量优先）
├── logging_setup.py    ← 结构化 JSON 日志
│
├── inventory/          ← 设备清单管理
│   ├── models.py       ← Pydantic 模型
│   ├── loader.py       ← Excel 解析器
│   ├── validator.py    ← 校验器
│   └── commands.py     ← 厂商命令注册表
│
├── collector/          ← SSH 采集引擎
│   ├── session.py      ← SSH 会话管理
│   ├── engine.py       ← 采集引擎
│   └── pool.py         ← Worker 池
│
├── parser/             ← CLI 输出解析
│   ├── engine.py       ← 解析引擎
│   └── textfsm_templates/  ← TextFSM 模板
│
├── topology/           ← 拓扑构建
│   ├── builder.py      ← 拓扑构建器
│   ├── linker.py       ← 链路确认引擎
│   ├── renderer.py     ← 渲染器
│   └── diff.py         ← 差异比较
│
└── orchestrator/       ← 流程编排
    ├── pipeline.py     ← Pipeline 编排器
    └── state_machine.py ← 状态机
```

---

## 快速开始

### 1. 准备

```bash
# 克隆项目
cd opsbrain/oobm-topology

# 初始化
make init

# 编辑配置
vi .env
```

### 2. 准备设备清单

将设备信息填入 `inventory/device-inventory.xlsx`，参考以下格式：

| device_name | vendor | console_ip | console_port | username | password | role |
|------------|--------|------------|-------------|---------|---------|------|
| Core-SW-01 | cisco | 10.0.0.100 | 2001 | admin | P@ssw0rd | core |
| Dist-SW-01 | cisco | 10.0.0.100 | 2002 | admin | P@ssw0rd | distribution |
| ACC-SW-01 | h3c | 10.0.0.100 | 2003 | admin | P@ssw0rd | access |

### 3. 运行

```bash
# 构建镜像
make build

# 加载设备清单
make inventory-load

# 全量运行
make run

# 或分步执行：
make run-collect     # 仅采集
make run-topology    # 仅拓扑构建
```

### 4. 查看结果

```bash
# 拓扑 JSON
cat data/topology/topology.json

# Mermaid 格式（可嵌入飞书文档）
cat data/topology/topology.mmd

# Graphviz DOT
cat data/topology/topology.dot
dot -Tpng data/topology/topology.dot -o topology.png  # 渲染为图片
```

---

## 支持的厂商与命令

| 厂商 | LLDP | CDP | ARP | MAC | 路由 | 接口 |
|------|------|-----|-----|-----|------|------|
| Cisco IOS | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Cisco NX-OS | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 华为 VRP | ✓ | - | ✓ | ✓ | ✓ | ✓ |
| H3C Comware | ✓ | - | ✓ | ✓ | ✓ | ✓ |
| Juniper JunOS | ✓ | - | ✓ | ✓ | ✓ | ✓ |
| FortiGate | ✓ | - | ✓ | - | ✓ | ✓ |
| 锐捷 | ✓ | - | ✓ | ✓ | ✓ | ✓ |

---

## 模式说明

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `full` | 全量：加载清单 → 采集 → 拓扑 | 首次运行 |
| `collect` | 仅采集，不构建拓扑 | 分步调试 |
| `topology` | 仅基于已有采集数据构建拓扑 | 重新出图 |
| `incremental` | 增量：只采新设备 + 拓扑对比 | 日常巡检 |

---

## 架构决策

| 决策 | 选择 | 理由 |
|------|------|------|
| SSH 库 | paramiko | 同步模式，适合 CLI expect 交互 |
| 配置管理 | pydantic-settings | 12-Factor，env 优先可覆盖 |
| CLI 输出解析 | TextFSM + 正则回退 | 行业标准，netdevops 生态成熟 |
| 并发模型 | threading.WorkerPool | 串口是阻塞 I/O，同步线程合理 |
| 日志格式 | JSON stdout | Docker 标准，可 log aggregation |
| 链路确认 | 双向匹配 | LLDP 有向 → 无向确认，防假链路 |
| 等待机制 | 多轮收敛 | LLDP 可能发现新设备 |
| 持久化 | JSON 文件 | 简单可靠，无需数据库 |
| 部署 | Docker Compose | 单机足够，复杂度低 |

---

## 安全

- **只读操作**：只执行 `show/display` 命令，不写配置
- **密码管理**：支持环境变量引用 `${VAR_NAME}`，不强制 Excel 明文
- **网络隔离**：采集器通过单独网桥连接串口服务器
- **会话隔离**：每台设备独立 SSH 连接，完成后断开

---

## License

MIT
