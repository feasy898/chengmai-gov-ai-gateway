"""T1·协议面契约 + T3·curl 回路（规划 §四M1 点名 t1_roundtrip；测试计划 T1·B/C、T3·V3-01）。

运行::

    cd anongw-transparent && ../.venv/bin/python -m anongw_evals.t1_roundtrip

exit 0 = 通过。检查项（用例号 = 测试计划表；M1-#1 验收口径）：
1. V3-01/V1-08 值级恒同：**三轮对话**（历史累积的多轮 messages，等价 curl 同款
   载荷）经壳 → 各轮上游实收中同值占位符**恒同**（值级语义：跨轮不漂移）；
   客户端各轮拿到还原原文，占位符形状零残留；
2. V1-13 归一化等价：第 1 轮写「138 0013 8000」、第 3 轮写「13800138000」——
   同 normalized → 同占位符；还原为归一化形态（基线 §2.2 口径，非逐字还原）；
3. M1-#1 泄漏计数 = 0（本地 mock 腿）：三轮后 /anongw/stats total_hits == 0；
4. V0-05 计数链正例（对账）：夹带「查表未命中的占位符形状」（伪造 hex）→
   引擎还原面按「宁残留不错还」放行 → 客户端可见 → 壳计数器 **同轮计数**：
   面板数 = 客户端可见数（对账口径，零明文——证据串只含形状键）；
5. V1-11 错还原负例族：伪 hex / hex 补零扩展 / 换标签+未知 digest → 一律
   原样放行，**绝不还原出错误原值**（错还原率=0 一票否决项的用例化；
   digest 即身份：真实 digest + 变形标签走副索引还原同值属设计语义，见
   masking/mapper.lookup，不在负例族内）；
6. V7-01（lite）审计零明文抽检：三轮的审计 preview bytes 级扫描零原值。

失败时指认的用户伤害：用户在自己终端里看到占位符/错还原 → 「无感」当场穿帮；
面板数与事实不符 → 工具在骗人（§1.2-#5 一等原则）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(PKG_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("MOCK_KEY", "mock-demo-key")
os.environ["ANONGW_GATEWAY_KEY"] = "dk_5e6f7a8b"

from anongw_evals._harness import ThreeTierStack  # noqa: E402
from anongw_evals.thresholds import T1_LEAK_EXPECTED, T1_ROUNDTRIP_ROUNDS  # noqa: E402
from masking.mapper import tolerant_placeholder_hits  # noqa: E402  # 内核复用（对账同尺）

RESULTS: list[tuple[bool, str]] = []

INSTANCE_ID = "anongw-inst-" + "c" * 32

PHONE_A = "138 0013 8000"        # 分隔符写法（第 1/2 轮）
PHONE_B = "13800138000"          # 同值连写（第 3 轮；归一化等价靶）
NAME = "王建国"
ADDRESS = "朝阳区幸福路 12 号"
ID_OK = "11010519491231002X"

#: 三轮对话（messages 历史累积——真实多轮形态；同值跨轮复现 = V3-01 主靶）。
#: 人名每次提及都带「我叫」锚定语境——无锚定形态（「王建国的手机号」）是引擎
#: NER 层现状召回缺口（规划 §2.2#4 开放词表面），会让已检出值以原样落进
#: response_preview 触发审计零明文硬闸（500）；本 eval 钉的是壳层值级恒同，
#: 不钉引擎召回缺口（缺口归 E3/M4），夹具按可检出形态构造。
ROUNDS: list[list[dict[str, str]]] = [
    [{"role": "user",
      "content": f"你好，我叫{NAME}，住{ADDRESS}。我的手机号是{PHONE_A}，请帮我登记。"}],
    [
        {"role": "user",
         "content": f"你好，我叫{NAME}，住{ADDRESS}。我的手机号是{PHONE_A}，请帮我登记。"},
        {"role": "assistant", "content": "已登记您的信息。"},
        {"role": "user", "content": f"再确认一下：我叫{NAME}，手机号是{PHONE_A}，对吗？"},
    ],
    [
        {"role": "user",
         "content": f"你好，我叫{NAME}，住{ADDRESS}。我的手机号是{PHONE_A}，请帮我登记。"},
        {"role": "assistant", "content": "已登记您的信息。"},
        {"role": "user", "content": f"再确认一下：我叫{NAME}，手机号是{PHONE_A}，对吗？"},
        {"role": "assistant", "content": "确认无误。"},
        {"role": "user",
         "content": f"最后核对：我叫{NAME}，住{ADDRESS}，手机号{PHONE_B}，身份证{ID_OK}。"},
    ],
]


def _record(name: str, fn) -> None:
    try:
        detail = fn()
        RESULTS.append((True, f"PASS  {name}" + (f" — {detail}" if detail else "")))
    except Exception as exc:  # noqa: BLE001 — 汇总所有失败后统一退出
        RESULTS.append((False, f"FAIL  {name} — {type(exc).__name__}: {exc}"))


def _chat_body(messages: list[dict[str, str]], *, stream: bool = False) -> dict[str, Any]:
    return {"model": "mock-chat", "stream": stream, "messages": messages}


def _phone_placeholder(text: str) -> str | None:
    """从上游实收文本中取「手机号」占位符（hex 段）；无则 None。"""
    hits = [h for h in tolerant_placeholder_hits(text) if h.startswith("〔手机号·")]
    return hits[0] if hits else None


def check_v3_01_v1_08_value_constancy() -> str:
    """检查项 1+2：三轮对话同值占位符恒同 + 归一化等价 + 客户端零残留。"""
    per_round_phone_ph: list[str] = []
    per_round_answers: list[str] = []
    with ThreeTierStack(instance_id=INSTANCE_ID) as stack:
        assert stack.internet is not None
        for i, messages in enumerate(ROUNDS[:T1_ROUNDTRIP_ROUNDS]):
            resp = stack.chat(_chat_body(messages))
            assert resp.status_code == 200, f"round {i}: {resp.status_code} {resp.text[:200]}"
            answer = resp.json()["choices"][0]["message"]["content"]
            per_round_answers.append(answer)
            # 上游实收：取本轮请求中的「手机号」占位符
            ring_texts = stack.internet.ring.texts()
            assert ring_texts, f"round {i}: upstream saw nothing"
            ph = _phone_placeholder(ring_texts[-1])
            assert ph is not None, (
                f"round {i}: no phone placeholder in upstream text: {ring_texts[-1][:200]!r}")
            per_round_phone_ph.append(ph)
            # 客户端可见：零占位符形状残留（并集口径仪器 = tolerant_placeholder_hits）
            residue = tolerant_placeholder_hits(answer)
            assert not residue, f"round {i}: placeholder residue on client screen: {residue}"
        # 恒同断言：三轮（含连写/分隔符两种写法）占位符逐字节相等
        assert len(set(per_round_phone_ph)) == 1, (
            f"value-level key broken — placeholder drifted across rounds: {per_round_phone_ph}")
        # 归一化等价：客户端各轮还原文本含归一化形态（基线 §2.2 口径，非逐字）
        for i, answer in enumerate(per_round_answers):
            assert PHONE_B in answer, (
                f"round {i}: restored text not normalization-equivalent: {answer[:120]!r}")
        # 上游 bytes 级零原值（全文扫描，含 system/历史轮）。
        # 注：住址「朝阳区幸福路 12 号」是 NER 层现状不召回的开放词表实体
        # （规则层零命中——规划 §2.2#4 的 39.8% 缺口在夹具里的如实显形），
        # 不进零原值断言；其余四值（两种手机写法/人名/身份证）必须全被脱敏。
        joined = "\n".join(stack.internet.ring.texts())
        for original in (PHONE_A, PHONE_B, NAME, ID_OK):
            assert original not in joined, f"upstream received raw value: {original}"
    return (f"{T1_ROUNDTRIP_ROUNDS} rounds → placeholder {per_round_phone_ph[0][:14]}…… 恒同；"
            f"客户端还原归一化等价、零残留")


def check_m1_leak_zero() -> str:
    """检查项 3：M1-#1 泄漏计数 = 0（本地 mock 腿，独立栈）。"""
    with ThreeTierStack(instance_id=INSTANCE_ID) as stack:
        for messages in ROUNDS[:T1_ROUNDTRIP_ROUNDS]:
            resp = stack.chat(_chat_body(messages))
            assert resp.status_code == 200
        stats = stack.shell_stats()
    leak = stats["leak"]
    assert leak["requests_metered"] == T1_ROUNDTRIP_ROUNDS, (
        f"meter should have seen exactly the 3 responses, saw {leak['requests_metered']}")
    assert leak["total_hits"] == T1_LEAK_EXPECTED, (
        f"M1-#1 violated: leak counter = {leak['total_hits']} (expected {T1_LEAK_EXPECTED})")
    assert leak["responses_with_hits"] == 0
    return (f"3 round-trips metered, leak counter = {leak['total_hits']} "
            f"(M1-#1 泄漏计数=0 达成，mock 腿)")


def check_v0_05_count_chain() -> str:
    """检查项 4：计数链正例对账——伪造 hex 占位符穿透 → 壳计数同轮可见。"""
    forged = "〔人名·deadbeef00〕"          # 形状可辨、查表必未命中（hex 不在映射表）
    text = f"请原样回显此标记：{forged}（测试用）。"
    with ThreeTierStack(instance_id=INSTANCE_ID) as stack:
        resp = stack.chat(_chat_body([{"role": "user", "content": text}]))
        assert resp.status_code == 200
        answer = resp.json()["choices"][0]["message"]["content"]
        client_visible = tolerant_placeholder_hits(answer)
        assert any("deadbeef00" in h for h in client_visible), (
            f"forged shape should pass through untouched and be visible, got: {answer[:160]!r}")
        stats = stack.shell_stats()
    leak = stats["leak"]
    panel_count = leak["total_hits"]
    assert panel_count >= 1, (
        f"count chain broken: client sees {len(client_visible)} residue(s) but panel = {panel_count}")
    # 对账：面板数 = 客户端可见数（同尺同轮；不做方向性上限——本例恰为 1:1）
    assert panel_count == len(client_visible), (
        f"panel ({panel_count}) != client-visible ({client_visible})")
    # 证据串零明文：只含占位符形状键（deadbeef00 hex + 标签），不含原值
    for event in leak["recent_events"]:
        for hit in event["hits"]:
            assert "·" in hit and hit.startswith("〔"), f"evidence not shape-only: {hit!r}"
    return (f"forged {forged} passed through; panel {panel_count} == client-visible "
            f"{len(client_visible)}; evidence strings shape-only (零明文)")


def check_v1_11_wrong_restore_negatives() -> str:
    """检查项 5：错还原负例族——未知 digest/补零扩展/换标签 → 原样放行。"""
    # 三条负例：伪 hex、真实 digest 补零扩展（扩写幻觉）、换标签+未知 digest
    # （真实 digest + 变形标签 = 副索引/digest 身份语义，还原同值非错还原——不列负例）
    fakes = [
        "〔手机号·0123abcd〕",        # 伪 hex（表外）
        "〔身份证·ffffffffFFFF〕",    # 表外 hex + 大写转写（canonical 后仍表外）
        "〔文号·1234567890abcd〕",    # 12 位扩写幻觉（表外）
    ]
    with ThreeTierStack(instance_id=INSTANCE_ID) as stack:
        for fake in fakes:
            text = f"标记测试：{fake} 请原样回显。"
            resp = stack.chat(_chat_body([{"role": "user", "content": text}]))
            assert resp.status_code == 200
            answer = resp.json()["choices"][0]["message"]["content"]
            canonical = fake.replace("FFFF", "ffff")
            assert canonical in answer or any(
                "·" in h for h in tolerant_placeholder_hits(answer)), (
                f"unknown digest must pass through untouched, got: {answer[:160]!r}")
            # 错还原率=0：回复中不得出现任何夹具原值（未注入过任何映射）
            for original in (PHONE_A, PHONE_B, NAME, ID_OK):
                assert original not in answer, (
                    f"wrong-restore! fake {fake} produced value {original}")
        stats = stack.shell_stats()
    # 这些穿透即泄漏形状：壳应计数（形状级披露口径），面板与屏幕一致
    assert stats["leak"]["total_hits"] >= len(fakes), (
        f"pass-through fakes must be metered, panel={stats['leak']['total_hits']}")
    return (f"{len(fakes)} fake shapes passed through untouched (宁残留不错还) "
            f"and metered ({stats['leak']['total_hits']} hits)")


def check_v7_01_audit_no_plaintext() -> str:
    """检查项 6：审计 preview bytes 级零原值（m7 口径 lite；全量 m7 在引擎侧）。"""
    with ThreeTierStack(instance_id=INSTANCE_ID) as stack:
        assert stack.audit is not None
        for messages in ROUNDS[:T1_ROUNDTRIP_ROUNDS]:
            stack.chat(_chat_body(messages))
        events = stack.audit.snapshot()
    assert len(events) >= T1_ROUNDTRIP_ROUNDS
    for event in events:
        for preview in (event.prompt_preview, event.response_preview):
            for original in (PHONE_A, PHONE_B, NAME, ID_OK):
                assert original not in (preview or ""), (
                    f"audit preview contains raw value {original!r}: {preview[:120]!r}")
    return f"{len(events)} audit events scanned, zero raw values in previews"


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    checks = [
        ("V3-01/V1-08 三轮同值恒同 + 归一化等价", check_v3_01_v1_08_value_constancy),
        ("M1-#1 泄漏计数 = 0（mock 腿）", check_m1_leak_zero),
        ("V0-05 计数链正例对账", check_v0_05_count_chain),
        ("V1-11 错还原负例族（原样放行）", check_v1_11_wrong_restore_negatives),
        ("V7-01(lite) 审计零明文抽检", check_v7_01_audit_no_plaintext),
    ]
    for name, fn in checks:
        _record(name, fn)
    print(f"\nT1 ROUNDTRIP: {sum(1 for ok, _ in RESULTS if ok)}/{len(RESULTS)} checks passed")
    for _ok, line in RESULTS:
        print(line, flush=True)
    return 0 if all(ok for ok, _ in RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
