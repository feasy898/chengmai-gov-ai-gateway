"""anongw-transparent 阈值唯一来源（测试计划 V2-06：每常量须被消费）。

与引擎 evals/thresholds.py 分file同纪律：本工具的阈值一处可调；生产壳代码
（anongw_shell.server / anongw_shell.relay）也从这里取缓冲上限——与引擎
gateway/app.py import evals.thresholds 同款先例。

**单机单次毫秒数禁令**（测试计划 §1.4）：本文件不含任何单机单次实测数
（19ms/2ms/0.26ms 等禁入）；TTFT 两值是规划 §三e 的**预算**（质量线），
不是实测数——V4-01 的判定对象，不是阈值来源。
"""
from __future__ import annotations

# ── T1·壳层（t1_shell）─────────────────────────────────────────────
#: V1-02 会话头恒定性探测轮数（测试计划：连续 N（≥10）个请求）
T1_SHELL_PROBE_ROUNDS = 12

# ── T1/T3·往返（t1_roundtrip）──────────────────────────────────────
#: V3-01 curl 三轮对话轮数（规划 M1-#1 口径）
T1_ROUNDTRIP_ROUNDS = 3
#: 本地 mock 腿泄漏计数上限（规划 M1-#1：泄漏计数 = 0）
T1_LEAK_EXPECTED = 0

# ── T4·TTFT 增量（t4_perf_ttft，V4-01 差值法）──────────────────────
#: 成对采样对数（预算门 n；测试计划：预算门 n ≥ 200）
TTFT_PAIRS = 200
#: 预热丢弃对数（V4-01：预热 ≥20 次丢弃）
TTFT_WARMUP_PAIRS = 20
#: 请求侧 TTFT 增量 p50 预算（规划 §三e；质量线）
TTFT_P50_BUDGET_MS = 20
#: 请求侧 TTFT 增量 p95 预算（规划 §三e；质量线）
TTFT_P95_BUDGET_MS = 50
#: 请求体目标字节数（「20KB」取 **bytes** 口径——测试计划开放问题 M3§7.3
#: 登记在案：UTF-8 下字节/字符差 3 倍，owner 裁定前按 bytes 执行并如实报告）
TTFT_BODY_TARGET_BYTES = 20 * 1024

# ── 壳层缓冲上限（生产代码 anongw_shell 同源消费）───────────────────
#: 非流式响应计量缓冲上限（超限不计量只透传——计量面永不阻塞数据面）
SHELL_METER_MAX_RESPONSE_BYTES = 32 * 1024 * 1024
#: 壳请求体上限（与引擎 GATEWAY_BODY_MAX_BYTES 同量级；壳先拒，413）
SHELL_REQUEST_MAX_BYTES = 10 * 1024 * 1024

# ── E1 服从性快测（t1_e1_quick）────────────────────────────────────
#: E1 杀死线（规划 §四 M0 实验表：可配类 + env 服从类合计 < 2 → 杀死）
E1_CHANNEL_KILL_LINE = 2
