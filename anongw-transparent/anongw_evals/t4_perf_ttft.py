"""T4·TTFT 增量首测（V4-01 差值法；规划 §四M1 验收 #4「E4 完整版」；「先测先记」）。

运行::

    cd anongw-transparent && ../.venv/bin/python -m anongw_evals.t4_perf_ttft --upstream mock
    cd anongw-transparent && ../.venv/bin/python -m anongw_evals.t4_perf_ttft --upstream zhipu \
        --pairs 200        # 预算门口径；zhipu 腿需先 source llm-env 并 export ZHIPU_LLM_KEY

exit 0 = 预算内（质量线）；exit 1 = **如实红**（超预算，数字照报，不重跑到过）；
exit 2 = PRECOND-FAIL（zhipu key 未配置 / 上游不可达——不计失败，可跑时补）。

口径（测试计划 T4·V4-01）：
- **差值**是「无感」唯一可操作的定义：同一请求体 bytes，A 臂 = 客户端直连本机
  引擎网关，B 臂 = 客户端经壳（shell→gateway），逐对交错采样（A,B,A,B…），
  **每请求新建连接**（两臂对齐，连接策略差不入 Δ）；TTFT = 请求发出到响应
  首字节（stream=true，首 SSE 帧）；逐对差值 Δ = B−A，对 Δ 取分位；
- 预热 ≥ :data:`TTFT_WARMUP_PAIRS` 对丢弃（V4-02：预热显式且被钉住，打印
  冷/热 p99 比值进环境健康度）；预算门 n = :data:`TTFT_PAIRS` 对；
- 请求体 :data:`TTFT_BODY_TARGET_BYTES`（20KB 取 **bytes** 口径——测试计划
  开放问题 M3§7.3，owner 裁定前按 bytes 执行并如实报告）；
- 预算 = 规划 §三e（p50 ≤ 20ms / p95 ≤ 50ms），不是单机单次实测数（§1.4 禁令）。

测量载体纪律：单 loop 顺序采样（Linux 本机；V4-01 的「多 loop 平台 artifact」
禁令针对 Windows 后台线程 loop，本机形态不触）。
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(PKG_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("MOCK_KEY", "mock-demo-key")
os.environ["ANONGW_GATEWAY_KEY"] = "dk_5e6f7a8b"

from anongw_evals._harness import DEMO_KEY, ThreeTierStack  # noqa: E402
from anongw_evals.thresholds import (  # noqa: E402
    TTFT_BODY_TARGET_BYTES,
    TTFT_P50_BUDGET_MS,
    TTFT_P95_BUDGET_MS,
    TTFT_PAIRS,
    TTFT_WARMUP_PAIRS,
)

#: zhipu 真实腿（M0-实验报告 §2.0 同款：OpenAI 兼容 paas/v4 + glm-4-flash）
ZHIPU_MODEL = "glm-4-flash"
ZHIPU_KEY_ENV = "ZHIPU_LLM_KEY"
ZHIPU_BASE_ENV = "ZHIPU_LLM_BASE_URL"
ZHIPU_DEFAULT_BASE = "https://open.bigmodel.cn/api/coding/paas/v4"
#: 生成上限（TTFT 量的是首字节；小 max_tokens 压尾延迟，不压首字节口径）
MAX_TOKENS = 32

INSTANCE_ID = "anongw-inst-" + "d" * 32
#: 与两侧臂共享的固定会话（A 臂显式带头、B 臂由壳注入恒同值——映射态对齐，
#: Δ 只剩壳一跳）
SESSION_ID = "sess_t1_perf_fixed"

PHONE = "138 0013 8000"
ID_OK = "11010519491231002X"
#: 夹具只含 2 个 MASK 命中（NER 人名 + 手机号）——3 个命中会触发引擎批量 GOVCLOUD
#: 路由（config thresholds.batch_pii_to_govcloud=3），而 TTFT 测量栈只配 INTERNET 上游。
_BASE_SENT = ("关于乡镇低保审批的事项，经办人张三的联系电话是138 0013 8000，"
              "材料已收齐，请按流程复核并出具意见，"
              "同步抄送民政办与财政所归档备查。")


def _build_body_bytes(*, model: str) -> bytes:
    """确定性构造 ≥ 20KB 的请求体（bytes 口径；实体在文本中段，规则全链都过）。"""
    body: dict = {"model": model, "stream": True, "max_tokens": MAX_TOKENS,
                  "messages": [{"role": "user", "content": ""}]}
    content = ""
    filler = _BASE_SENT
    while True:
        body["messages"][0]["content"] = content
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        if len(raw) >= TTFT_BODY_TARGET_BYTES:
            return raw
        content += filler


def _percentile(sorted_values: list[float], p: float) -> float:
    """线性插值分位（样本已升序；n≥1）。"""
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(sorted_values) - 1)
    frac = k - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def measure_ttft_once(url: str, body: bytes, headers: dict[str, str]) -> float:
    """单次 TTFT（ms）：每请求新建连接（两臂对齐）；首响应字节计时，随后**排空整流**。

    排空纪律（实测教训，2026-10-06 本机）：只读首字节即断开会让网关的流收尾
    （还原后全文复检 + 审计落账）被推迟到**下一个请求**头上（对端 RST 后
    uvicorn 才通知 ASGI 断连），Δ 系统性假阴（B 臂反而"快" 50ms+）。两臂都
    排空后，收尾成本留在各自请求内，Δ 恢复为壳跳真实开销。
    """
    t0 = time.perf_counter()
    with httpx.Client(timeout=httpx.Timeout(connect=10.0, read=120.0, write=60.0, pool=60.0)) as client:
        with client.stream("POST", url, content=body,
                           headers={"content-type": "application/json", **headers}) as resp:
            if resp.status_code != 200:
                snippet = resp.read()[:200]
                raise RuntimeError(f"arm returned {resp.status_code}: {snippet!r}")
            ttft: float | None = None
            for _chunk in resp.iter_bytes():
                if ttft is None:
                    ttft = (time.perf_counter() - t0) * 1000.0
    if ttft is None:
        raise RuntimeError("empty response body (no first byte)")
    return ttft


def run_pairs(*, direct_url: str, shell_url: str, body: bytes,
              n_pairs: int, warmup_pairs: int) -> tuple[list[float], list[float], list[float]]:
    """交错 A/B 配对采样；返回 (deltas, arm_a_all, arm_b_all) 毫秒序列。"""
    headers_a = {"authorization": f"Bearer {DEMO_KEY}", "x-anongw-session-id": SESSION_ID}
    deltas: list[float] = []
    a_all: list[float] = []
    b_all: list[float] = []
    total = warmup_pairs + n_pairs
    for i in range(total):
        a = measure_ttft_once(direct_url, body, headers_a)
        b = measure_ttft_once(shell_url, body, headers_a)
        a_all.append(a)
        b_all.append(b)
        if i >= warmup_pairs:
            deltas.append(b - a)
        if (i + 1) % 25 == 0:
            print(f"  pair {i + 1}/{total}: A={a:.1f}ms B={b:.1f}ms Δ={b - a:+.1f}ms",
                  flush=True)
    return deltas, a_all, b_all


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="t4_perf_ttft")
    parser.add_argument("--upstream", choices=["mock", "zhipu"], default="mock")
    parser.add_argument("--pairs", type=int, default=TTFT_PAIRS)
    parser.add_argument("--warmup", type=int, default=TTFT_WARMUP_PAIRS)
    parser.add_argument("--shell-keepalive", choices=["on", "off"], default="off",
                        help="off=壳→网关每请求新建连接（V4-01 配臂对齐：Δ 只剩壳开销，"
                             "判定用）；on=生产形态（连接池收益入 Δ，记录用）")
    args = parser.parse_args(argv)

    model = ZHIPU_MODEL if args.upstream == "zhipu" else "mock-chat"
    body = _build_body_bytes(model=model)
    print(f"TTFT Δ harness: upstream={args.upstream} body={len(body)}B "
          f"(target {TTFT_BODY_TARGET_BYTES}B, bytes 口径) pairs={args.pairs} "
          f"warmup={args.warmup} shell-keepalive={args.shell_keepalive}")

    if args.upstream == "zhipu":
        key = os.environ.get(ZHIPU_KEY_ENV)
        if not key:
            print(f"PRECOND-FAIL: env {ZHIPU_KEY_ENV} not set "
                  "(source llm-env zhipu 并 export ZHIPU_LLM_KEY=\"$LLM_API_KEY\" 后重跑)",
                  flush=True)
            return 2
        base = os.environ.get(ZHIPU_BASE_ENV) or ZHIPU_DEFAULT_BASE
        # zhipu 腿：起独立栈（mock 上游端口占位不用），网关上游经 env 覆盖指 zhipu
        return _run_zhipu(base=base, key=key, body=body, pairs=args.pairs,
                          warmup=args.warmup, keepalive=args.shell_keepalive)
    return _run_mock(body=body, pairs=args.pairs, warmup=args.warmup,
                     keepalive=args.shell_keepalive)


def _report(deltas: list[float], a_all: list[float], b_all: list[float],
            *, leg: str) -> int:
    ds = sorted(deltas)
    p50 = _percentile(ds, 50)
    p95 = _percentile(ds, 95)
    p99 = _percentile(ds, 99)
    print(f"\n[{leg}] paired Δ distribution (n={len(ds)} pairs, ms):")
    print(f"  Δ p50={p50:.1f}  p95={p95:.1f}  p99={p99:.1f}  "
          f"min={ds[0]:.1f}  max={ds[-1]:.1f}  mean={statistics.fmean(ds):.1f}")
    print(f"  absolute: A p50={_percentile(sorted(a_all), 50):.1f}ms "
          f"B p50={_percentile(sorted(b_all), 50):.1f}ms")
    print(f"  V4-02 noise discipline: first-2-pairs max="
          f"{max(a_all[:2] + b_all[:2]):.1f}ms vs overall max={max(a_all + b_all):.1f}ms "
          "(预热样本已丢弃，不进分布)")
    budget_ok = p50 <= TTFT_P50_BUDGET_MS and p95 <= TTFT_P95_BUDGET_MS
    verdict = ("PASS（预算内）" if budget_ok else
               "FAIL（如实红：超规划 §三e 预算——数字照报，不重跑到过）")
    print(f"  budget: p50 ≤ {TTFT_P50_BUDGET_MS}ms / p95 ≤ {TTFT_P95_BUDGET_MS}ms → {verdict}")
    return 0 if budget_ok else 1


def _run_mock(*, body: bytes, pairs: int, warmup: int, keepalive: str) -> int:
    keepalive_n = 16 if keepalive == "on" else 0
    with ThreeTierStack(instance_id=INSTANCE_ID) as stack:
        assert stack.shell is not None and stack.gateway is not None
        # 重起壳（栈缺省形态 → 本轮测量形态）
        stack.shell.stop()
        from anongw_evals._harness import start_shell

        stack.shell = start_shell(gateway_port=stack.gateway_port, port=stack.shell_port,
                                  instance_id=INSTANCE_ID, meter=stack.meter,
                                  keepalive_connections=keepalive_n)
        direct_url = f"{stack.gateway.base_url}/v1/chat/completions"
        shell_url = f"{stack.shell.base_url}/v1/chat/completions"
        deltas, a_all, b_all = run_pairs(direct_url=direct_url, shell_url=shell_url,
                                         body=body, n_pairs=pairs, warmup_pairs=warmup)
        stats = stack.shell_stats()
    print(f"  shell meter during run: requests_metered={stats['leak']['requests_metered']} "
          f"total_hits={stats['leak']['total_hits']}")
    return _report(deltas, a_all, b_all,
                   leg=f"mock 腿（gw :{stack.gateway_port} / shell :{stack.shell_port}, "
                       f"keepalive={keepalive}）")


def _run_zhipu(*, base: str, key: str, body: bytes, pairs: int, warmup: int,
               keepalive: str) -> int:
    import httpx as _httpx

    from anongw_evals._harness import start_shell
    from anongw_evals._portalloc import free_ports
    from common.config import AppConfig, UpstreamCfg
    from gateway.app import create_app
    from masking.mapper import SessionRegistry

    # 先负控：zhipu 直连可达性（PRECOND-FAIL 语义，不冒充 FAIL）
    probe_body = json.dumps({"model": ZHIPU_MODEL, "max_tokens": 8,
                             "messages": [{"role": "user", "content": "ping"}]},
                            ensure_ascii=False).encode("utf-8")
    try:
        with _httpx.Client(timeout=30.0) as c:
            r = c.post(f"{base.rstrip('/')}/chat/completions", content=probe_body,
                       headers={"content-type": "application/json",
                                "authorization": f"Bearer {key}"})
        if r.status_code != 200:
            print(f"PRECOND-FAIL: zhipu upstream returned {r.status_code}: {r.text[:160]}",
                  flush=True)
            return 2
    except _httpx.HTTPError as exc:
        print(f"PRECOND-FAIL: zhipu unreachable: {type(exc).__name__}", flush=True)
        return 2

    internet_p, gov_p, gw_p, shell_p = free_ports(4)
    cfg = AppConfig(
        listen=0, mask_key_env="MASK_KEY", session_ttl_h=24,
        upstreams=[UpstreamCfg(name="internet_zhipu", base_url=base,
                               api_key_env=ZHIPU_KEY_ENV, models=[ZHIPU_MODEL],
                               route="INTERNET")],
    )
    os.environ[ZHIPU_KEY_ENV] = key
    from audit.store import InMemoryAuditStore  # noqa: PLC0415 — 内存审计，不落仓内 data/

    app = create_app(cfg=cfg, mask_key="cd" * 32,
                     audit_store=InMemoryAuditStore(),
                     session_registry=SessionRegistry(("cd" * 32).encode("utf-8")))
    from anongw_evals._harness import UvicornFixture

    gw = UvicornFixture(app, host="127.0.0.1", port=gw_p, name="gateway-zhipu",
                        health_path="/healthz").start()
    shell = start_shell(gateway_port=gw_p, port=shell_p, instance_id=INSTANCE_ID,
                        keepalive_connections=16 if keepalive == "on" else 0)
    try:
        direct_url = f"http://127.0.0.1:{gw_p}/v1/chat/completions"
        shell_url = f"http://127.0.0.1:{shell_p}/v1/chat/completions"
        deltas, a_all, b_all = run_pairs(direct_url=direct_url, shell_url=shell_url,
                                         body=body, n_pairs=pairs, warmup_pairs=warmup)
    finally:
        shell.stop()
        gw.stop()
    return _report(deltas, a_all, b_all,
                   leg=f"zhipu 真实腿（{base}, keepalive={keepalive}）")


if __name__ == "__main__":
    sys.exit(main())
