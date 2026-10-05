#!/usr/bin/env python3
"""门脚本共用：受管端口残留监听收割（gate_final / gate_d0 / gate_b1–b6 共用）。

背景（两代实锤，同一失败类）：
- run2 实锤（gate_final 原注）：门脚本是子进程，其异常退出路径留下的子进程
  本门够不到——e2e mock 就绪超时路径泄漏子进程 → 后续 m5 端点占用 FAIL；
- 2026-10-04 gate_final 实锤（tmp/wf/1791067555021）：另一会话的 eval 进程在
  门中途占住 :8901，首次命中在嵌套门 gate_b4 ⑥ m10_e2e——顶层每项前的收割
  帮不到**嵌套门内部的检查项**（gate_b4/gate_b3/gate_b2 各自再跑 m10_e2e/
  m5_outguard 等），端口占用一路级联成 3/9 FAIL。根因 = 收割粒度只到顶层项，
  嵌套门之间（最长数十分钟）无任何自愈点。

修法 = 收割函数抽平为本模块，各门脚本在**每项检查开跑前**调用（时序安全：
门内检查串行，此刻上一项自己的 mock 已随 finally 终止，受管端口上若有监听
必是非本门在跑的残留/并发进程——与 gate_final 既有收割口径同 policy）。
"""
from __future__ import annotations

import subprocess

#: 门间残留监听端口（e2e :9000/:8901/:8902/:9010；m11 专用 :9012/:9013/:8911-8913）。
#: 只收割门系列检查用到的端口，不碰其他（含 :9004 隧道）。
GATE_MANAGED_PORTS = (9000, 8901, 8902, 9010, 9012, 9013, 8911, 8912, 8913)


def reap_leftover_listeners() -> list[str]:
    """收割受管端口上的残留 LISTENING 进程（返回「端口<-pid」注记列表）。

    netstat 解析失败/无残留都安静返回；只对 :data:`GATE_MANAGED_PORTS` 生效。
    """
    reaped: list[str] = []
    try:
        proc = subprocess.run(["netstat", "-ano", "-p", "tcp"],
                              capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return reaped
    pid_by_port: dict[int, str] = {}
    for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[3].upper() != "LISTENING":
            continue
        for port in GATE_MANAGED_PORTS:
            if parts[1].endswith(f":{port}"):
                pid_by_port.setdefault(port, parts[4])
                break
    for port, pid in sorted(pid_by_port.items()):
        if not pid.isdigit() or pid == "0":
            continue
        try:
            subprocess.run(["taskkill", "/F", "/PID", pid],
                           capture_output=True, timeout=60)
            reaped.append(f"{port}<-pid {pid}")
        except (OSError, subprocess.TimeoutExpired):
            reaped.append(f"{port}<-pid {pid}(kill 失败)")
    return reaped
