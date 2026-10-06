"""流式转发中继（V1-04）：字节零改写透传 + **帧组装后**计量。

M0 教训（M0-实验报告 §2.2-1，壳层第一条纪律）：SSE 会把同一句拆进多个
``delta.content`` 帧，对原始字节流、单帧、甚至「逐帧取叶」做泄漏检测都会
**系统性假阴**——同一个占位符形状常被切进相邻两帧。泄漏/残留计量必须在
**通道级组装后的客户端可见文本** 上做：

1. SSE 组帧（行切分 + 空行组帧，与引擎 gateway/sse.py 同语义）→ 事件 JSON；
2. 逐事件抽取 ``choices[*].delta.content``（按到达顺序拼接 = 客户端所见正文）
   与 ``delta.tool_calls[*].function.arguments``（网关 hold-to-finish 后单帧
   发出 = 完整参数串）——两条**通道**分别组装；
3. 流收尾（EOF / ``[DONE]`` / 客户端断连）把组装文本一次性交给
   :class:`anongw_shell.leakmeter.LeakMeter`（内核 = 引擎
   ``tolerant_placeholder_hits``）。

数据面纪律：上游字节块原样 yield——不丢帧、不改序、不改字节（V1-04）。
非流式 JSON 响应走 :func:`meter_json_bytes`：整体缓冲（有界）→ 字符串叶
计量 → 原字节返回（叶即完整字符串，无跨帧问题）。
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterable
from typing import Any

from anongw_shell.leakmeter import LeakMeter

_DATA_PREFIX = "data:"
_DONE_PAYLOAD = "[DONE]"


def _iter_strings(obj: Any):
    """递归产出 JSON 结构中的字符串叶（非流式响应的可见文本全集口径）。"""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _iter_strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _iter_strings(value)


class SseTextTap:
    """SSE 字节流 → **通道级组装文本**累积器（计量面；不碰数据面）。

    组帧语义与引擎 :func:`gateway.sse.iter_sse_data_lines` 同源（按 ``\\n``
    切行、行尾 ``\\r`` 去除、空行组帧、多行 ``data:`` 拼接）——壳在引擎
    下游，看到的已是网关组好的帧，此处复刻同规则只为把**跨 TCP 块**的
    半行/半帧重新对齐（网络分块与 SSE 帧边界不对齐是常态）。

    抽取面（客户端可见文本的两条通道）：
    - ``content``：``choices[*].delta.content`` 字符串按事件到达顺序拼接；
    - ``tool_arguments``：``choices[*].delta.tool_calls[*].function.arguments``
      （网关 hold-to-finish 语义下每个参数串整帧到达）。
    protocol 字符串（role/model/finish_reason 等）**不进**计量面——混入会在
    占位符片段之间垫入噪声，重新制造跨帧假阴（M0 教训的隐蔽变体）。
    """

    def __init__(self) -> None:
        self._line_buf = b""            # 跨 chunk 半行缓冲
        self._data_lines: list[str] = []
        self._content_parts: list[str] = []
        self._tool_arg_parts: list[str] = []
        self._frames = 0                # 组装出的 data 事件数（V1-04 计数用）
        self._unparsed = 0              # 非 JSON 载荷事件数（协议串透传，不计量内容）

    def feed(self, data: bytes) -> None:
        self._line_buf += data
        while b"\n" in self._line_buf:
            raw, self._line_buf = self._line_buf.split(b"\n", 1)
            self._consume_line(raw)

    def _consume_line(self, raw: bytes) -> None:
        line = raw.rstrip(b"\r")
        if not line:
            # 空行 = 事件边界：组帧（多行 data 拼接）并取数
            if self._data_lines:
                self._take_event("\n".join(self._data_lines))
                self._data_lines = []
            return
        text = line.decode("utf-8", errors="replace")
        if text.startswith(_DATA_PREFIX):
            payload = text[len(_DATA_PREFIX):]
            if payload.startswith(" "):
                payload = payload[1:]
            self._data_lines.append(payload)

    def _take_event(self, payload: str) -> None:
        self._frames += 1
        if payload.strip() == _DONE_PAYLOAD:
            return  # 结束哨兵无内容
        try:
            obj = json.loads(payload)
        except ValueError:
            self._unparsed += 1  # 非 JSON 载荷原样透传（不吞不猜），计量面跳过
            return
        if not isinstance(obj, dict):
            return
        choices = obj.get("choices")
        if not isinstance(choices, list):
            return
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            if not isinstance(delta, dict):
                continue
            content = delta.get("content")
            if isinstance(content, str) and content:
                self._content_parts.append(content)
            tool_calls = delta.get("tool_calls")
            if isinstance(tool_calls, list):
                for call in tool_calls:
                    if not isinstance(call, dict):
                        continue
                    fn = call.get("function")
                    if isinstance(fn, dict):
                        args = fn.get("arguments")
                        if isinstance(args, str) and args:
                            self._tool_arg_parts.append(args)

    def feed_eof(self) -> None:
        """流结束：处理残留半行与未组帧的 data 行（引擎同语义：按一个事件产出）。"""
        if self._line_buf:
            self._consume_line(self._line_buf)
            self._line_buf = b""
        if self._data_lines:
            self._take_event("\n".join(self._data_lines))
            self._data_lines = []

    @property
    def frame_count(self) -> int:
        return self._frames

    def assembled_channels(self) -> list[str]:
        """通道级组装文本：[拼接正文（若有）] + 各工具参数串。

        每条通道内部已按到达顺序组装——这是**帧组装后**的口径（M0 教训
        的落地点）；计量只吃这里的输出，绝不逐帧/逐叶检测。
        """
        channels: list[str] = []
        content = "".join(self._content_parts)
        if content:
            channels.append(content)
        channels.extend(self._tool_arg_parts)
        return channels


async def relay_stream_with_meter(
    src: AsyncIterator[bytes], *, meter: LeakMeter, request_id: str
) -> AsyncIterator[bytes]:
    """数据面透传 + 计量面旁路：SSE 字节流原样 yield，流收尾按组装文本计量。

    计量在 ``finally`` 中执行——客户端中途断开也要计（泄漏不因断连而消失）。
    """
    tap = SseTextTap()
    metered = False

    def do_meter() -> None:
        nonlocal metered
        if not metered:
            metered = True
            # M0 教训落地点：计量对象 = 帧组装后的通道文本，不是原始分片
            meter.meter_texts(tap.assembled_channels(), request_id=request_id, source="stream")

    try:
        async for chunk in src:
            tap.feed(chunk)
            yield chunk
        tap.feed_eof()
    finally:
        do_meter()


def meter_json_bytes(body: bytes, *, meter: LeakMeter, request_id: str) -> list[str]:
    """非流式 JSON 响应计量：字符串叶全集过检测面；返回命中证据串。"""
    texts: list[str] = []
    try:
        obj = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        obj = None  # 非 JSON 体（错误页等）无可组装文本，按 0 命中如实计量
    if obj is not None:
        texts.extend(_iter_strings(obj))
    return meter.meter_texts(texts, request_id=request_id, source="nonstream")


def collect_json_strings(body: bytes) -> list[str]:  # pragma: no cover - 备用导出
    """（导出给 eval 复用）JSON 体 → 字符串叶全集。"""
    try:
        return list(_iter_strings(json.loads(body)))
    except (ValueError, UnicodeDecodeError):
        return []


def join_texts(texts: Iterable[str]) -> str:  # pragma: no cover - 备用导出
    return "".join(texts)
