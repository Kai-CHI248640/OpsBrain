# OpsBrain v2 架构设计

> 面向中小企业的 AI 网络运维 Agent 框架
> 目标：简洁、可落地、可扩展

---

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    浏览器 (Vue 3 SPA)                       │
│          /opsbrain/  → 控制台 / 拓扑 / 知识库               │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP (nginx)
┌──────────────────────▼──────────────────────────────────────┐
│                   FastAPI 后端                              │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ 设备管理  │  │ 拓扑引擎  │  │ 配置中心  │  │ AI Agent  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│       │              │             │              │        │
│  ┌────▼──────────────▼─────────────▼──────────────▼─────┐  │
│  │                 SQLite 数据库                         │  │
│  │    devices / topology_saves / configs / sessions      │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┼────────────┬─────────────┐
          ▼            ▼            ▼             ▼
      ┌────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐
      │ 种子   │ │ 主机    │ │ 串口服务  │ │ Excel    │
      │ 发现   │ │ 网络嗅探 │ │ 器发现   │ │ 导入     │
      └────────┘ └─────────┘ └──────────┘ └──────────┘
```

**架构原则：**
- 少即是多 — 去掉 Commander/Subagent 两层抽象
- 单 Agent，按职责分 Tool 分组
- 四种发现模式并行，用户按需选
- 数据库简单可靠，不用 ORM 迷宫

---

## 二、网络发现：四种模式

### 模式 1：种子设备法（推荐，最准确）

**原理：** 用户提供 1-3 台已知设备（核心交换机/网关路由器），Agent 通过 SSH 登录后利用 LLDP/CDP 递归发现全拓扑。

**流程：**

```
用户输入种子设备信息（IP/用户名/密码/厂商）
        │
        ▼
SSH 登录种子设备
        │
        ├── show lldp neighbors detail
        ├── show cdp neighbors detail  
        ├── show mac address-table
        └── show ip route
        │
        ▼
解析邻居 → 得到新设备（IP/型号/接口）
        │
        ▼
对新设备 SSH 登录（复用凭证，尝试已知密码）
        │
        ▼
递归采集，直到：
  a) 没有新设备发现
  b) 达到最大深度（默认 5 跳）
  c) 达到最大设备数（默认 50 台）
```

**关键技术点：**
- Port-to-port 双向确认：A:gi1/0/1 ↔ B:gi0/2 需要两端都采集才能确认
- 厂商自适应：Cisco→`show lldp neighbors detail`、华为→`display lldp neighbor-information`、Juniper→`show lldp neighbors detail`
- 未知密码处理：新发现的设备如果无法登录，标记为"未确认节点"，拓扑中用虚线显示
- MAC 表辅助：当 LLDP 不可用时，用 MAC 地址表推算连接关系

**优势：**
- 拓扑发现最准确（基于真实 LLDP 数据）
- 无需额外扫描，对生产网络零侵入
- 自动识别设备型号、厂商、接口名

**局限：**
- 依赖 LLDP/CDP 启用（大部分 SME 网络默认开启）
- 要求至少一台设备的 SSH 凭证

---

### 模式 2：主机网络嗅探（独立 Collector）

**原理：** 部署一个独立容器（`network=host` 模式或物理机部署），直接访问主机的网络栈，进行 ARP/Ping/SNMP/TCP 扫描。

**架构：**

```
┌──────────────────────────────────────────┐
│              物理机 / VM                  │
│                                           │
│  ┌────────────────────┐                  │
│  │  opsbrain-collector │  host network   │
│  │  ──── ARP 扫描      │  直接访问      │
│  │  ──── TCP 22/23/80  │  物理网卡      │
│  │  ──── SNMP v2/v3    │                │
│  │  ──── Ping sweep    │                │
│  └─────────┬──────────┘                  │
│            │ HTTP API                     │
│  ┌─────────▼──────────┐                  │
│  │  opsbrain-web       │                  │
│  │  (nginx + FastAPI)  │                  │
│  └────────────────────┘                  │
└──────────────────────────────────────────┘
```

**扫描步骤：**

```
Step 1: 自动检测本机所有网卡子网
        → 读取 /proc/net/fib_trie 或 ip addr
        → 收集 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 等

Step 2: 主机存活性扫描
        → ARP ping（最准确，但需要 root）
        → TCP ping（22/23/80/443，无需 root）
        → ICMP ping（部分网络屏蔽 ICMP）

Step 3: 设备识别
        → TCP 端口开放检测：22(SSH)、23(Telnet)、161(SNMP)
        → SSH 指纹识别：连接后读取 SSH banner
        → SNMP 查询：sysDescr(.1.3.6.1.2.1.1.1.0) 获取设备型号

Step 4: 结果汇总
        → 去重
        → 设备类型推断（交换机/路由器/防火墙/服务器/打印机）
        → 发送到 Web 后端
```

**优势：**
- 零前提，不需要任何设备的凭证
- 可以发现网络中所有 IP 设备（包括未管理的傻瓜交换机）
- 适合"我有什么设备"的摸底场景

**局限：**
- 只能发现 IP 可达的设备
- 无法发现链路关系（谁连谁）
- 可能漏掉不响应 ICMP/ARP 的设备

---

### 模式 3：串口服务器发现（带外管理）

**原理：** 通过 Console Server（串口服务器）的带外管理链路访问设备 Console 口，即使网络不通也能采集。

**什么是串口服务器：**
- 物理设备，提供 N 个 RS-232 串口转以太网
- 每个串口连接一台网络设备的 Console 口
- 用户通过 Telnet/SSH 到 `console_server_ip:port` 访问对应设备的 Console

**设备清单配置：**

```
串口服务器 IP: 10.0.0.100
────────────────────────────────────────
端口  │  连接设备        │  访问方式
2001  │  Core-SW-01     │  SSH/Telnet → 10.0.0.100:2001
2002  │  Dist-SW-01     │  SSH/Telnet → 10.0.0.100:2002
2003  │  Acc-SW-01      │  SSH/Telnet → 10.0.0.100:2003
2004  │  Firewall-01    │  SSH/Telnet → 10.0.0.100:2004
...
```

**采集流程：**

```
用户配置：
  ├── 串口服务器 IP（如 10.0.0.100）
  ├── 登录方式（Telnet/SSH）
  ├── 全局凭证（Console 登录用户名/密码）
  └── 端口-设备映射表（CSV 或手动输入）
        │
        ▼
Agent 逐个端口连接：
  ┌─────────────────────────────────┐
  │  for each 端口映射:             │
  │    连接 console_ip:port         │
  │    发送凭证                      │
  │    执行采集命令                  │
  │    show lldp neighbors detail    │
  │    show version                  │
  │    show running-config (摘要)     │
  │    断开连接                      │
  │    解析输出                      │
  └─────────────────────────────────┘
        │
        ▼
拓扑构建（同模式 1）
```

**为什么 SME 需要这个：**
- 线上网络挂了 → 通过 Console 还能访问设备排查
- 新设备上线前配置 → Console 是唯一方式
- 密码忘了 → Console 可以中断引导恢复
- 不需要设备 IP 可达

**技术实现：**

```python
class ConsoleServerCollector:
    """串口服务器采集器"""
    
    def __init__(self, server_ip: str, port_map: list[dict]):
        # port_map = [
        #   {"port": 2001, "device_name": "Core-SW-01", "vendor": "cisco"},
        #   {"port": 2002, "device_name": "Dist-SW-01", "vendor": "huawei"},
        # ]
        self.server_ip = server_ip
        self.port_map = port_map
    
    async def collect_all(self) -> list[CollectionResult]:
        results = []
        for entry in self.port_map:
            result = await self.collect_one(entry)
            results.append(result)
        return results
    
    async def collect_one(self, entry: dict) -> CollectionResult:
        # 连接到 console_ip:port
        # 发送凭证
        # 执行 show 命令
        # 解析输出
        # 返回结果
        ...

    def auto_discover_ports(self) -> list[int]:
        """自动探测串口服务器哪些端口有设备连接"""
        # 扫描 2001-2100 等常见端口范围
        # 检查 TCP 连接是否成功
        # 发送回车看是否有响应
        ...
```

**优势：**
- 带外管理，网络不通照样采集
- 能发现带内方式访问不到的基础设施
- 配置备份的"最后一道防线"

**局限：**
- 需要用户配置端口-设备映射
- 采集速度受串口速率限制（9600/115200 bps）
- 串口服务器品牌差异可能导致兼容性问题

---

### 模式 4：Excel/CSV 导入（最实用）

**原理：** 用户使用企业已有设备台账 Excel 文件，直接导入，Agent 验证可达性后构建拓扑。

**导入格式：**

| 设备名 | IP | 厂商 | 型号 | SSH端口 | 用户名 | 登录方式 | 
|--------|-----|------|------|---------|--------|---------|
| Core-SW-01 | 10.0.0.1 | cisco | Catalyst 9300 | 22 | admin | ssh |
| Dist-SW-01 | 10.0.0.2 | huawei | S5720 | 22 | admin | ssh |
| FW-01 | 10.0.0.254 | fortinet | FortiGate 60F | 22 | admin | ssh |

**流程：**

```
导入 Excel
  │
  ▼
验证清单 → 标记可达/不可达设备
  │
  ▼
对可达设备 → SSH 采集 LLDP 邻居
  │
  ▼
补充未在清单中的邻居设备
  │
  ▼
生成拓扑
  │
  ▼
导出不含密码的版本（用于分享）
```

---

## 三、四种模式选择指南

| 场景 | 推荐模式 | 说明 |
|------|---------|------|
| 我有一台核心交换机密码 | 种子发现 | 最准确，LLDP 发现全网 |
| 我什么都没有，想知道网络上有啥 | 主机网络嗅探 | 摸底扫描，先看看有啥 |
| 我有 Console Server 和线缆 | 串口服务器 | 带外管理，网络故障也能用 |
| 我有设备台账 Excel | 导入 | 最方便，有清单直接导入 |
| 混合场景 | 任意组合 | 先导入/嗅探 → 再种子发现补全拓扑 |

---

## 四、拓扑展现优化

### 当前问题
- Mermaid 静态图，不可交互
- 设备信息简略
- 没有实时状态

### 优化方案：交互式拓扑引擎

**前端渲染：** 使用 Cytoscape.js 或 vis-network

```
┌──────────────────────────────────────────┐
│  Core-SW-01          Dist-SW-02           │
│  ┌─────┐  gi1/0/1   ┌─────┐              │
│  │ 🟢  │═══════════════│ 🟢  │   ← 绿色=正常 │
│  └──┬──┘             └──┬──┘              │
│     │gi1/0/2           │gi0/2             │
│     │                  │                  │
│  ┌──▼──┐           ┌──▼──┐               │
│  │ 🟡  │           │ 🔴  │   ← 红色=离线 │
│  │Acc-SW└───────────┤FW-01│               │
│  └─────┘  gi0/1     └─────┘               │
│                                           │
│  [缩放] [导出PNG] [导出Draw.io] [打印]    │
└──────────────────────────────────────────┘
```

**交互功能：**
- 拖拽布局，自由调整
- 滚轮缩放
- 点击设备 → 弹出详情面板
- 右键 → 快速操作（SSH进入、查看配置、备份）
- 链路颜色编码：正常=绿，高延迟=黄，断开=红
- 搜索/过滤：按设备名/厂商/型号

**设备详情面板：**

```
┌────────────────────────────────┐
│ Core-SW-01                     │
│ ───────────────────────        │
│ IP:    10.0.0.1                │
│ 厂商:  Cisco                   │
│ 型号:  Catalyst 9300-48P       │
│ 版本:  17.9.5                  │
│ 状态:  🟢 在线 (5min)         │
│ 端口:  48口 / 8口 up           │
│ ───────────────────────        │
│ [SSH进入] [查看配置] [备份]     │
│ [端口列表] [邻居] [日志]       │
└────────────────────────────────┘
```

---

## 五、AI Agent 重构

### 当前问题
- Commander + Subagent 两层（过度抽象）
- Function Calling 工具多是 DB 查询伪工具
- Agent 对话上下文沉重

### 重构方案：单 Agent + 工具分组

```
用户消息
    │
    ▼
┌──────────────────┐
│   会话管理器      │  ← 管理对话历史、上下文窗口
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   LLM 推理        │  ← 单次调用，不嵌套
└────────┬─────────┘
         │
         ▼
  Tool 执行（按需）
         │
    ┌────┼────┬────┬────┐
    ▼    ▼    ▼    ▼    ▼
   SSH  拓扑  配置  知识库  Ping
  ─────────────────────────────
  ssh_exec       build_topology
  verify_config  diff_topology
  show_run       export_topology
  backup_config  analyze_topology
  list_ports
```

**工具分组设计：**

```python
# 每个 Tool 是一个独立函数，单一职责

SSH_TOOLS = {
    "ssh_exec": "SSH 到设备执行命令",
    "verify_config": "验证配置是否生效",
    "backup_device": "备份设备配置",
    "check_device_health": "检查设备健康状态",
}

TOPOLOGY_TOOLS = {
    "build_topology": "构建/刷新拓扑",
    "get_topology": "获取当前拓扑",
    "diff_topology": "对比两次拓扑差异",
    "analyze_topology": "分析拓扑问题",
}

ANALYTICS_TOOLS = {
    "search_knowledge": "搜索知识库",
    "analyze_fault": "分析故障",
    "generate_report": "生成运维报告",
}
```

---

## 六、基础设施优化

### Docker 镜像瘦身

| 依赖 | 当前大小 | 优化后 | 说明 |
|------|---------|--------|------|
| sentence-transformers | ~1.5 GB | 0 (移除) | 改用 SQLite FTS5 |
| torch | ~1.2 GB | 0 (移除) | sentence-transformers 的传递依赖 |
| CUDA 相关 | ~400 MB | 0 (移除) | CPU 推理不需要 |
| **web 镜像总计** | **~3.5 GB** | **~350 MB** | 缩到十分之一 |

### Dockerfile 修正

```dockerfile
# 修正后 web/Dockerfile
FROM python:3.12-slim AS web

RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends tini && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY app/ ./app/
COPY logging_setup.py ./

# 固定 UID，避免 bind mount 权限问题
RUN groupadd -g 1001 opsbrain && \
    useradd -u 1001 -g opsbrain --create-home --shell /sbin/nologin opsbrain && \
    mkdir -p /var/lib/opsbrain && \
    chown -R opsbrain:opsbrain /app /var/lib/opsbrain

# 保留 root 运行（避免端口绑定问题），让 WORKER 降权
# 健康检查需要 root 权限写临时文件

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.__init__:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml 优化

```yaml
services:
  web:
    build:
      context: ../web-backend
    volumes:
      - type: bind
        source: ./data
        target: /var/lib/opsbrain
    user: "1001:1001"  # 显式指定 UID

  # 主机网络嗅探器（独立）
  scanner:
    build:
      context: ../scanner
    network_mode: host
    privileged: true  # 需要 ARP 扫描权限
    profiles:
      - scanner
```

### 数据库迁移

引入 Alembic 管理 schema 变更，而不是每次 `create_all`：

```
opsbrain/migrations/
├── versions/
│   ├── 001_initial.py
│   ├── 002_add_device_table.py
│   └── 003_add_config_backup.py
├── env.py
└── alembic.ini
```

---

## 七、实施路线

### Phase 1：基础设施清理（1-2天）
- [ ] 移除 sentence-transformers / torch 依赖
- [ ] 知识库改用 SQLite FTS5
- [ ] 修正 Dockerfile 和 docker-compose
- [ ] 修复 Python 导入路径
- [ ] 数据库迁移工具

### Phase 2：嗅探重写（3-5天）
- [ ] 模式 1：种子设备发现（LLDP/CDP 递归）
- [ ] 模式 2：主机网络嗅探（ARP + TCP + SNMP）
- [ ] 模式 3：串口服务器采集
- [ ] 模式 4：Excel 导入（补全）
- [ ] 前端四种模式选择向导

### Phase 3：拓扑展现（2-3天）
- [ ] 前端交互式拓扑（Cytoscape.js）
- [ ] 设备详情面板
- [ ] 状态可视化（在线/离线/告警）
- [ ] 导出功能（PNG/Draw.io/JSON）

### Phase 4：Agent 重构（2-3天）
- [ ] 去除 Commander/Subagent 架构
- [ ] 单 Agent + 工具分组
- [ ] Agent ↔ 知识库编排
- [ ] 配置备份/变更检测

### Phase 5：运维功能（2-3天）
- [ ] 配置备份自动化
- [ ] 变更检测
- [ ] 故障分析
- [ ] 告警通知

---

## 八、串口服务器深度方案

### 支持的串口服务器品牌

| 品牌 | 默认端口范围 | 连接方式 | 备注 |
|------|------------|---------|------|
| OpenGear | 2001-2100 | SSH/Telnet | 市场主力，SME 常用 |
| Digi CM | 2001-2100 | SSH | 老牌工业级 |
| Raritan | 3001-3100 | SSH | 数据中心常见 |
| 国产（迈存/康海） | 2001-2100 | Telnet | SME 性价比高 |
| 通用 | 用户自定义 | SSH/Telnet | 任意品牌 |

### 串口采集适配

```python
# 不同品牌串口服务器的连接处理
CONSOLE_SERVER_ADAPTERS = {
    "opengear": {
        "connect": "ssh {user}@{ip} -p {port}",  # OpenGear 直接 SSH 到端口
        "login_prompt": "login:",
        "password_prompt": "Password:",
    },
    "digi": {
        "connect": "ssh {user}@{ip} -p {port}",
        "login_prompt": "User:",
        "password_prompt": "Password:",
    },
    "telnet": {
        "connect": "telnet {ip} {port}",
        "login_prompt": r"(login|Username|user):",
        "password_prompt": r"(Password|password):",
    }
}
```

### 端口自动发现

对于未知映射的串口服务器，自动探测哪些端口有设备连接：

```python
def auto_discover_ports(server_ip: str, 
                        port_range: range = range(2001, 2101)) -> list[int]:
    """
    自动发现串口服务器上有设备连接的端口。
    
    原理：尝试 TCP 连接，发送回车，看是否有响应。
    有响应的端口 → 设备在线
    无响应或拒绝 → 空端口
    """
    active_ports = []
    for port in port_range:
        try:
            sock = socket.create_connection((server_ip, port), timeout=3)
            sock.sendall(b"\r\n")
            response = sock.recv(1024)
            if response:  # 有回显，说明有设备
                active_ports.append(port)
            sock.close()
        except (socket.timeout, ConnectionRefusedError):
            pass
    return active_ports
```

### 混合模式

四种模式可以**任意组合**，例如：

1. **先导入** Excel 设备清单 → 确定已知设备
2. **种子发现** 补全链路关系
3. **串口服务器** 备份配置（保障网络不通也能采集）
4. **主机嗅探** 发现"清单之外"的未知设备

```
用户工作流示例：
1. 上传台账 Excel → 系统验证可达性
2. 自动种子发现 → 补充 LLDP 链路
3. 配置 Console Server 映射 → 深度采集
4. Agent 汇总 → 生成完整拓扑
```

---

## 九、SME 场景案例

### 案例：100 人公司，3 层网络

```
场景：某科技公司，1台核心+3台汇聚+8台接入+1台防火墙
现状：有 Excel 台账，部分设备密码统一

推荐流程：
1. 导入 Excel（10秒）
2. Agent 验证可达性 → 发现部分设备密码错误
3. 用户补充密码 → Agent 重新验证
4. 种子发现 → SSH 核心交换机 → LLDP 发现全拓扑
5. Agent 展示拓扑 → 用户确认
6. 配置定期备份（每周自动）
```

### 案例：新公司，网络裸奔

```
场景：刚搬办公室，网络设备刚上架，没有台账

推荐流程：
1. 主机网络嗅探模式 → 扫描 30 秒
2. 发现 15 台设备（交换机+路由器+AP）
3. Agent 尝试公共凭证登录 → 成功 12 台
4. 种子发现补全 LLDP 链路
5. 生成完整拓扑
6. 用户核对后保存
```

---

## 十、总结

| 维度 | 当前问题 | v2 目标 |
|------|---------|--------|
| 架构复杂度 | Commander+Subagent 两层 | 单 Agent + Tool 分组 |
| 网络发现 | 只扫一个网段，无效 | 4 种模式，覆盖全场景 |
| 拓扑展示 | Mermaid 静态图 | 交互式拓扑引擎 |
| 知识库 | 3GB 依赖换 30 条模板 | SQLite FTS5，零额外依赖 |
| 镜像大小 | ~3.5 GB | ~350 MB |
| 权限 | UID 不固定导致 500 | 固定 UID，bind mount 安全 |
| 串口服务器 | 只有概念，未实现 | 完整支持四大品牌 |
| 导入 | 路由就绪，前端没做 | 完整导入流程 |
| 数据库 | create_all 裸奔 | Alembic 迁移 |
