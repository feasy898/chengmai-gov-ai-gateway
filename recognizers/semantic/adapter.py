"""语义适配器（开发指令 §6 M2）：prompt/文本语义审核入口（T4.2 第一档落地）。

实现口径（铁律 D：MVP 识别只做规则层；语义层走适配器，**严禁拉真模型**）：

- **第一档规则词表**（:mod:`recognizers.semantic.patterns`）：STRONG/EXFIL 任意
  位置命中即判，WEAK 须位置启发佐证；否定前缀守卫压误拦。产出
  ``type=INJECTION、layer="semantic"、action_hint="BLOCK_FLAG"`` 的
  :class:`~recognizers.models.Finding`——路由决策矩阵 R2（§5.2：INJECTION →
  BLOCK，记录 flag=injection）在 ``routing.engine.decide`` 原生消费，本层零改动
  即完成「拦截进 decide」。
- **LLM-judge 升档位**（:mod:`recognizers.semantic.judge`，env 驱动）：
  ``SEMANTIC_JUDGE_*`` 三变量齐备才启用；**无 key 降级词表**（零网络行为）；
  judge 仅在词表零命中时补判一次（词表已命中无需再问），judge 故障按词表
  结果降级、不抛错。judge 补判命中产出**无 span** 的整段 finding（``raw=""``，
  语义判定无字符级定位，raw 留空即不进表面形式清单/审计预览替换面）。
<<<<<<< 8340533e2268ad9f14f101eb696538bea1e8d9ab
  judge 端点可能为外部服务：补判收到的文本先按规则层命中把 PII/密级表面
  形式替换为中性占位（审查加固：原文不在脱敏/BLOCK 判定前出网，见
  :meth:`SemanticAdapter._redact_for_judge`）。
=======
>>>>>>> 47048f64cf6ee1fff8757a2565bf59d4c0003972
- **接口形状不变**（P0 冻结）：``moderate(text) -> {verdict, categories}``，
  verdict ∈ {"safe", "flagged"}；``config.app.moderation_model`` 指向的本地
  guard 模型属后续任务，本层 MVP 不加载任何本地模型（传入 model_path 仅记录
  不生效，与 NER 适配器同款「显式声明未加载」口径）。

类别码（categories 值域）：INJECTION_OVERRIDE（指令覆盖/接管/窃取/隐匿）、
INJECTION_EXFIL（工具诱导外发/内容走私）、INJECTION_EMBEDDED（位置佐证的
文档内嵌指令）、INJECTION_JUDGE（judge 补判命中）。
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from common.logs import get_logger
from recognizers.models import EntityClass, Finding
from recognizers.semantic.judge import LlmJudge
from recognizers.semantic.patterns import (
    KIND_EXFIL,
    KIND_STRONG,
    KIND_WEAK,
    corroborated,
    get_injection_patterns,
    is_negated,
)

log = get_logger(__name__)

#: 风险类别码（moderate().categories 值域）
CATEGORY_OVERRIDE = "INJECTION_OVERRIDE"
CATEGORY_EXFIL = "INJECTION_EXFIL"
CATEGORY_EMBEDDED = "INJECTION_EMBEDDED"
CATEGORY_JUDGE = "INJECTION_JUDGE"

#: 档位 → 风险类别码
_KIND_CATEGORY = {
    KIND_STRONG: CATEGORY_OVERRIDE,
    KIND_EXFIL: CATEGORY_EXFIL,
    KIND_WEAK: CATEGORY_EMBEDDED,
}

#: 置信度口径：词表强特征/外发链 = 1.0；位置佐证的弱特征 = 0.7；judge 补判 = 0.9
_CONFIDENCE = {KIND_STRONG: 1.0, KIND_EXFIL: 1.0, KIND_WEAK: 0.7}
_JUDGE_CONFIDENCE = 0.9


class SemanticAdapter:
    """语义审核适配器：第一档规则词表 + env 驱动的 LLM-judge 升档位。"""

    def __init__(self, model_path: str | None = None, *,
                 judge: Any = None) -> None:
        self.model_path = model_path
        if model_path:
            # 本层 MVP 不加载本地 guard 模型（铁律 D）：显式声明未加载，而非静默
            log.debug("semantic_adapter.model_path_ignored_mvp",
                      extra={"model_path": model_path})
        # judge：显式注入优先（测试/组装形态）；缺省按 env 构建（无 key → None 降级）
        self._judge = judge if judge is not None else LlmJudge.from_env()

    # ── 契约入口（P0 冻结形状）────────────────────────────────────
<<<<<<< 8340533e2268ad9f14f101eb696538bea1e8d9ab
    def moderate(self, text: str, *, rule_findings: Sequence[Finding] = ()) -> dict[str, Any]:
        """语义审核：``{"verdict": "safe"|"flagged", "categories": [str]}``。

        词表命中即 flagged；词表零命中且 judge 已配置时补判一次（judge 故障
        降级为词表结果）。``rule_findings`` 为调用方已有的规则层命中——judge
        端点可能为外部服务，补判前把其中 PII/密级词表面形式替换为中性占位
        （审查加固：原文不在脱敏/BLOCK 判定前出网到 judge）。categories 见
        模块 docstring 值域。
        """
        findings, categories = self._scan(text)
        if not findings:
            judge_verdict, judge_categories = self._judge_lookup(
                self._redact_for_judge(text, rule_findings))
=======
    def moderate(self, text: str) -> dict[str, Any]:
        """语义审核：``{"verdict": "safe"|"flagged", "categories": [str]}``。

        词表命中即 flagged；词表零命中且 judge 已配置时补判一次（judge 故障
        降级为词表结果）。categories 见模块 docstring 值域。
        """
        findings, categories = self._scan(text)
        if not findings:
            judge_verdict, judge_categories = self._judge_lookup(text)
>>>>>>> 47048f64cf6ee1fff8757a2565bf59d4c0003972
            if judge_verdict == "flagged":
                return {"verdict": "flagged",
                        "categories": sorted(set(judge_categories) | {CATEGORY_JUDGE})}
        return {"verdict": "flagged" if findings else "safe", "categories": categories}

    # ── finding 级视图（网关主链路消费；fid 恒空串由调用方编号）────
<<<<<<< 8340533e2268ad9f14f101eb696538bea1e8d9ab
    def detect(self, text: str, *,
               rule_findings: Sequence[Finding] = ()) -> list[Finding]:
        """注入检测：返回 INJECTION Finding 列表（start 升序、span 去重）。

        词表命中带精确 span；judge 补判命中为整段无 surface finding（raw=""）。
        ``rule_findings``：规则层命中（judge 补判前据此脱敏，见 :meth:`moderate`）。
        """
        findings, _ = self._scan(text)
        if not findings:
            judge_verdict, _ = self._judge_lookup(
                self._redact_for_judge(text, rule_findings))
=======
    def detect(self, text: str) -> list[Finding]:
        """注入检测：返回 INJECTION Finding 列表（start 升序、span 去重）。

        词表命中带精确 span；judge 补判命中为整段无 surface finding（raw=""）。
        """
        findings, _ = self._scan(text)
        if not findings:
            judge_verdict, _ = self._judge_lookup(text)
>>>>>>> 47048f64cf6ee1fff8757a2565bf59d4c0003972
            if judge_verdict == "flagged" and text:
                findings.append(Finding(
                    fid="", type=EntityClass.INJECTION, layer="semantic",
                    start=0, end=len(text), raw="", normalized="",
                    confidence=_JUDGE_CONFIDENCE, action_hint="BLOCK_FLAG",
                ))
        return findings

    # ── 内部 ─────────────────────────────────────────────────────
    def _scan(self, text: str) -> tuple[list[Finding], list[str]]:
        """第一档词表扫描：返回（span 去重 findings, 类别码）。

        STRONG/EXFIL 直判，WEAK 位置佐证，否定守卫压误拦；类别码按命中模式
        档位映射（OVERRIDE/EXFIL/EMBEDDED，按档位优先级去重）。
        """
        if not text:
            return [], []
        found: list[Finding] = []
        kinds: set[str] = set()
        for kind, rx in get_injection_patterns():
            for m in rx.finditer(text):
                if kind == KIND_WEAK and not corroborated(text, m.start()):
                    continue
                if is_negated(text, m.start()):
                    continue
                kinds.add(kind)
                found.append(Finding(
                    fid="", type=EntityClass.INJECTION, layer="semantic",
                    start=m.start(), end=m.end(), raw=text[m.start():m.end()],
                    normalized=text[m.start():m.end()],
                    confidence=_CONFIDENCE[kind], action_hint="BLOCK_FLAG",
                ))
        categories = sorted(
            _KIND_CATEGORY[k] for k in kinds
            if k in _KIND_CATEGORY
        )
        return self._dedupe(found), categories

    def _judge_lookup(self, text: str) -> tuple[str, list[str]]:
        """judge 补判（仅在配置了端点时）；任何故障降级为 safe + 大声记日志。"""
        if self._judge is None or not text:
            return "safe", []
        try:
            verdict: dict[str, Any] = self._judge.judge(text)
        except Exception as exc:  # noqa: BLE001 — 降级不抛（判定链路绝不因 judge 故障崩）
            log.warning("semantic_judge.degrade",
                        extra={"exc_type": type(exc).__name__})
            return "safe", []
        return str(verdict.get("verdict", "safe")), [
            str(c) for c in verdict.get("categories", []) if isinstance(c, str)
        ]

    @staticmethod
<<<<<<< 8340533e2268ad9f14f101eb696538bea1e8d9ab
    def _redact_for_judge(text: str, rule_findings: Sequence[Finding]) -> str:
        """judge 补判前的脱敏（审查加固）：规则层 PII/密级表面形式 → 中性占位。

        judge 端点（``SEMANTIC_JUDGE_BASE_URL``）可能为外部服务：未脱敏原文
        在路由 BLOCK / 会话脱敏**之前**发往 judge 即构成原文外发面（含最终被
        403 拦截的密级文本）。此处把非白名单的 MASK/BLOCK_FLAG 命中面按 span
        倒序替换为 ``〔脱敏〕``——注入指令文本不受影响（judge 只判注入语义）；
        词表判定仍在原文上进行，位置语义不变。
        """
        spans = [(f.start, f.end) for f in rule_findings
                 if not f.whitelisted and f.action_hint in ("MASK", "BLOCK_FLAG")
                 and f.end > f.start]
        if not spans:
            return text
        out = text
        for start, end in sorted(spans, reverse=True):
            out = out[:start] + "〔脱敏〕" + out[end:]
        return out

    @staticmethod
=======
>>>>>>> 47048f64cf6ee1fff8757a2565bf59d4c0003972
    def _dedupe(findings: list[Finding]) -> list[Finding]:
        """span 去重：多条模式命中同一/重叠区间时保留首条（start 升序、长者优先）。"""
        ordered = sorted(findings, key=lambda f: (f.start, -(f.end - f.start), f.type.value))
        kept: list[Finding] = []
        for f in ordered:
            if kept and f.start < kept[-1].end:
                continue
            kept.append(f)
        return kept


_ADAPTER: SemanticAdapter | None = None


def get_semantic_adapter(model_path: str | None = None) -> SemanticAdapter:
    """进程级单例（首次以给定模型路径创建，其后忽略路径参数）。"""
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = SemanticAdapter(model_path)
    return _ADAPTER
