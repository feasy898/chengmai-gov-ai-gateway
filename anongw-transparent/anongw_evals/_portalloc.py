"""端口自分配基床（测试计划 V2-02）：绑 0 取闲端口 + 占用诊断。

M2§0.1 实测教训（t0_stream 5/14、t0_gateway 1/15 败于端口占用）：测试端口
一律自分配，不写死；冲突时打印占用者 PID 与命令行，便于人肉排障。
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time


def free_port(host: str = "127.0.0.1") -> int:
    """向内核要一个当前空闲的 TCP 端口（bind(:0) → getsockname → 关闭）。

    关闭与复用之间的竞窗属理论残余（V2-02 口径：冲突重试）；服务线程起在
    该端口上若 bind 失败会经 wait_ready 超时暴露，不静默。
    """
    for _ in range(20):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, 0))
            port = int(sock.getsockname()[1])
        # 竞窗自检：立刻重连试探，连不上（ refused）才认为真闲
        with socket.socket() as probe:
            probe.settimeout(0.2)
            if probe.connect_ex((host, port)) != 0:
                return port
        time.sleep(0.05)
    raise RuntimeError("no free port found after 20 attempts")


def free_ports(n: int, host: str = "127.0.0.1") -> list[int]:
    return [free_port(host) for _ in range(n)]


def port_owner_diagnosis(host: str, port: int) -> str:
    """占用者诊断（尽力而为）：ss → lsof → ps 逐级回退；都不可用返回提示。"""
    try:
        out = subprocess.run(
            ["ss", "-ltnp", f"sport = :{port}"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if out and str(port) in out:
            return f"ss: {out.splitlines()[-1]}"
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        out = subprocess.run(
            ["lsof", "-i", f"TCP:{port}", "-sTCP:LISTEN", "-P", "-n"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if out:
            return f"lsof: {out.splitlines()[-1]}"
    except (OSError, subprocess.SubprocessError):
        pass
    return f"port {port} busy on {host}; diagnosis tools unavailable (python {sys.version.split()[0]})"
