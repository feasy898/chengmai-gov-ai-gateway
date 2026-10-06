"""NER 适配器（开发指令 §6 M2）：人名/住址等非结构化实体的模型识别入口。

P0 口径（铁律 D：MVP 识别只做规则层）：无模型时空输出，detect 调用规则层
实现的人名/住址识别器，返回 layer="ner" 的 Finding 列表。上层（gateway/filechannel）
零改动。
"""
from __future__ import annotations

from common.logs import get_logger
from recognizers.models import Finding

from .person import detect_person
from .address import detect_address

log = get_logger(__name__)


class NerAdapter:
    """NER 识别适配器（P0：规则层实现，预留 ONNX 模型路径）。"""

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path
        if model_path:
            log.debug("ner_adapter.model_path_ignored_p0", extra={"model_path": model_path})

    def detect(self, text: str, rule_taken: list[tuple[int, int]] | None = None) -> list[Finding]:
        """识别人名/住址等实体（P0：规则层实现，返回 layer="ner"）。"""
        taken = list(rule_taken) if rule_taken else []
        findings: list[Finding] = []
        findings.extend(detect_person(text, taken))
        findings.extend(detect_address(text, taken))
        return findings


_ADAPTER: NerAdapter | None = None


def get_ner_adapter(model_path: str | None = None) -> NerAdapter:
    """进程级单例（首次以给定模型路径创建，其后忽略路径参数）。"""
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = NerAdapter(model_path)
    return _ADAPTER
