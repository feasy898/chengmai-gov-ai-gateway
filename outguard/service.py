"""输出侧服务门面（M5）：AI 标识 + 拦截文案 + 复检钩子的单一持有者。

gateway 只依赖本类（构造一次、随 :class:`gateway.pipeline.GatewayService` 生命周期）：
- ``ai_label``：来自 config/app.yaml ``ai_label``（空/空白 → 不注入标识）；
- ``texts``：config/outguard_texts.yaml（缺失回落内置默认，见 outguard/fallback）；
- ``moderator``：输出复检后端（P0 :class:`outguard.moderation.NullModerator`，
  P1 注入语义审核模型后端，形状见 outguard/moderation 协议）。
"""
from __future__ import annotations

<<<<<<< 8340533e2268ad9f14f101eb696538bea1e8d9ab
import inspect
=======
>>>>>>> 47048f64cf6ee1fff8757a2565bf59d4c0003972
from pathlib import Path

from common.config import REPO_ROOT, AppConfig
from outguard.fallback import DEFAULT_TEXTS_PATH, block_message, load_texts
from outguard.models import ModerationVerdict, OutguardTexts
<<<<<<< 8340533e2268ad9f14f101eb696538bea1e8d9ab
from outguard.moderation import NullModerator, OutputModerationBackend, RedactFn, verdict_of
=======
from outguard.moderation import NullModerator, OutputModerationBackend, verdict_of
>>>>>>> 47048f64cf6ee1fff8757a2565bf59d4c0003972
from routing.models import RouteDecision


class OutguardService:
    """输出侧防护服务（标识文案 / 代答拒答 / 复检钩子的组合门面）。"""

    def __init__(
        self,
        texts: OutguardTexts,
        *,
        ai_label: str = "",
        moderator: OutputModerationBackend | None = None,
    ) -> None:
        self.texts = texts
        self.ai_label = (ai_label or "").strip()
        self.moderator: OutputModerationBackend = moderator if moderator is not None else NullModerator()
<<<<<<< 8340533e2268ad9f14f101eb696538bea1e8d9ab
        # 后端是否声明 redact 形参（构造期定死；审查加固脱敏承接的兼容判定——
        # 旧式两参后端未声明时不传该关键字参数，行为与此前完全一致）
        self._backend_takes_redact = "redact" in inspect.signature(
            self.moderator.moderate).parameters
=======
>>>>>>> 47048f64cf6ee1fff8757a2565bf59d4c0003972

    @classmethod
    def from_config(
        cls, cfg: AppConfig, *, moderator: OutputModerationBackend | None = None,
    ) -> "OutguardService":
        """按 AppConfig 构造：文案库路径（相对路径按仓库根解析）+ AI 标识文案。"""
        path = Path(getattr(cfg, "outguard_texts", DEFAULT_TEXTS_PATH) or DEFAULT_TEXTS_PATH)
        if not path.is_absolute():
            path = REPO_ROOT / path
        return cls(load_texts(path), ai_label=cfg.ai_label, moderator=moderator)

    # ── 拦截代答/拒答 ─────────────────────────────────────────────
    def block_reply(self, decision: RouteDecision, prompt_masked: str = "") -> str:
        """BLOCK 403 的 message：决定性 reason 模板（+ 关键词代答拼尾）。

        ``prompt_masked`` 传**脱敏后**的最后一.user 消息文本（占位符版本）——
        仅用于代答关键词匹配，不回显、不入库。
        """
        return block_message(self.texts, decision, prompt_masked)

    # ── 输出侧复检钩子（§6 M5：moderate(response) 接口）───────────
<<<<<<< 8340533e2268ad9f14f101eb696538bea1e8d9ab
    def moderate(self, text: str, *, redact: RedactFn | None = None) -> ModerationVerdict:
        """复检（还原后的）响应文本；判定经 :func:`verdict_of` 归一化。

        ``redact``：可选脱敏承接（审查加固）：调用方传入的 ``str -> str``
        纯函数（网关侧为「PII/密级表面形式 → 会话占位符/拦截占位」，与输入侧
        judge 脱敏同口径）——后端若把文本发往外部端点，必须先经它换占位符，
        原文不在复检判定前出网。后端未声明 ``redact`` 形参（旧式实现）时不传，
        行为与此前完全一致；P0 :class:`NullModerator` 声明并忽略之，恒 safe
        零变化。
        """
        if redact is not None and self._backend_takes_redact:
            return verdict_of(self.moderator.moderate(text, redact=redact))
=======
    def moderate(self, text: str) -> ModerationVerdict:
        """复检（还原后的）响应文本；判定经 :func:`verdict_of` 归一化。"""
>>>>>>> 47048f64cf6ee1fff8757a2565bf59d4c0003972
        return verdict_of(self.moderator.moderate(text))
