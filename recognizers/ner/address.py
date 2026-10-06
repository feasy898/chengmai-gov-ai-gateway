"""住址识别（NER 层）。

策略：
1. 上下文前缀：仅在「家庭住址|住址|地址|户籍地|现住址|住所|位于」等锚点后匹配。
2. 结构化文法：省 + (市)? + 区/县 + (镇/街道)? + (路/街/巷)? + 号，支持多级缺省。
3. 行政区划词典：基于 benchmark.generator.geo 中的海南省区划 + 自补全国主要省份。
4. 与 taken span 协作，避免与规则层或其他 NER 实体重叠。
"""
from __future__ import annotations

import re

from common.logs import get_logger
from recognizers.models import Finding

log = get_logger(__name__)

# ── 行政区划词典 ────────────────────────────────────────────────────────
_PROVINCES = (
    "北京市", "天津市", "上海市", "重庆市",
    "河北省", "山西省", "辽宁省", "吉林省", "黑龙江省",
    "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省", "广东省", "海南省",
    "四川省", "贵州省", "云南省", "陕西省", "甘肃省", "青海省", "台湾省",
    "内蒙古自治区", "广西壮族自治区", "西藏自治区", "宁夏回族自治区", "新疆维吾尔自治区",
    "香港特别行政区", "澳门特别行政区",
)

_HAINAN_COUNTIES = (
    "秀英区", "龙华区", "琼山区", "美兰区",
    "海棠区", "吉阳区", "天涯区", "崖州区",
    "三沙市", "儋州市",
    "五指山市", "琼海市", "文昌市",
    "万宁市", "东方市",
    "定安县", "屯昌县", "澄迈县", "临高县",
    "白沙黎族自治县", "昌江黎族自治县", "乐东黎族自治县",
    "陵水黎族自治县", "保亭黎族苗族自治县", "琼中黎族苗族自治县",
)

# 通用乡镇/街道后缀
_TOWN_SUFFIXES = ("镇", "乡", "街道", "街", "道")

# 路名/街名/巷名后缀
_ROAD_SUFFIXES = ("路", "街", "巷", "道", "大街", "大道")

# ── 地址文法正则（分三级置信度）──────────────────────────────────────────
# 核心文法：行政区划单元 + (路街)? + 门牌号，中间层级可缺。

_PROV = "|".join(_PROVINCES)
_CITY = r"(?:[\u4e00-\u9fff]+?(?:市|区))?"
_COUNTY = "|".join(_HAINAN_COUNTIES)
_TOWN = r"(?:[\u4e00-\u9fff]+?(?:镇|乡|街道|街|道))?"
_ROAD = r"(?:[\u4e00-\u9fff]+?(?:路|街|巷|道|大街|大道))?"
_NO = r"\d+号"

_ADDR_FULL = re.compile(
    rf"(?:{_PROV})"
    rf"{_CITY}"
    rf"(?:{_COUNTY})"
    rf"{_TOWN}"
    rf"{_ROAD}"
    rf"(?:{_NO})"
)

# 缺省：无省，以市/县/区开头
_ADDR_NO_PROV = re.compile(
    r"(?:[\u4e00-\u9fff]+?(?:市|区|县))"
    r"(?:[\u4e00-\u9fff]+?(?:镇|乡|街道|街|道))?"
    r"(?:[\u4e00-\u9fff]+?(?:路|街|巷|道|大街|大道))?"
    r"\d+号"
)

# 缺级：仅 镇/街道 + 路 + 号（minimal）
_ADDR_MINIMAL = re.compile(
    r"[\u4e00-\u9fff]+?(?:镇|乡|街道|街|道)"
    r"(?:[\u4e00-\u9fff]+?(?:路|街|巷|道|大街|大道))?"
    r"\d+号"
)

# ── 上下文前缀 ──────────────────────────────────────────────────────────
_CONTEXT_PREFIX = (
    "家庭住址", "住址", "地址", "户籍地", "现住址", "住所", "位于",
)
_CONTEXT_RE = re.compile(
    r"(?P<ctx>" + "|".join(_CONTEXT_PREFIX) + r")[:：]?\s*(?P<addr>.+?)(?=[。；\n]|$)"
)

# ── 负面模式（机构名等）─────────────────────────────────────────────────
_INSTITUTION_SUFFIXES = (
    "办事处", "服务中心", "指挥部", "办公室", "工作站", "居委会", "村委会",
)


def _is_institution(text: str, start: int, end: int) -> bool:
    """检查地址候选是否实际是机构名。"""
    suffix = text[end:end + 6]
    return any(suffix.startswith(s) for s in _INSTITUTION_SUFFIXES)


def _match_addr(text: str, start_hint: int = 0) -> tuple[int, int] | None:
    """在文本中尝试匹配地址文法，返回 (start, end) 或 None。"""
    # 优先完整文法
    m = _ADDR_FULL.search(text, start_hint)
    if m:
        s, e = m.start(), m.end()
        if not _is_institution(text, s, e):
            return s, e
    # 缺省
    m = _ADDR_NO_PROV.search(text, start_hint)
    if m:
        s, e = m.start(), m.end()
        if not _is_institution(text, s, e):
            return s, e
    # 缺级
    m = _ADDR_MINIMAL.search(text, start_hint)
    if m:
        s, e = m.start(), m.end()
        if not _is_institution(text, s, e):
            return s, e
    return None


def detect_address(text: str, taken: list[tuple[int, int]]) -> list[Finding]:
    """识别住址，返回 Finding 列表（layer="ner"）。"""
    findings: list[Finding] = []
    if not text:
        return findings

    # 1) 上下文前缀 + 文法验证
    for m in _CONTEXT_RE.finditer(text):
        candidate = m.group("addr")
        candidate = candidate.rstrip("。；，,、 ")
        addr_start = m.start("addr")
        span = _match_addr(candidate, 0)
        if span is None:
            continue
        rel_s, rel_e = span
        start = addr_start + rel_s
        end = addr_start + rel_e
        if _overlaps(start, end, taken):
            continue
        raw = text[start:end]
        taken.append((start, end))
        # 缺级/缺省地址置信度略低
        confidence = 0.8
        if not any(text[start:start + 2] == p[:2] for p in _PROVINCES):
            confidence = 0.7
        findings.append(Finding(
            fid="", type="ADDRESS", layer="ner", start=start, end=end,
            raw=raw, normalized=raw, confidence=confidence,
            whitelisted=False, action_hint="MASK",
        ))

    # 2) 全文扫描（仅在上下文未覆盖区域尝试，降低误报）
    search_from = 0
    while True:
        span = _match_addr(text, search_from)
        if span is None:
            break
        s, e = span
        if _overlaps(s, e, taken):
            search_from = e
            continue
        if s > 0 and text[s - 1] in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
            search_from = e
            continue
        raw = text[s:e]
        taken.append((s, e))
        confidence = 0.6
        findings.append(Finding(
            fid="", type="ADDRESS", layer="ner", start=s, end=e,
            raw=raw, normalized=raw, confidence=confidence,
            whitelisted=False, action_hint="MASK",
        ))
        search_from = e

    return findings


def _overlaps(start: int, end: int, taken: list[tuple[int, int]]) -> bool:
    return any(start < t_end and t_start < end for t_start, t_end in taken)
