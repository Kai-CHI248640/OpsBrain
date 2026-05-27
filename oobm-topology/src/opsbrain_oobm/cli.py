"""
OpsBrain OOBM — CLI Entrypoint

Docker 风格 CLI: 单个二进制入口，subcommand 驱动
  opsbrain-oobm inventory load    ← 加载 Excel 清单
  opsbrain-oobm collect           ← 执行采集
  opsbrain-oobm topology build    ← 构建拓扑
  opsbrain-oobm run --pipeline    ← 全流程
  opsbrain-oobm status            ← 运行状态
  opsbrain-oobm version           ← 版本信息
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from . import __version__
from .config import AppConfig, config as global_config
from .logging_setup import setup_logging, get_logger

log = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 通用选项
# ═══════════════════════════════════════════════════════════════════════════

_common_opts = [
    click.option(
        "--config",
        "-c",
        envvar="OPSBRAIN_CONFIG_DIR",
        default="/etc/opsbrain",
        show_envvar=True,
        help="配置目录路径",
        type=click.Path(exists=True, file_okay=False, dir_okay=True),
    ),
    click.option(
        "--log-level",
        envvar="OPSBRAIN_LOG_LEVEL",
        default="info",
        show_envvar=True,
        type=click.Choice(["debug", "info", "warning", "error"]),
        help="日志级别",
    ),
    click.option(
        "--log-format",
        envvar="OPSBRAIN_LOG_FORMAT",
        default="json",
        show_envvar=True,
        type=click.Choice(["json", "text"]),
        help="日志格式",
    ),
]


def common_options(func):
    for opt in _common_opts:
        func = opt(func)
    return func


# ═══════════════════════════════════════════════════════════════════════════
# Main Group
# ═══════════════════════════════════════════════════════════════════════════

@click.group()
@click.version_option(version=__version__, prog_name="opsbrain-oobm")
@common_options
def cli(config: str, log_level: str, log_format: str):
    """OpsBrain OOBM — 网络拓扑自动发现 (v{})""".format(__version__)
    setup_logging(level=log_level.upper(), fmt=log_format)


# ═══════════════════════════════════════════════════════════════════════════
# inventory — 设备清单管理
# ═══════════════════════════════════════════════════════════════════════════

@cli.group()
def inventory():
    """管理设备清单"""


@inventory.command("load")
@click.option(
    "--file", "-f",
    envvar="OPSBRAIN_INVENTORY_FILE",
    default="/etc/opsbrain/device-inventory.xlsx",
    show_envvar=True,
    help="Excel 设备清单文件路径",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    "--output", "-o",
    envvar="OPSBRAIN_INVENTORY_OUTPUT",
    default="/var/lib/opsbrain/inventory/devices.json",
    show_envvar=True,
    help="设备清单输出路径",
)
@click.option("--strict/--no-strict", default=True, help="严格校验")
@click.option("--show/--no-show", default=False, help="输出后打印概要")
def load_inventory(file: str, output: str, strict: bool, show: bool):
    """加载并校验 Excel 设备清单，输出标准化设备清单 JSON"""
    from .inventory.loader import InventoryLoader
    from .inventory.validator import InventoryValidator

    file_path = Path(file)
    output_path = Path(output)

    log.info("Loading inventory", extra={"file": str(file_path)})

    loader = InventoryLoader(file_path)
    devices = loader.load()

    validator = InventoryValidator()
    errors = validator.validate(devices, strict=strict)

    if errors:
        for err in errors:
            log.error("Validation error", extra={"error": err})
        if strict:
            sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    loader.save(devices, output_path)

    log.info(
        "Inventory loaded",
        extra={
            "device_count": len(devices),
            "output": str(output_path),
        },
    )

    if show:
        _print_inventory_summary(devices)


def _print_inventory_summary(devices: list[dict]) -> None:
    """打印设备清单概要"""
    from collections import Counter

    types = Counter(d["device_type"] for d in devices)
    vendors = Counter(d["vendor"] for d in devices)
    roles = Counter(d["role"] for d in devices)

    click.echo("\n═══ 设备清单概要 ═══")
    click.echo(f"  总数: {len(devices)} 台")
    click.echo(f"  类型: {', '.join(f'{k}={v}' for k, v in types.most_common())}")
    click.echo(f"  厂商: {', '.join(f'{k}={v}' for k, v in vendors.most_common())}")
    click.echo(f"  角色: {', '.join(f'{k}={v}' for k, v in roles.most_common())}")
    click.echo(f"{'─' * 40}")


# ═══════════════════════════════════════════════════════════════════════════
# collect — 采集
# ═══════════════════════════════════════════════════════════════════════════

@cli.command()
@click.option(
    "--inventory", "-i",
    envvar="OPSBRAIN_INVENTORY_OUTPUT",
    default="/var/lib/opsbrain/inventory/devices.json",
    show_envvar=True,
    help="设备清单 JSON 路径",
)
@click.option(
    "--workers", "-w",
    envvar="OPSBRAIN_WORKERS",
    default=10,
    show_envvar=True,
    type=int,
    help="并行 Worker 数",
)
@click.option(
    "--output", "-o",
    envvar="OPSBRAIN_COLLECTED_DIR",
    default="/var/lib/opsbrain/collected",
    show_envvar=True,
    help="采集结果输出目录",
)
def collect(inventory: str, workers: int, output: str):
    """执行设备采集 — SSH Console 端口采集网络信息"""
    from .inventory.loader import InventoryLoader
    from .collector.pool import CollectorPool

    inv_path = Path(inventory)
    out_dir = Path(output)

    log.info("Starting collection",
             extra={"workers": workers, "output": str(out_dir)})

    devices = InventoryLoader.load_json(inv_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    pool = CollectorPool(devices, out_dir, max_workers=workers)
    results = pool.run()

    click.echo(
        f"\n═══ 采集完成 ═══\n"
        f"  成功: {results['success']}  |  "
        f"失败: {results['failed']}  |  "
        f"跳过: {results['skipped']}\n"
        f"  总耗时: {results.get('duration_seconds', 0):.1f}s\n"
        f"  发现新设备: {results.get('discovered', 0)}\n"
        f"{'─' * 40}"
    )

    if results.get("discovered_files"):
        click.echo(f"  新发现设备列表已保存至 {results['discovered_files']}")

    if results["failed"] > 0:
        click.echo(f"\n  ⚠ 失败设备列表: {results.get('failed_devices', [])}")


# ═══════════════════════════════════════════════════════════════════════════
# topology — 拓扑构建
# ═══════════════════════════════════════════════════════════════════════════

@cli.group()
def topology():
    """拓扑构建与管理"""


@topology.command("build")
@click.option(
    "--collected", "-c",
    envvar="OPSBRAIN_COLLECTED_DIR",
    default="/var/lib/opsbrain/collected",
    show_envvar=True,
    help="采集数据目录",
)
@click.option(
    "--output", "-o",
    envvar="OPSBRAIN_OUTPUT_DIR",
    default="/var/lib/opsbrain/topology",
    show_envvar=True,
    help="拓扑输出目录",
)
@click.option(
    "--formats",
    envvar="OPSBRAIN_OUTPUT_FORMATS",
    default="json,dot,mermaid",
    show_envvar=True,
    help="输出格式 (逗号分隔)",
)
@click.option("--render/--no-render", default=False, help="渲染为图片")
def build_topology(collected: str, output: str, formats: str, render: bool):
    """构建设备拓扑 — 采集数据 → 关联 → 输出拓扑图"""
    from .topology.builder import TopologyBuilder

    collected_dir = Path(collected)
    output_dir = Path(output)
    fmt_list = [f.strip() for f in formats.split(",")]

    log.info("Building topology",
             extra={
                 "collected_dir": str(collected_dir),
                 "output_dir": str(output_dir),
                 "formats": fmt_list,
             })

    builder = TopologyBuilder(collected_dir, output_dir)
    builder.build()
    builder.save_output(formats=fmt_list)

    summary = builder.summary()
    click.echo(
        f"\n═══ 拓扑构建完成 ═══\n"
        f"  设备数: {summary['total_devices']}\n"
        f"  确认链路: {summary['confirmed_links']}\n"
        f"  未确认链路: {summary['unconfirmed_links']}\n"
        f"  输出目录: {output_dir}"
    )

    if builder.unconfirmed_links:
        click.echo(f"\n  ⚠ 以下链路未双向确认:")
        for link in builder.unconfirmed_links:
            click.echo(
                f"    {link.device_a}:{link.port_a} → "
                f"{link.device_b}:{link.port_b or '?'}"
            )


@topology.command("diff")
@click.option("--before", "-b", required=True, help="旧拓扑 JSON 路径")
@click.option("--after", "-a", required=True, help="新拓扑 JSON 路径")
def diff_topology(before: str, after: str):
    """对比两个拓扑的差异"""
    from .topology.diff import TopologyDiff

    diff = TopologyDiff(Path(before), Path(after))
    changes = diff.compare()

    click.echo(f"\n═══ 拓扑变更 ═══")
    for change in changes:
        icon = {"added": "➕", "removed": "➖", "changed": "🔄"}.get(
            change["type"], "❓"
        )
        click.echo(f"  {icon} {change['description']}")

    if not changes:
        click.echo("  无变更")


# ═══════════════════════════════════════════════════════════════════════════
# model — 模型 API 管理
# ═══════════════════════════════════════════════════════════════════════════

@cli.group()
def model():
    """模型 API 管理"""


@model.command("test")
@click.option(
    "--provider",
    envvar="OPSBRAIN_MODEL_PROVIDER",
    default="deepseek",
    show_envvar=True,
    help="模型提供商",
)
@click.option(
    "--api-base",
    envvar="OPSBRAIN_MODEL_API_BASE",
    default="",
    show_envvar=True,
    help="API 基础地址",
)
@click.option(
    "--api-key",
    envvar="OPSBRAIN_MODEL_API_KEY",
    default="",
    show_envvar=True,
    help="API Key",
)
@click.option(
    "--model-name",
    envvar="OPSBRAIN_MODEL_MODEL",
    default="",
    show_envvar=True,
    help="模型名称",
)
@click.option(
    "--prompt",
    default="Reply with exactly: Connection OK",
    show_default=True,
    help="测试提示词",
)
def test_model(
    provider: str,
    api_base: str,
    api_key: str,
    model_name: str,
    prompt: str,
):
    """测试模型 API 连通性"""
    from .model import ModelConfig, create_client

    conf = ModelConfig(
        provider=provider,
        api_base=api_base,
        api_key=api_key,
        model=model_name,
    )

    api_base_val = conf.get_api_base() or "(未配置)"
    model_val = conf.get_model() or "(未配置)"

    click.echo(f"\n═══ 模型 API 连通性测试 ═══")
    click.echo(f"  提供商:    {provider}")
    click.echo(f"  API 地址:  {api_base_val}")
    click.echo(f"  模型:      {model_val}")
    click.echo(f"  API Key:   {'****' + api_key[-4:] if len(api_key) > 4 else '(未设置)'}")
    click.echo(f"  {'─' * 40}")

    if not api_key:
        click.echo(f"\n  ❌ API Key 未配置")
        click.echo(f"  设置: export OPSBRAIN_MODEL_API_KEY=sk-xxx")
        click.echo(f"  或写 .env: OPSBRAIN_MODEL_API_KEY=sk-xxx")
        return

    client = create_client(conf)
    if not client:
        click.echo(f"\n  ❌ 创建客户端失败 (提供商: {provider})")
        return

    click.echo(f"  发送测试请求...")

    try:
        result = client.check_connection()

        if result.get("status") == "ok":
            click.echo(f"  ✅ 连接成功!")
            click.echo(f"  {'─' * 40}")
            click.echo(f"  响应时间: {result.get('latency_ms', '?')}ms")
            click.echo(f"  模型实际: {result.get('model', model_val)}")
            click.echo(f"  响应内容: {result.get('response', '')[:150]}")
        else:
            click.echo(f"  ❌ 连接失败: {result.get('error', '未知错误')}")
    except Exception as e:
        click.echo(f"  ❌ 异常: {e}")


@model.command("providers")
def list_providers():
    """列出所有支持的模型提供商"""
    from .model import MODEL_PROVIDER_BASES, MODEL_PROVIDER_MODELS

    click.echo(f"\n═══ 支持的模型提供商 ═══")
    click.echo(f"  {'提供商':<16} {'默认 API 地址':<40} {'默认模型':<30}")
    click.echo(f"  {'─'*16} {'─'*40} {'─'*30}")

    for provider in ["openai", "deepseek", "siliconflow", "anthropic", "ollama", "custom"]:
        base = MODEL_PROVIDER_BASES.get(provider, "")
        model = MODEL_PROVIDER_MODELS.get(provider, "")
        click.echo(f"  {provider:<16} {base:<40} {model:<30}")

    click.echo(f"\n  用法:")
    click.echo(f"    # 使用环境变量:")
    click.echo(f"    export OPSBRAIN_MODEL_PROVIDER=custom")
    click.echo(f"    export OPSBRAIN_MODEL_API_BASE=https://your-endpoint/v1")
    click.echo(f"    export OPSBRAIN_MODEL_API_KEY=sk-xxx")
    click.echo(f"    export OPSBRAIN_MODEL_MODEL=your-model")
    click.echo(f"")
    click.echo(f"    # 测试连接:")
    click.echo(f"    opsbrain-oobm model test")
    click.echo(f"    opsbrain-oobm model test --provider deepseek")
    click.echo(f"    opsbrain-oobm model test --provider custom --api-base https://xxx/v1 --api-key sk-xxx")


# ═══════════════════════════════════════════════════════════════════════════
# run — 全流程执行
# ═══════════════════════════════════════════════════════════════════════════

@cli.command()
@click.option(
    "--pipeline",
    envvar="OPSBRAIN_PIPELINE_MODE",
    default="full",
    show_envvar=True,
    type=click.Choice(["full", "collect", "topology", "incremental"]),
    help="Pipeline 模式",
)
def run(pipeline: str):
    """运行 OOBM 全流程"""
    from .orchestrator.pipeline import Pipeline

    log.info("Starting pipeline", extra={"mode": pipeline})

    pipeline = Pipeline(mode=pipeline)
    result = pipeline.execute()

    if result["status"] == "success":
        click.echo(f"\n✅ Pipeline 完成 (模式: {pipeline})")
    else:
        click.echo(f"\n❌ Pipeline 失败: {result.get('error', '未知错误')}")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════
# status — 运行状态
# ═══════════════════════════════════════════════════════════════════════════

@cli.command()
def status():
    """查看当前运行状态"""
    from .orchestrator.state_machine import PipelineState

    state = PipelineState.load()
    click.echo(f"\n═══ OOBM 状态 ═══")
    click.echo(f"  Phase: {state.phase.value}")
    click.echo(f"  Devices: {state.total_devices}")
    click.echo(f"  Collected: {state.collected_count}")
    click.echo(f"  Failed: {state.failed_count}")
    click.echo(f"  Round: {state.current_round}")
    click.echo(f"  Started: {state.started_at or 'N/A'}")
    click.echo(f"  Updated: {state.updated_at or 'N/A'}")


# ═══════════════════════════════════════════════════════════════════════════
# version
# ═══════════════════════════════════════════════════════════════════════════

@cli.command("version")
def show_version():
    """显示版本信息"""
    click.echo(f"opsbrain-oobm v{__version__}")
    click.echo(f"Python: {sys.version.split()[0]}")
