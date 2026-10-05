"""输出侧复检钩子（开发指令 §6 M5）：``moderate(response)`` 接口预留，P0 always-safe。

- **P0（铁律 D）**：:class:`NullModerator` 恒 ``safe``——无审核模型时降级为
  "未发现风险"，主链路零影响、零阻塞；
- **P1（采样执行）**：接语义审核模型 response 侧——后端实现
<<<<<<< 8340533e2268ad9f14f101eb696538bea1e8d9ab
  :class:`OutputModerationBackend` 协议（``moderate(text, *, redact=None) ->
  ModerationVerdict``，词汇与语义审核适配器一致：``safe | flagged`` +
  categories），注入 :class:`outguard.service.OutguardService`；``flagged`` →
  网关按 content_blocked 拦截本次响应（reasons code=``OUTPUT_MODERATION``）。
  模型路径配置只写 ``config.app.moderation_model``（公开仓库卫生，模型名不进
  源码）。

脱敏承接（审查加固，与输入侧 judge 脱敏同口径）：输出复检对象是**还原后**
文本（含原值）；后端若会把文本发往外部端点（如 ``SEMANTIC_JUDGE_BASE_URL``），
必须先经 ``redact`` 参数把 PII/密级表面形式换为占位符——原文不在脱敏/BLOCK
判定前出网（输入侧参照 :meth:`recognizers.semantic.adapter.SemanticAdapter.
_redact_for_judge`）。``redact`` 为可选关键字参数（缺省 ``None`` = 原样复检），
调用方经 :meth:`outguard.service.OutguardService.moderate` 传入。
=======
  :class:`OutputModerationBackend` 协议（``moderate(text) -> ModerationVerdict``，
  词汇与语义审核适配器一致：``safe | flagged`` + categories），注入
  :class:`outguard.service.OutguardService`；``flagged`` → 网关按 content_blocked
  拦截本次响应（reasons code=``OUTPUT_MODERATION``）。模型路径配置只写
  ``config.app.moderation_model``（公开仓库卫生，模型名不进源码）。
>>>>>>> 47048f64cf6ee1fff8757a2565bf59d4c0003972

接线现状（M5 范围）：非流式路径在**还原后**对首 choice 正文执行复检
（gateway/pipeline.py）；流式路径为 P1 采样执行预留（流收尾取还原前占位符版
正文，复检动作与执行率由 D4 任务接线，接口不再变更）。
"""
from __future__ import annotations

<<<<<<< 8340533e2268ad9f14f101eb696538bea1e8d9ab
from collections.abc import Callable
=======
>>>>>>> 47048f64cf6ee1fff8757a2565bf59d4c0003972
from typing import Any, Protocol, runtime_checkable

from outguard.models import ModerationVerdict

<<<<<<< 8340533e2268ad9f14f101eb696538bea1e8d9ab
#: 可选脱敏承接函数形状：还原后文本 → 占位符版本（单参、纯函数）
RedactFn = Callable[[str], str]


@runtime_checkable
class OutputModerationBackend(Protocol):
    """输出复检后端协议：``moderate(text, *, redact=None)``（P1 实现此形状）。

    ``redact``：可选脱敏承接（见模块 docstring）——后端向外部端点发送文本前
    必须经它换占位符；不做外发的本地后端可声明并忽略之。
    """

    def moderate(self, text: str, *, redact: RedactFn | None = None) -> ModerationVerdict:
=======

@runtime_checkable
class OutputModerationBackend(Protocol):
    """输出复检后端协议：``moderate(text) -> ModerationVerdict``（P1 实现此形状）。"""

    def moderate(self, text: str) -> ModerationVerdict:
>>>>>>> 47048f64cf6ee1fff8757a2565bf59d4c0003972
        """对（还原后的）响应文本做风险复检；实现必须无副作用、可采样调用。"""
        ...


class NullModerator:
<<<<<<< 8340533e2268ad9f14f101eb696538bea1e8d9ab
    """P0 空审核后端：恒 ``safe``（接口占位；语义审核模型后端就位后整体替换）。

    ``redact`` 仅声明协议承接、从不调用——P0 行为零变化（无外发面，无需脱敏）。
    """

    def moderate(self, text: str, *, redact: RedactFn | None = None) -> ModerationVerdict:
=======
    """P0 空审核后端：恒 ``safe``（接口占位；语义审核模型后端就位后整体替换）。"""

    def moderate(self, text: str) -> ModerationVerdict:
>>>>>>> 47048f64cf6ee1fff8757a2565bf59d4c0003972
        return ModerationVerdict(verdict="safe")


def verdict_of(result: ModerationVerdict | dict[str, Any]) -> ModerationVerdict:
    """判定归一化：后端可返回模型或 ``{verdict, categories}`` dict（适配器口径）。

    - 未识的 verdict 值一律归 ``safe``（复检器故障不得误拦正常回答——宁可放行）；
    - ``categories``/``detail`` 如实透传（面向审计 flags 与 reasons detail）。
    """
    if isinstance(result, ModerationVerdict):
        return result
    raw = result.get("verdict", "safe")
    verdict = "flagged" if raw == "flagged" else "safe"
    categories = result.get("categories") or []
    if not isinstance(categories, list):
        categories = []
    return ModerationVerdict(
        verdict=verdict,
        categories=[str(c) for c in categories],
        detail=str(result.get("detail", "") or ""),
    )
