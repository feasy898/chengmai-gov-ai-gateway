"""壳代理服务面：回环监听、恒定头注入、转发保真、响应计量（M1 竖切主体）。

拓扑（规划 §三h·M1 接法）::

    agent/curl ──HTTP(明文回环)──▶ anongw-transparent 壳 ──▶ 本机引擎网关 ──▶ 上游

壳的四件事（规划 §四M1 改动面）：
1. 回环 HTTP 监听（V1-01：只听 127.0.0.1/::1；非回环显式拒绝，除非
   ``ANONGW_SHELL_ALLOW_NON_LOOPBACK=1`` 响亮放行——默认 fail-closed）；
2. **恒定注入** ``x-anongw-session-id`` = 安装实例标识（值级键语义；客户端
   自带的同名头被覆盖——壳是实例边界，禁止每请求现造会话的退化，V1-02）；
3. 本地网关鉴权头注入（``Authorization: Bearer <ANONGW_GATEWAY_KEY>``，
   值请求期从 env 解析、永不落盘/日志；缺失 → 503 响亮拒绝，不裸转发——
   F9 fail-open/closed 未裁决前按 fail-closed 默认，README 登记）；
4. 运行时泄漏计数：SSE 流在**帧组装后**、非流式在 JSON 组装后，调引擎
   ``tolerant_placeholder_hits`` 计量（M0 教训；计数经 /anongw/stats 可查）。

转发保真（V1-03/V1-04）：请求体字节零改写（检测/脱敏/重建全在引擎）；
响应字节零改写（还原已在引擎完成）——壳只剥 hop-by-hop 头、注入身份头。
"""
from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from anongw_evals.thresholds import SHELL_METER_MAX_RESPONSE_BYTES, SHELL_REQUEST_MAX_BYTES
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from anongw_shell.config import LOOPBACK_HOSTS, SESSION_HEADER, ShellSettings
from anongw_shell.identity import InstanceIdentity, load_or_create
from anongw_shell.leakmeter import LeakMeter
from anongw_shell.relay import meter_json_bytes, relay_stream_with_meter
from common.logs import get_logger

log = get_logger(__name__)

#: hop-by-hop 头（RFC 9110 §7.6.1）：转发时剥离；content-length 由发送侧重算
_HOP_BY_HOP = frozenset({
    "host", "content-length", "connection", "keep-alive", "transfer-encoding",
    "upgrade", "te", "trailer", "expect",
    "proxy-authorization", "proxy-authenticate", "proxy-connection",
})

SSE_CONTENT_TYPE = "text/event-stream"

_REQUEST_ID_HEADER = "x-anongw-request-id"   # 引擎网关响应自带，用作计量事件关联键


def _shell_request_id() -> str:
    return "t1sh-" + uuid.uuid4().hex[:12]


def _error_envelope(status: int, message: str) -> JSONResponse:
    """§5.6 同形状错误信封（客户端按 OpenAI 兼容错误解析；壳不静默吞错）。"""
    return JSONResponse(
        {"error": {"message": message, "type": "anongw_shell_error",
                   "param": None, "code": None}},
        status_code=status,
    )


def _forwarded_stream(
    resp: httpx.Response, *, meter: LeakMeter, request_id: str
) -> AsyncIterator[bytes]:
    """数据面字节零改写中继；计量面在帧组装后（含客户端中途断开的 finally）。"""

    async def gen():
        try:
            async for chunk in relay_stream_with_meter(resp.aiter_bytes(),
                                                       meter=meter, request_id=request_id):
                yield chunk
        finally:
            await resp.aclose()
            snap = meter.snapshot()
            events = snap["recent_events"]
            if events and events[-1]["request_id"] == request_id:
                log.error("shell.leak_detected", extra={
                    "request_id": request_id, "source": "stream",
                    "hits": len(events[-1]["hits"]),
                })

    return gen()


def create_shell_app(
    settings: ShellSettings, *,
    identity: InstanceIdentity | None = None,
    meter: LeakMeter | None = None,
    client: httpx.AsyncClient | None = None,
) -> FastAPI:
    """构造壳应用。生产入口不传参（env 配置 + 实例文件装载）；测试可全量注入。"""
    identity = identity or load_or_create(settings)
    meter = meter or LeakMeter()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        own_client = client is None
        # keepalive_connections<=0：每请求新建到网关的连接（性能测量配臂对齐用，
        # V4-01；生产缺省开池——规划 §三e「连接池与会话复用」）
        limits = httpx.Limits(max_connections=64,
                              max_keepalive_connections=settings.keepalive_connections)
        c = client or httpx.AsyncClient(
            base_url=settings.gateway_url, limits=limits,
            timeout=httpx.Timeout(connect=10.0, read=settings.read_timeout_s,
                                  write=60.0, pool=60.0),
        )
        app.state.client = c
        log.info("shell.start", extra={
            "listen": f"{settings.listen_host}:{settings.listen_port}",
            "gateway_url": settings.gateway_url,
            "instance_id": identity.instance_id,
        })
        try:
            yield
        finally:
            if own_client:
                await c.aclose()

    app = FastAPI(title="anongw-transparent-shell", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.settings = settings
    app.state.identity = identity
    app.state.meter = meter

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "anongw-transparent-shell",
            "instance_id": identity.instance_id,
            "gateway_url": settings.gateway_url,
            "session_header": SESSION_HEADER,
        }

    @app.get("/anongw/stats")
    async def stats() -> dict[str, Any]:
        """运行时泄漏计数器出口（「不骗人」一等原则：面板数 = 计数器数，可复算）。"""
        return {
            "service": "anongw-transparent-shell",
            "instance_id": identity.instance_id,
            "leak": meter.snapshot(),
        }

    @app.post("/anongw/stats/reset")
    async def stats_reset() -> dict[str, Any]:
        return {"cleared": meter.reset()}

    async def forward(path: str, request: Request) -> Response:
        # ── 0) fail-closed：本地网关 key 未配置 → 响亮拒绝，不裸转发（F9 默认）──
        gateway_key = os.environ.get(settings.gateway_key_env) or ""
        if not gateway_key:
            log.error("shell.missing_gateway_key", extra={
                "env_name": settings.gateway_key_env,
            })
            return _error_envelope(
                503, f"shell misconfigured: env {settings.gateway_key_env} "
                     "(local gateway key) is not set — refusing to forward (fail-closed)")

        # ── 1) 请求体：字节保真读取（有界；检测/脱敏在引擎，壳零改写）──
        body = await request.body()
        if len(body) > SHELL_REQUEST_MAX_BYTES:
            return _error_envelope(413, "request body exceeds shell limit")

        # ── 2) 头重整：剥 hop-by-hop、剥客户端会话头，恒定注入实例会话头 + 鉴权头 ──
        headers = {
            name: value for name, value in request.headers.items()
            if name.lower() not in _HOP_BY_HOP and name.lower() != SESSION_HEADER
        }
        headers[SESSION_HEADER] = identity.instance_id            # 恒定注入（V1-02）
        headers["authorization"] = f"Bearer {gateway_key}"        # 本地网关鉴权头
        client_drove_session = SESSION_HEADER in request.headers

        # ── 3) 转发（流式/非流式同路径；query 原样）──
        c: httpx.AsyncClient = request.app.state.client
        shell_rid = _shell_request_id()
        try:
            upstream_resp = await c.send(
                c.build_request(request.method, f"/{path}", params=request.query_params,
                                headers=headers, content=body),
                stream=True,
            )
        except httpx.HTTPError as exc:
            # 上游（本机网关）不可达：显式 502 信封——可判别故障，绝不静默（V1-07）
            log.error("shell.gateway_unreachable", extra={
                "request_id": shell_rid, "exc_type": type(exc).__name__, "path": path,
            })
            return _error_envelope(502, "shell cannot reach local gateway")

        gateway_rid = upstream_resp.headers.get(_REQUEST_ID_HEADER, shell_rid)
        content_type = upstream_resp.headers.get("content-type", "")
        resp_headers = {
            name: value for name, value in upstream_resp.headers.items()
            if name.lower() not in _HOP_BY_HOP
        }
        if client_drove_session:
            log.warning("shell.client_session_header_overridden", extra={
                "request_id": gateway_rid,
            })

        if content_type.split(";")[0].strip() == SSE_CONTENT_TYPE:
            # 流式：字节零改写中继；计量在帧组装后（_forwarded_stream finally）
            return StreamingResponse(
                _forwarded_stream(upstream_resp, meter=meter, request_id=gateway_rid),
                status_code=upstream_resp.status_code,
                media_type=SSE_CONTENT_TYPE,
                headers=resp_headers,
            )

        # 非流式：有界读取 → 组装后计量 → 原字节返回（V1-03 除注入头外逐字节回来）
        raw = await upstream_resp.aread()
        await upstream_resp.aclose()
        if len(raw) <= SHELL_METER_MAX_RESPONSE_BYTES:
            hits = meter_json_bytes(raw, meter=meter, request_id=gateway_rid)
            if hits:
                log.error("shell.leak_detected", extra={
                    "request_id": gateway_rid, "source": "nonstream", "hits": len(hits),
                })
        else:
            # 超限不计量只透传——计量面永不阻塞数据面（如实记 skipped，不冒充计量过）
            meter.meter_texts([], request_id=gateway_rid, source="nonstream_skipped_too_large")
            log.warning("shell.meter_skipped_too_large", extra={
                "request_id": gateway_rid, "bytes": len(raw),
            })
        return Response(content=raw, status_code=upstream_resp.status_code,
                        headers=resp_headers)

    app.add_api_route("/{path:path}", forward,
                      methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    # 根路径（path=""）单独登记（{path:path} 不匹配空串）
    app.add_api_route("", forward,
                      methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                      include_in_schema=False)
    return app


def assert_loopback_bind(settings: ShellSettings) -> None:
    """V1-01 运行时闸：非回环监听默认拒绝（显式 env 放行时响亮告警）。"""
    if settings.listen_host in LOOPBACK_HOSTS:
        return
    if not settings.allow_non_loopback:
        raise RuntimeError(
            f"refusing to bind non-loopback {settings.listen_host!r} "
            "(V1-01: the shell must not become a LAN-adjacent attack surface); "
            "set ANONGW_SHELL_ALLOW_NON_LOOPBACK=1 to override explicitly")
    log.warning("shell.non_loopback_bind_overridden", extra={"host": settings.listen_host})


def describe_payload(payload: bytes) -> str:  # pragma: no cover - 诊断工具
    try:
        return json.dumps(json.loads(payload), ensure_ascii=False)
    except (ValueError, UnicodeDecodeError):
        return ""
