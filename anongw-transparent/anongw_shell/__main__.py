"""壳进程入口：``cd anongw-transparent && ../.venv/bin/python -m anongw_shell``。

先装载/生成安装实例标识（恒定会话号的来源），再起回环监听；
key 全程走 env（``ANONGW_GATEWAY_KEY``），缺失时进程照起、请求期按
fail-closed 503 拒绝（见 server.py——便于先起壳再配 key 的部署顺序，
且缺 key 的失败对客户端可判别）。
"""
from __future__ import annotations

import argparse
import sys

import uvicorn

from anongw_shell.config import load_settings
from anongw_shell.identity import load_or_create
from anongw_shell.server import assert_loopback_bind, create_shell_app
from common.logs import setup_logging


def main(argv: list[str] | None = None) -> int:
    # Windows 编码纪律（与引擎 gateway.__main__ 同口径）：入口先重配 UTF-8
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        prog="anongw_shell",
        description="anongw-transparent 壳代理（T1：回环监听 + 恒定会话头注入 + 转发中继 + 泄漏计量）",
    )
    parser.add_argument("--host", default=None, help="监听地址（默认 127.0.0.1，非回环默认拒绝）")
    parser.add_argument("--port", type=int, default=None, help="监听端口（默认 8720）")
    parser.add_argument("--gateway-url", default=None, help="本机引擎网关（默认 http://127.0.0.1:9000）")
    parser.add_argument("--instance-file", default=None, help="实例标识保管文件（默认 data/instance.json）")
    args = parser.parse_args(argv)

    setup_logging("INFO")
    overrides: dict[str, str] = {}
    if args.host is not None:
        overrides["ANONGW_SHELL_LISTEN_HOST"] = args.host
    if args.port is not None:
        overrides["ANONGW_SHELL_LISTEN_PORT"] = str(args.port)
    if args.gateway_url is not None:
        overrides["ANONGW_SHELL_GATEWAY_URL"] = args.gateway_url
    if args.instance_file is not None:
        overrides["ANONGW_SHELL_INSTANCE_FILE"] = args.instance_file

    from common.config import load_env_file  # noqa: PLC0415 — 与引擎同序：.env 先于配置
    load_env_file()

    settings = load_settings(overrides)
    assert_loopback_bind(settings)
    identity = load_or_create(settings)
    app = create_shell_app(settings, identity=identity)

    print(f"anongw-transparent shell: instance={identity.instance_id} "
          f"listen={settings.listen_host}:{settings.listen_port} -> {settings.gateway_url}",
          file=sys.stderr)
    uvicorn.run(app, host=settings.listen_host, port=settings.listen_port,
                log_level="warning", access_log=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
