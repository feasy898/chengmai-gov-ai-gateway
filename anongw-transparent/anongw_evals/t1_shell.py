"""T1·壳层单测（规划 §四M1 点名 t1_shell；测试计划 T1·A 接入层）。

运行::

    cd anongw-transparent && ../.venv/bin/python -m anongw_evals.t1_shell

exit 0 = 通过。检查项（用例号 = 测试计划 T1·A 表）：
1. fixture：mock 上游×2 + 引擎网关 + 壳三层栈拉起（端口全自分配 V2-02）；
   实例标识恒过引擎网关会话头形态闸（复用 gateway.app.SESSION_ID_RE 同一对象）；
2. V1-01 回环纪律：壳缺省监听 127.0.0.1；对本机非回环地址同端口 TCP 连接被拒
   （本机无非回环地址则如实 SKIP 记录，不冒充验证）；非回环 bind 默认拒绝、
   env 显式放行才可（assert_loopback_bind 运行时闸直测）；
3. V1-02 会话头恒定注入：连续 N=12 个请求经壳，网关回落头 x-anongw-session-id
   与审计事件 session_id **逐字节恒等**于安装实例标识；客户端自带会话头被壳
   覆盖（恒定注入语义）；**反例断言**：客户端直连网关（无壳）每请求现造
   sess_* 会话（gateway/app.py:385-389 行为）——壳的存在正是杀掉这条退化路径；
4. V1-03 转发保真：含敏感值请求经壳 → mock 上游实收 bytes 级零原值（ring 全文
   扫描）+ 占位符在位；客户端拿到还原原文；本地网关 key 不出现在上游实收
   （G2§一a-1：key 也是不该出网的敏感信息）；
   V1-06 干净文本进出壳逐字保真（直连网关与经壳响应 body 全等，零改写）；
5. V1-04 流式中继：stream=true 经壳——帧序保真（首帧 role 声明、逐内容帧、
   finish、[DONE] 收尾）、帧数与直连网关（同定切块 mock）一致（零丢帧）、
   组装文本与原文全等、帧结构 data: JSON 逐帧可解析；
6. V1-05 T2 安装/卸载快照：SKIP——T2 形态（CA 分发/env wrapper）属 M2 矩阵；
   T1 形态按设计零系统写入（无证书库/信任库/env 污染面），此处如实登记不测；
7. V1-07 故障可判别（半例，fail-open/closed 裁决前按「可判别」断言）：杀掉
   壳背后的网关 → 客户端收到显式 502 错误信封（不挂起、不静默成功）；
8. 泄漏计数器可见性：全程 mock 腿（干净还原链）后 /anongw/stats：
   requests_metered>0、total_hits=0（计数链出口在位；正例计数链在 t1_roundtrip）。

失败时指认的用户伤害（测试计划 T1·A 列）：接入层错 = 流量到不了/环境被改/
身份漂移，直接打穿「无感」承诺（各断言消息内写明）。
"""
from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(PKG_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("MOCK_KEY", "mock-demo-key")
os.environ["ANONGW_GATEWAY_KEY"] = "dk_5e6f7a8b"  # 演示部门 key（仓内文档化）

from anongw_evals._harness import (  # noqa: E402
    DEMO_KEY,
    MockUpstreamServer,
    ThreeTierStack,
    start_gateway,
    start_shell,
)
from anongw_evals._portalloc import free_ports  # noqa: E402
from anongw_evals.thresholds import T1_LEAK_EXPECTED, T1_SHELL_PROBE_ROUNDS  # noqa: E402
from masking.mapper import tolerant_placeholder_hits  # noqa: E402  # 仪器同尺（泄漏断言）

RESULTS: list[tuple[bool, str]] = []

INSTANCE_ID = "anongw-inst-" + "b" * 32  # eval 固定实例（生成/保管语义在 identity 自检）

PHONE = "138 0013 8000"                   # 分隔符写法（归一化 → 13800138000）
ID_OK = "11010519491231002X"              # 校验位合法样例号（与 t0_gateway 夹具同源）
SENSITIVE_TEXT = f"居民张三手机号{PHONE}，身份证{ID_OK}，请核对。"
CLEAN_TEXT = "今天下午三点召开全镇防汛工作会议，请各村干部参加。"


class SkipCase(Exception):
    """显式 SKIP + 原因（占位可见纪律，测试计划 §4.4——不允许静默缺席）。"""


def _record(name: str, fn) -> None:
    try:
        detail = fn()
        RESULTS.append((True, f"PASS  {name}" + (f" — {detail}" if detail else "")))
    except SkipCase as exc:
        RESULTS.append((True, f"SKIP  {name} — {exc}"))
    except Exception as exc:  # noqa: BLE001 — 汇总所有失败后统一退出
        RESULTS.append((False, f"FAIL  {name} — {type(exc).__name__}: {exc}"))


def _chat_body(text: str, *, stream: bool = False) -> dict[str, Any]:
    return {"model": "mock-chat", "stream": stream,
            "messages": [{"role": "user", "content": text}]}


def _nonloopback_addresses() -> list[str]:
    """本机非回环 IPv4 地址（尽力而为；空列表 = 无法验证非回环不可达）。"""
    addresses: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                addresses.add(ip)
    except OSError:
        pass
    try:  # UDP connect 技巧不发包也能取默认路由源地址
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            if not ip.startswith("127."):
                addresses.add(ip)
    except OSError:
        pass
    return sorted(addresses)


# ── 检查项 ────────────────────────────────────────────────────────

def check_identity_and_session_regex() -> str:
    """检查项 1b：实例标识生成恒过引擎网关会话头形态闸（单一事实源）。"""
    from anongw_shell import identity as ident
    from anongw_shell.identity import INSTANCE_ID_PREFIX, new_instance_id

    from gateway.app import SESSION_ID_RE

    assert ident.SESSION_ID_RE is SESSION_ID_RE, (
        "identity module must reuse gateway SESSION_ID_RE (不造平行实现)")
    generated = [new_instance_id() for _ in range(50)]
    for value in generated:
        assert SESSION_ID_RE.fullmatch(value), f"instance id violates gateway regex: {value}"
        assert value.startswith(INSTANCE_ID_PREFIX)
    return f"50 generated ids pass gateway SESSION_ID_RE ({SESSION_ID_RE.pattern})"


def check_v1_01_loopback_only() -> str:
    """V1-01：壳只听回环；非回环地址同端口不可达。"""
    from anongw_shell.config import LOOPBACK_HOSTS, ShellSettings
    from anongw_shell.server import assert_loopback_bind

    # 运行时闸：非回环默认拒绝；env 显式放行才通过
    for host in ("0.0.0.0", "192.168.1.10"):
        try:
            assert_loopback_bind(ShellSettings(listen_host=host))
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"non-loopback bind {host!r} must be refused by default")
    assert_loopback_bind(ShellSettings(listen_host="0.0.0.0", allow_non_loopback=True))
    for host in LOOPBACK_HOSTS:
        assert_loopback_bind(ShellSettings(listen_host=host))

    # 实测：运行中的壳（栈内 127.0.0.1 绑定）对非回环地址同端口不可达
    addresses = _nonloopback_addresses()
    with ThreeTierStack(instance_id=INSTANCE_ID) as stack:
        assert stack.shell is not None
        refused = 0
        for ip in addresses:
            with socket.socket() as sock:
                sock.settimeout(0.5)
                if sock.connect_ex((ip, stack.shell_port)) != 0:
                    refused += 1
    if not addresses:
        raise SkipCase("no non-loopback address detected on this host — loopback-only "
                       "bind verified via settings gate above")
    assert refused == len(addresses), (
        f"shell port reachable via non-loopback address(es): {refused}/{len(addresses)} refused")
    return f"{refused}/{len(addresses)} non-loopback addrs refused ({addresses[0]}…)"


def check_v1_02_session_header_constant() -> str:
    """V1-02：连续 N 个请求经壳，会话头恒等实例标识；反例：直连网关现造会话。"""
    sessions_seen: list[str] = []
    with ThreeTierStack(instance_id=INSTANCE_ID) as stack:
        assert stack.gateway is not None and stack.audit is not None
        for i in range(T1_SHELL_PROBE_ROUNDS):
            resp = stack.chat(_chat_body(f"第{i}轮：{CLEAN_TEXT}"))
            assert resp.status_code == 200, f"round {i}: {resp.status_code} {resp.text[:200]}"
            header_value = resp.headers.get("x-anongw-session-id")
            assert header_value is not None, f"round {i}: gateway session header missing"
            sessions_seen.append(header_value)
        # 审计事件侧（网关实际记账的 session 键）逐字节比对
        audit_sessions = [e.session_id for e in stack.audit.snapshot()]
        assert len(audit_sessions) == T1_SHELL_PROBE_ROUNDS
        for i, sid in enumerate(audit_sessions):
            assert sid == INSTANCE_ID, f"audit round {i}: session {sid!r} != instance id"
        # 客户端自带会话头被壳覆盖（恒定注入语义）
        resp = stack.chat(_chat_body(CLEAN_TEXT),
                          headers={"x-anongw-session-id": "sess_client_forged_123"})
        assert resp.headers.get("x-anongw-session-id") == INSTANCE_ID, (
            "client-supplied session header must be overridden by the shell")
    assert all(s == INSTANCE_ID for s in sessions_seen), (
        f"session header drifted across requests: {sorted(set(sessions_seen))}")

    # 反例断言：直连网关（无壳）每请求现造会话（sess_ 形态、逐请求漂移）——
    # 这正是壳要杀掉的 BROKEN 行为（规划 §2.2#2；M1 实测现造会话 coherence=BROKEN）
    with ThreeTierStack(instance_id=INSTANCE_ID) as stack:
        assert stack.gateway is not None
        direct_ids = []
        for i in range(3):
            resp = stack.chat(_chat_body(f"直连第{i}轮"), via_shell=False,
                              headers={"Authorization": f"Bearer {DEMO_KEY}"})
            direct_ids.append(resp.headers["x-anongw-session-id"])
    assert all(sid.startswith("sess_") for sid in direct_ids), direct_ids
    assert len(set(direct_ids)) == 3, "gateway without shell should mint per-request sessions"
    return (f"{T1_SHELL_PROBE_ROUNDS} rounds constant={INSTANCE_ID[:22]}…; "
            f"direct-gateway control mints 3 distinct sess_* ids (negative pinned)")


def check_v1_03_forwarding_fidelity() -> str:
    """V1-03+V1-06：请求体零改写、上游实收零原值零 key、响应还原保真。"""
    with ThreeTierStack(instance_id=INSTANCE_ID) as stack:
        assert stack.internet is not None
        resp = stack.chat(_chat_body(SENSITIVE_TEXT))
        assert resp.status_code == 200, resp.text[:300]
        answer = resp.json()["choices"][0]["message"]["content"]
        # 客户端拿到还原原文（mock 回显 → 还原后应含原值）；占位符形状零残留
        # （仪器 = tolerant_placeholder_hits 同尺；〔Mock上游回显〕是 mock 自身
        # 文案用的全角括号，无「标签·hex」两段结构，不算占位符形状）
        assert "13800138000" in answer or PHONE in answer, (
            f"restored answer lost the value: {answer!r}")
        assert ID_OK in answer, f"restored answer lost id: {answer!r}"
        residue = tolerant_placeholder_hits(answer)
        assert not residue, f"placeholder leaked to client: {residue} in {answer!r}"

        # 上游实收（ring 全文 bytes 级）：零原值、占位符在位、零本地 key
        upstream_texts = stack.internet.ring.texts()
        assert upstream_texts, "mock upstream saw no request"
        joined = "\n".join(upstream_texts)
        for original in ("13800138000", PHONE, ID_OK, "张三"):
            assert original not in joined, f"upstream received raw value: {original}"
        assert "〔手机号·" in joined or "〔人名·" in joined, (
            f"placeholder shape missing in upstream text: {joined[:200]!r}")
        assert DEMO_KEY not in joined, "local gateway key must never reach the upstream"

        # V1-06 干净文本：进出壳逐字保真——直连网关与经壳响应 body 全等（无实体零改写）。
        # mock 响应体的 id/created 每请求随机（协议字段，非壳经手面），掩码后比对；
        # 壳若改写字节（重排键/重编码/去空白）在掩码外任一处即暴露。
        import re as _re

        direct = stack.chat(_chat_body(CLEAN_TEXT), via_shell=False,
                            headers={"Authorization": f"Bearer {DEMO_KEY}",
                                     "x-anongw-session-id": "sess_direct_cmp"})
        via = stack.chat(_chat_body(CLEAN_TEXT))
        assert direct.status_code == via.status_code == 200

        def _mask(raw: bytes) -> str:
            text = raw.decode("utf-8")
            text = _re.sub(r'"id":\s*"chatcmpl-[0-9a-f]+"', '"id":<masked>', text)
            text = _re.sub(r'"created":\s*\d+', '"created":<masked>', text)
            return text

        assert _mask(direct.content) == _mask(via.content), (
            "clean-text response bytes differ between direct gateway and via shell "
            "(beyond mock's random id/created fields)")
    return ("upstream bytes zero raw values & zero gateway key; clean-text "
            "direct-vs-shell response bodies byte-equal")


def _frames_of(sse_text: str) -> list[str]:
    """SSE 文本 → 事件**载荷**列表（``data:`` 前缀已剥；[DONE] 哨兵原样）。"""
    events: list[str] = []
    for block in sse_text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        lines = [ln for ln in block.split("\n") if ln.startswith("data:")]
        assert lines, f"non-data SSE block: {block[:80]!r}"
        payload = "\n".join(ln[len("data:"):].lstrip() for ln in lines)
        events.append(payload)
    return events


def check_v1_04_stream_relay() -> str:
    """V1-04：SSE 帧序/帧结构保真、零丢帧、组装文本全等。"""
    with ThreeTierStack(instance_id=INSTANCE_ID, chunk_min=3, chunk_max=3) as stack:
        assert stack.gateway is not None
        via_frames = _frames_of(stack.chat_stream(_chat_body(SENSITIVE_TEXT, stream=True)))
        direct_frames = _frames_of(stack.chat_stream(
            _chat_body(SENSITIVE_TEXT, stream=True), via_shell=False,
            headers={"Authorization": f"Bearer {DEMO_KEY}",
                     "x-anongw-session-id": "sess_direct_stream"}))
        assert via_frames[-1] == "[DONE]", "stream must end with [DONE] sentinel"
        assert len(via_frames) == len(direct_frames), (
            f"frame count mismatch via shell ({len(via_frames)}) vs direct "
            f"({len(direct_frames)}) — lost/duplicated frames")
        assert len(via_frames) > 5, f"unexpectedly few frames: {len(via_frames)}"
        # 帧结构：逐帧 JSON 可解析；首帧 role 声明；finish 帧在位
        parsed = []
        for f in via_frames[:-1]:
            parsed.append(json.loads(f))  # 非 JSON 载荷此处即断言失败（帧结构破坏）
        assert parsed[0]["choices"][0]["delta"].get("role") == "assistant"
        finish_frames = [p for p in parsed if p["choices"][0].get("finish_reason")]
        assert finish_frames and finish_frames[-1]["choices"][0]["finish_reason"] == "stop"
        # 组装文本（客户端可见）== 还原原文（帧组装后口径）
        content = "".join(p["choices"][0]["delta"].get("content") or "" for p in parsed)
        assert "13800138000" in content and ID_OK in content, (
            f"assembled stream text lost values: {content[:120]!r}")
        assert not tolerant_placeholder_hits(content), (
            f"placeholder leaked in stream to client: {tolerant_placeholder_hits(content)}")
    return f"{len(via_frames)} frames relayed (== direct count), assembled text intact"


def check_v1_05_t2_install_skip() -> str:
    """V1-05：SKIP——T2 形态属 M2；T1 按设计零系统写入（如实登记，不静默缺席）。"""
    raise SkipCase("V1-05 targets T2 install/uninstall (CA store/env wrapper) — M2 scope; "
                   "T1 form has zero system-write surface by design (no CA, no trust store, "
                   "no persistent env), recorded here per visible-SKIP discipline")


def check_v1_07_fail_visible() -> str:
    """V1-07（半例）：壳背后的网关死亡 → 客户端收到显式 502 错误信封（可判别）。

    fail-open vs fail-closed 规划未裁决（F9 候补）——裁决前按「可判别」断言：
    不挂起、不静默成功，错误形状可解析。
    """
    internet_p, gov_p, gw_p, shell_p = free_ports(4)
    internet = MockUpstreamServer(internet_p).start()
    gov = MockUpstreamServer(gov_p).start()
    gw, _audit = start_gateway(internet_port=internet_p, govcloud_port=gov_p, port=gw_p)
    shell = start_shell(gateway_port=gw_p, port=shell_p, instance_id=INSTANCE_ID)
    try:
        ok = httpx.post(f"{shell.base_url}/v1/chat/completions",
                        json=_chat_body(CLEAN_TEXT), timeout=15.0)
        assert ok.status_code == 200, ok.text[:200]
        gw.stop()  # 杀网关（壳仍活着）
        dead = httpx.post(f"{shell.base_url}/v1/chat/completions",
                          json=_chat_body(CLEAN_TEXT), timeout=15.0)
        assert dead.status_code == 502, (
            f"gateway-down must surface as explicit 502, got {dead.status_code}")
        envelope = dead.json()
        assert "error" in envelope, f"unjudgable failure shape: {envelope}"
    finally:
        shell.stop()
        gw.stop()
        gov.stop()
        internet.stop()
    return "gateway killed → shell answers explicit 502 error envelope (no hang, no silent success)"


def check_stats_visibility() -> str:
    """检查项 8：/anongw/stats 泄漏计数器出口在位（干净 mock 腿 total_hits=0）。"""
    with ThreeTierStack(instance_id=INSTANCE_ID) as stack:
        for i in range(3):
            stack.chat(_chat_body(f"{CLEAN_TEXT}（第{i}轮）"))
            stack.chat(_chat_body(SENSITIVE_TEXT, stream=True))
        stats = stack.shell_stats()
    leak = stats["leak"]
    assert stats["instance_id"] == INSTANCE_ID
    assert leak["requests_metered"] >= 6, f"meter saw too few responses: {leak}"
    assert leak["total_hits"] == T1_LEAK_EXPECTED, (
        f"clean mock leg must meter zero leaks, got {leak['total_hits']}")
    assert leak["responses_with_hits"] == 0
    return (f"metered {leak['requests_metered']} responses, total_hits=0 "
            f"(count-chain egress live)")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    checks = [
        ("identity/session-regex reuse", check_identity_and_session_regex),
        ("V1-01 loopback-only bind", check_v1_01_loopback_only),
        ("V1-02 session header constant injection", check_v1_02_session_header_constant),
        ("V1-03+V1-06 forwarding fidelity", check_v1_03_forwarding_fidelity),
        ("V1-04 stream relay fidelity", check_v1_04_stream_relay),
        ("V1-05 T2 install (SKIP)", check_v1_05_t2_install_skip),
        ("V1-07 fail-visible (gateway down)", check_v1_07_fail_visible),
        ("stats visibility (leak counter egress)", check_stats_visibility),
    ]
    for name, fn in checks:
        _record(name, fn)
    print(f"\nT1 SHELL: {sum(1 for ok, _ in RESULTS if ok)}/{len(RESULTS)} checks passed")
    for _ok, line in RESULTS:
        print(line, flush=True)
    return 0 if all(ok for ok, _ in RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
