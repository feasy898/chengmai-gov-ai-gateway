"""测试基床：mock 上游 + 引擎网关 + 壳的三层进程内 fixture（uvicorn 线程）。

链路（T1 形态）：httpx 客户端 → ShellServer → GatewayServer → MockUpstreamServer。
全部端口自分配（_portalloc，V2-02）；网关注入内存审计表与进程内会话注册表
（不落 data/*.db）；key 全走 env（MOCK_KEY / MASK_KEY 测试值 / ANONGW_GATEWAY_KEY
= 仓内文档化的演示部门 key——与 evals/t0_gateway.py 同一夹具口径）。
"""
from __future__ import annotations

import threading
import time
from typing import Any

import httpx
import uvicorn

from anongw_evals._portalloc import free_ports
from audit.store import InMemoryAuditStore
from common.config import AppConfig, UpstreamCfg, load_dept_keys
from gateway.app import create_app
from gateway.mock_upstream import MockUpstreamServer
from masking.mapper import SessionRegistry

DEMO_DEPT = "民政局"
#: 演示明文（仓内 .env.example / t0_gateway.py 文档化；YAML 只存 sha256）
DEMO_KEY = "dk_5e6f7a8b"
EVAL_MASK_KEY = "cd" * 32


def make_gateway_config(*, internet_port: int, govcloud_port: int) -> AppConfig:
    """eval 专用网关配置：两条 mock 上游（端口自分配），其余字段取契约默认。"""
    return AppConfig(
        listen=0,  # 由 uvicorn 线程实际绑定；配置值不参与
        mask_key_env="MASK_KEY",
        session_ttl_h=24,
        upstreams=[
            UpstreamCfg(name="internet_mock", base_url=f"http://127.0.0.1:{internet_port}/v1",
                        api_key_env="MOCK_KEY", models=["mock-chat"], route="INTERNET"),
            UpstreamCfg(name="govcloud_local", base_url=f"http://127.0.0.1:{govcloud_port}/v1",
                        api_key_env="MOCK_KEY", models=["gov-chat"], route="GOVCLOUD"),
        ],
    )


class UvicornFixture:
    """uvicorn 后台线程通用壳（与 gateway.mock_upstream.MockUpstreamServer 同模式）。"""

    def __init__(self, app: Any, *, host: str, port: int, name: str, health_path: str) -> None:
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.name = name
        self._health_path = health_path
        self._server = uvicorn.Server(uvicorn.Config(
            app, host=host, port=port, log_level="warning", log_config=None, access_log=False,
        ))
        self._thread: threading.Thread | None = None

    def start(self, *, wait: bool = True, timeout: float = 15.0) -> UvicornFixture:
        self._thread = threading.Thread(target=self._server.run, name=f"{self.name}-{self.port}",
                                        daemon=True)
        self._thread.start()
        if wait:
            self.wait_ready(timeout)
        return self

    def wait_ready(self, timeout: float = 15.0) -> None:
        deadline = time.monotonic() + timeout
        last_exc: Exception | None = None
        while time.monotonic() < deadline:
            if self._thread is not None and not self._thread.is_alive():
                raise RuntimeError(f"{self.name} :{self.port} thread exited before ready")
            try:
                resp = httpx.get(f"{self.base_url}{self._health_path}", timeout=1.0)
                if resp.status_code == 200 and resp.json().get("ok") is True:
                    return
            except Exception as exc:  # noqa: BLE001 — 启动窗口内连接失败属预期
                last_exc = exc
            time.sleep(0.1)
        raise RuntimeError(f"{self.name} :{self.port} not ready within {timeout}s (last: {last_exc})")

    def stop(self) -> None:
        self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=10.0)
        self._thread = None

    def __enter__(self) -> UvicornFixture:
        return self.start()

    def __exit__(self, *exc_info: object) -> None:
        self.stop()


def start_gateway(*, internet_port: int, govcloud_port: int, port: int,
                  audit_store: InMemoryAuditStore | None = None,
                  registry: SessionRegistry | None = None) -> tuple[UvicornFixture, InMemoryAuditStore]:
    """拉起引擎网关（真实 create_app 链路；注入内存审计/注册表防落盘）。"""
    audit = audit_store if audit_store is not None else InMemoryAuditStore()
    mask_key = EVAL_MASK_KEY
    reg = registry if registry is not None else SessionRegistry(mask_key.encode("utf-8"))
    app = create_app(
        cfg=make_gateway_config(internet_port=internet_port, govcloud_port=govcloud_port),
        mask_key=mask_key,
        dept_key_digests=load_dept_keys(),
        audit_store=audit,
        session_registry=reg,
    )
    fixture = UvicornFixture(app, host="127.0.0.1", port=port, name="gateway",
                             health_path="/healthz")
    fixture.start()
    return fixture, audit


def start_shell(*, gateway_port: int, port: int, instance_id: str,
                meter: Any | None = None,
                keepalive_connections: int = 16) -> Any:
    """拉起壳（真实 create_shell_app 链路；实例标识显式注入，不碰仓内 data/）。

    ``keepalive_connections=0``：壳→网关每请求新建连接（性能测量配臂对齐，
    V4-01 连接策略纪律）；缺省 16（生产形态）。
    """
    from anongw_shell.config import ShellSettings
    from anongw_shell.identity import InstanceIdentity
    from anongw_shell.leakmeter import LeakMeter
    from anongw_shell.server import create_shell_app

    settings = ShellSettings(
        listen_host="127.0.0.1", listen_port=port,
        gateway_url=f"http://127.0.0.1:{gateway_port}",
        gateway_key_env="ANONGW_GATEWAY_KEY",
        instance_file="/nonexistent/anongw_evals_instance.json",  # 显式覆盖态，不落盘
        instance_id=instance_id,
        keepalive_connections=keepalive_connections,
    )
    identity = InstanceIdentity(instance_id=instance_id, created_at="", store_path=None)
    app = create_shell_app(settings, identity=identity,
                           meter=meter if meter is not None else LeakMeter())
    fixture = UvicornFixture(app, host="127.0.0.1", port=port, name="shell",
                             health_path="/healthz")
    fixture.start()
    return fixture


class ThreeTierStack:
    """mock 上游×2 + 引擎网关 + 壳 的一次性栈（with 语义；退出全停）。"""

    def __init__(self, *, instance_id: str, chunk_min: int = 1, chunk_max: int = 7) -> None:
        self.instance_id = instance_id
        ports = free_ports(4)
        self.internet_port, self.govcloud_port, self.gateway_port, self.shell_port = ports
        self._chunk_min = chunk_min
        self._chunk_max = chunk_max
        self.internet: MockUpstreamServer | None = None
        self.govcloud: MockUpstreamServer | None = None
        self.gateway: UvicornFixture | None = None
        self.shell: UvicornFixture | None = None
        self.audit: InMemoryAuditStore | None = None
        self.meter: Any | None = None

    def __enter__(self) -> ThreeTierStack:
        import os

        os.environ.setdefault("MOCK_KEY", "mock-demo-key")
        os.environ["ANONGW_GATEWAY_KEY"] = DEMO_KEY
        self.internet = MockUpstreamServer(self.internet_port, chunk_min=self._chunk_min,
                                           chunk_max=self._chunk_max).start()
        self.govcloud = MockUpstreamServer(self.govcloud_port, chunk_min=self._chunk_min,
                                           chunk_max=self._chunk_max).start()
        self.gateway, self.audit = start_gateway(
            internet_port=self.internet_port, govcloud_port=self.govcloud_port,
            port=self.gateway_port)
        from anongw_shell.leakmeter import LeakMeter

        self.meter = LeakMeter()
        self.shell = start_shell(gateway_port=self.gateway_port, port=self.shell_port,
                                 instance_id=self.instance_id, meter=self.meter)
        return self

    def __exit__(self, *exc_info: object) -> None:
        for fixture in (self.shell, self.gateway, self.govcloud, self.internet):
            if fixture is not None:
                fixture.stop()

    # ── 便捷面 ────────────────────────────────────────────────────
    def chat(self, body: dict[str, Any], *, via_shell: bool = True,
             headers: dict[str, str] | None = None) -> httpx.Response:
        """非流式 chat（每请求新建连接，匹配臂对齐——V4-01 连接策略纪律）。"""
        base = self.shell.base_url if via_shell else self.gateway.base_url
        with httpx.Client(timeout=30.0) as client:
            return client.post(f"{base}/v1/chat/completions", json=body, headers=headers or {})

    def chat_stream(self, body: dict[str, Any], *, via_shell: bool = True,
                    headers: dict[str, str] | None = None) -> str:
        """流式 chat → 原始 SSE 文本（逐帧收齐，供帧结构/组装断言）。"""
        base = self.shell.base_url if via_shell else self.gateway.base_url
        parts: list[str] = []
        with httpx.Client(timeout=60.0) as client:
            with client.stream("POST", f"{base}/v1/chat/completions", json=body,
                               headers=headers or {}) as resp:
                resp.raise_for_status()
                for chunk in resp.iter_text():
                    parts.append(chunk)
        return "".join(parts)

    def shell_stats(self) -> dict[str, Any]:
        assert self.shell is not None
        return httpx.get(f"{self.shell.base_url}/anongw/stats", timeout=10.0).json()
