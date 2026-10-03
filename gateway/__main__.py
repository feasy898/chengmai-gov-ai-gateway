"""网关进程入口：``python -m gateway --port 9000``（加载 .env → config → uvicorn）。"""
from __future__ import annotations

import argparse
import sys

import uvicorn

from common.config import load_app_config, load_env_file
from common.logs import get_logger, setup_logging
from gateway.app import create_app

log = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    # Windows 编码纪律（与 ops.e2e_smoke / evals.gate_d0 同口径）：GBK 控制台
    # 重定向下中文 JSON 日志不得触发 logging 编码告警——入口先重配 UTF-8。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        prog="gateway",
        description="政务 AI 安全网关（OpenAI 兼容 /v1/chat/completions 代理）",
    )
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=None, help="监听端口（缺省取 config listen，默认 9000）")
    parser.add_argument("--config", default=None, help="主配置路径（缺省 config/app.yaml）")
    args: argparse.Namespace = parser.parse_args(argv)

    load_env_file()  # .env 预载（不覆盖已有环境变量）
    setup_logging("INFO")
    cfg = load_app_config(args.config)
    app = create_app(cfg=cfg)  # 内部解析 MASK_KEY；缺失时抛出明确错误
    port = args.port if args.port is not None else cfg.listen
    log.info("gateway.start", extra={"host": args.host, "port": port,
                                     "upstreams": [u.name for u in cfg.upstreams]})
    uvicorn.run(app, host=args.host, port=port, log_level="warning", access_log=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
