"""壳代理配置：环境变量驱动（``ANONGW_SHELL_`` 前缀），密钥值不入任何文件。

规则（与引擎 common/config.py 的环境覆盖纪律同源、前缀不同面）：
- 壳自己的旋钮一律 ``ANONGW_SHELL_<K>``（如 ``ANONGW_SHELL_LISTEN_PORT``），
  与引擎网关的 ``ANONGW_<K>`` 覆盖面互不重叠——同机同跑两进程时不串线；
- **密钥只存环境变量名不存值**：本地网关鉴权 key 的值从
  ``settings.gateway_key_env`` 命名的环境变量在**请求期**解析（与引擎
  ``resolve_secret`` 同口径），不进配置文件/日志/审计；
- 安装实例标识缺省落 ``anongw-transparent/data/instance.json``（该路径在
  仓 .gitignore 的 ``data/`` 规则下，不进仓）——值级键语义的"每安装实例
  独立命名空间"由此文件跨重启保持（规划 §三b）。
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

#: 壳层包根（anongw-transparent/）
PKG_ROOT = Path(__file__).resolve().parents[1]

ENV_PREFIX = "ANONGW_SHELL_"

#: 缺省监听端口（回环；避开引擎网关 9000 与 mock 8901/8902、真实腿 9004）
DEFAULT_LISTEN_PORT = 8720

#: 允许的回环监听地址（V1-01：只听 127.0.0.1/::1——壳不该成为局域网攻击面）
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

#: 恒定注入的会话头名（规划 §四M1 点名；与引擎 gateway/app.py 读取头同名）
SESSION_HEADER = "x-anongw-session-id"


@dataclass(frozen=True)
class ShellSettings:
    """壳进程配置（字段即契约，只增不改名）。"""

    listen_host: str = "127.0.0.1"
    listen_port: int = DEFAULT_LISTEN_PORT
    #: 本机引擎网关（T1 接法：壳 → 网关 → 上游）
    gateway_url: str = "http://127.0.0.1:9000"
    #: 本地网关鉴权 key 的**环境变量名**（值请求期解析，不入盘）
    gateway_key_env: str = "ANONGW_GATEWAY_KEY"
    #: 安装实例标识保管文件（相对路径按 anongw-transparent/ 解析）
    instance_file: Path = Path("data/instance.json")
    #: 实例标识显式覆盖（测试/CI 用；生产缺省走 instance_file）
    instance_id: str | None = None
    #: 上游（网关）读超时秒数：LLM 长回答不被壳掐断
    read_timeout_s: float = 300.0
    #: 壳→网关 keep-alive 连接池（缺省开：省每请求回环建连；规划 §三e 连接复用）。
    #: 关闭（=0）用于性能测量配臂对齐（V4-01：两臂每请求新建连接，Δ 只剩壳开销）。
    keepalive_connections: int = 16
    #: 非回环监听显式放行（默认拒绝；V1-01 纪律的运行时闸）
    allow_non_loopback: bool = False

    def resolve_instance_file(self) -> Path:
        p = Path(self.instance_file)
        return p if p.is_absolute() else PKG_ROOT / p


def _env_int(raw: str) -> int | None:
    try:
        return int(raw)
    except ValueError:
        return None


def _env_float(raw: str) -> float | None:
    try:
        return float(raw)
    except ValueError:
        return None


def load_settings(env: Mapping[str, str] | None = None) -> ShellSettings:
    """环境变量 → ShellSettings；``env`` 是叠在真实进程环境**之上**的覆盖层
    （CLI 参数经此注入；``None`` 即纯进程环境）。"""
    raw_env: dict[str, str] = dict(os.environ)
    if env:
        raw_env.update({k: v for k, v in env.items() if v is not None})

    def get(key: str) -> str | None:
        return raw_env.get(ENV_PREFIX + key)

    host = get("LISTEN_HOST") or "127.0.0.1"
    port = _env_int(get("LISTEN_PORT") or "") or DEFAULT_LISTEN_PORT
    gateway_url = get("GATEWAY_URL") or "http://127.0.0.1:9000"
    gateway_key_env = get("GATEWAY_KEY_ENV") or "ANONGW_GATEWAY_KEY"
    instance_file = Path(get("INSTANCE_FILE") or "data/instance.json")
    instance_id = get("INSTANCE_ID") or None
    read_timeout = _env_float(get("READ_TIMEOUT_S") or "") or 300.0
    keepalive = _env_int(get("KEEPALIVE_CONNECTIONS") or "")
    allow_non_loopback = (get("ALLOW_NON_LOOPBACK") or "").strip().lower() in ("1", "true", "yes")
    return ShellSettings(
        listen_host=host, listen_port=port, gateway_url=gateway_url,
        gateway_key_env=gateway_key_env, instance_file=instance_file,
        instance_id=instance_id, read_timeout_s=read_timeout,
        keepalive_connections=0 if keepalive is not None and keepalive <= 0
        else (keepalive if keepalive is not None else 16),
        allow_non_loopback=allow_non_loopback,
    )
