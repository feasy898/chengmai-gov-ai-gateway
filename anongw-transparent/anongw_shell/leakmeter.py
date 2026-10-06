"""运行时泄漏计数器（规划 §四M1；三 g「把 tolerant_placeholder_hits 接成运行时策略」）。

一号运行时指标（规划 §三g）：检测「形状可辨但（还原后仍）占位符残留」→
计数 + 留痕 + 可查（/anongw/stats），不做自动补救（F8 推荐暂不，M2 拿到
失败分布后再议）。

**内核复用纪律**：形状检测只调引擎 :func:`masking.mapper.tolerant_placeholder_hits`
（含 M0 步骤 1 的裸 digest 第二检测面），不造平行实现——仪器与引擎 eval
（T0）同一把尺，泄漏数字才可对账。

口径（测试计划 T0/V0-04 两级断言）：
- 命中一律是**形状级证据**（证据串=占位符形状键，含 ~noncanon 标记；
  不含原值）——进披露计数；
- 计量对象是**帧组装后的客户端可见文本**（M0-实验报告 §2.2-1 教训：
  对 SSE 原始分片做检测会系统性假阴）。
"""
from __future__ import annotations

import threading
from collections import deque
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

# 内核复用（规划 §四M1：调 tolerant_placeholder_hits，若已有则复用不造平行实现）
from masking.mapper import tolerant_placeholder_hits

#: 事件环形缓冲容量（本地可见性用；证据串无原值，容量防失控）
EVENT_CAPACITY = 200


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class LeakMeter:
    """进程内泄漏计数器（线程安全；壳全响应面共用一个实例）。

    ``meter_text`` 幂等于「检测→计数→留痕」三步；证据串是占位符形状键
    （``〔标签·hex〕`` 及 ``~noncanon`` 变体），不含任何原值——计数器自身
    不构成新渗漏面（测试计划 V3-05 元断言）。
    """

    def __init__(self, *, event_capacity: int = EVENT_CAPACITY) -> None:
        self._lock = threading.Lock()
        self._requests_metered = 0
        self._responses_with_hits = 0
        self._total_hits = 0
        self._events: deque[dict[str, Any]] = deque(maxlen=max(1, event_capacity))

    def meter_text(self, text: str, *, request_id: str, source: str) -> list[str]:
        """对一段**组装后**文本计量；返回命中证据串列表（空 = 无残留）。

        ``source``：计量面来源（``nonstream`` | ``stream``），进事件留痕。
        """
        hits = tolerant_placeholder_hits(text) if text else []
        with self._lock:
            self._requests_metered += 1
            if hits:
                self._responses_with_hits += 1
                self._total_hits += len(hits)
                self._events.append({
                    "ts": _utc_now_iso(),
                    "request_id": request_id,
                    "source": source,
                    "hits": list(hits),
                })
        return hits

    def meter_texts(self, texts: Iterable[str], *, request_id: str, source: str) -> list[str]:
        """多条**已组装**通道文本合并计量（一次请求 = 一次计数，不去重跨通道证据）。

        契约（M0 教训）：``texts`` 的每个元素必须是帧组装后的完整通道
        （如流式的拼接正文、整段工具参数串）——逐帧/逐叶传入会在占位符
        跨帧切分处系统性假阴（见 relay.SseTextTap 的组装职责）。
        """
        all_hits: list[str] = []
        for text in texts:
            if text:
                all_hits.extend(tolerant_placeholder_hits(text))
        with self._lock:
            self._requests_metered += 1
            if all_hits:
                self._responses_with_hits += 1
                self._total_hits += len(all_hits)
                self._events.append({
                    "ts": _utc_now_iso(),
                    "request_id": request_id,
                    "source": source,
                    "hits": all_hits,
                })
        return all_hits

    def snapshot(self) -> dict[str, Any]:
        """计数快照（/anongw/stats 出口；对账口径：面板数 = 计数器数）。"""
        with self._lock:
            return {
                "requests_metered": self._requests_metered,
                "responses_with_hits": self._responses_with_hits,
                "total_hits": self._total_hits,
                "recent_events": list(self._events),
            }

    def reset(self) -> dict[str, int]:
        """清零（测试/换场景用）；返回清零前计数（对账留痕）。"""
        with self._lock:
            before = {
                "requests_metered": self._requests_metered,
                "responses_with_hits": self._responses_with_hits,
                "total_hits": self._total_hits,
            }
            self._requests_metered = 0
            self._responses_with_hits = 0
            self._total_hits = 0
            self._events.clear()
            return before
