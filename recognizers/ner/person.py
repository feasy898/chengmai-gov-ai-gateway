"""词表外人名识别（NER 层）。

策略：
1. 上下文锚定：在「户主|联系人|申请人|经办人|居民|村民|同志|先生|女士|经理|老师|医生」等
   前缀/后缀后，直接匹配姓名形状（高置信度 0.9）。
2. 职务后缀消歧：若匹配到的人名末尾字与已知职务（局长/科长/主任/书记/经理/老师/医生/院长/校长/村长/镇长）
   构成词汇，则视为职务称谓而非人名，降低置信度或跳过。
3. 独立姓名形状：姓氏表（单姓 + 复姓）+ 名字长度/用字特征，左/右边界守卫。
"""
from __future__ import annotations

import re

from common.logs import get_logger
from recognizers.models import Finding

log = get_logger(__name__)

# ── 姓氏表 ─────────────────────────────────────────────────────────────
_SINGLE_SURNAMES = (
    "王李张刘陈杨黄赵吴周徐孙马朱胡郭何林罗高郑梁谢宋唐许韩冯邓曹彭曾肖田董潘"
    "袁蔡蒋余于杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦"
    "邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤"
)
_COMPOUND_SURNAMES = (
    "欧阳", "司马", "诸葛", "上官", "皇甫", "令狐", "慕容", "端木",
    "公孙", "轩辕", "长孙", "宇文",
)

# 按长度降序排列，避免部分匹配（如「欧阳」在前）
_SURNAME_ALTERNATIVES = "|".join(
    f"(?:{s})" for s in sorted(_COMPOUND_SURNAMES + tuple(_SINGLE_SURNAMES), key=len, reverse=True)
)

# ── 姓名形状 ────────────────────────────────────────────────────────────
# 复姓 2 字 + 名 1-2 字；单姓 1 字 + 名 1-2 字；总长 3-4 字。
_PERSON_RE = re.compile(
    rf"(?<![\u4e00-\u9fff])"          # 左边界非汉字
    rf"({_SURNAME_ALTERNATIVES})"     # 姓
    rf"([\u4e00-\u9fff]{{1,2}})"      # 名
    rf"(?![\u4e00-\u9fff])"           # 右边界非汉字
)

# ── 上下文锚点 ──────────────────────────────────────────────────────────
_CONTEXT_PREFIX = (
    "户主", "联系人", "申请人", "经办人", "居民", "村民", "同志", "先生", "女士",
    "经理", "老师", "医生", "局长", "科长", "主任", "书记", "院长", "校长", "村长", "镇长",
)
_CONTEXT_RE = re.compile(
    r"(?P<ctx>" + "|".join(_CONTEXT_PREFIX) + r")[:：]?\s*(?P<name>[\u4e00-\u9fff]{2,4})"
)

# ── 职务后缀消歧 ────────────────────────────────────────────────────────
_TITLE_SUFFIXES = (
    "局长", "副局长", "科长", "副科长", "主任", "副主任", "股长", "办事员", "科员",
    "站长", "所长", "院长", "校长", "院长助理", "经理", "老师", "医生", "先生", "女士",
    "书记", "镇长", "村长", "主席",
)
_TITLE_SUFFIX_RE = re.compile(
    r"^(" + "|".join(_TITLE_SUFFIXES) + r")$"
)

# ── 停用词 ─────────────────────────────────────────────────────────────
_STOPWORDS = frozenset({
    "周一", "周二", "周三", "周四", "周五", "周六", "周日", "周年", "周报",
    "马上", "马路", "于是", "由于", "属于", "关于", "对于", "在于", "等于",
    "终于", "介于", "任何", "曾经", "方面", "范围", "范畴", "程度", "杜绝",
    "严格", "金融", "金额", "余额", "其余", "石头", "石油", "白天", "白色",
    "王国", "夏天", "谢谢", "许可", "肖像", "董事", "付款", "高端", "林业",
    "万一", "陆地", "向上", "向下", "时效", "现金", "合同", "合作",
    # 公文字段词（2026-10-06 m10_e2e db_file_scan 暴露：上下文锚定曾把
    # 「居民电话登记表」的「电话登记」当 PERSON，通用词进 seen_values 后
    # 全库扫描必中——姓氏门+本表双保险）
    "电话", "登记", "名单", "公示", "信息", "材料", "证明", "申请", "审核",
    "意见", "情况", "说明", "编号", "号码", "记录", "工作", "时间", "地点",
    "单位", "身份", "证件", "家庭", "成员", "关系", "人口", "户数", "地址",
    "地区", "区域", "辖区", "社区", "小组", "以下", "如下", "尚未", "已经",
    "派出所", "指挥部", "办公室", "工作站", "服务站", "居委会",
})


def _is_title_suffix(word: str) -> bool:
    """检查 word 是否完全匹配某个职务后缀。"""
    return bool(_TITLE_SUFFIX_RE.match(word))


def detect_person(text: str, taken: list[tuple[int, int]]) -> list[Finding]:
    """识别词表外人名，返回 Finding 列表（layer="ner"）。"""
    findings: list[Finding] = []
    if not text:
        return findings

    # 1) 上下文锚定（高置信度 0.9，姓氏门：首字须为姓氏表姓/复姓前缀——
    #    「居民电话登记表」类字段词曾借此路径混入）
    _surname_chars = set("".join(_SINGLE_SURNAMES)) | {cs[0] for cs in _COMPOUND_SURNAMES}
    for m in _CONTEXT_RE.finditer(text):
        name = m.group("name")
        if name in _STOPWORDS:
            continue
        if name[0] not in _surname_chars:
            continue
        start = m.start("name")
        end = start + len(name)
        if _overlaps(start, end, taken):
            continue
        # 职务后缀消歧：若名字本身是完整职务词，跳过
        if _is_title_suffix(name):
            continue
        taken.append((start, end))
        findings.append(Finding(
            fid="", type="PERSON", layer="ner", start=start, end=end,
            raw=name, normalized=name, confidence=0.9,
            whitelisted=False, action_hint="MASK",
        ))

    # 2) 独立姓名形状（中置信度 0.7）
    for m in _PERSON_RE.finditer(text):
        name = m.group(0)
        if name in _STOPWORDS:
            continue
        start = m.start()
        end = m.end()
        if _overlaps(start, end, taken):
            continue
        # 若姓名后紧跟职务后缀，降为 0.5 或跳过
        suffix = text[end:end + 4]
        if any(text[end:].startswith(t) for t in _TITLE_SUFFIXES):
            # 姓名末尾字恰是职务首字 → 跳过（如「王局」长、「李主」任）
            if any(name.endswith(t[0]) and text[end:end + len(t)] == t for t in _TITLE_SUFFIXES):
                continue
        taken.append((start, end))
        findings.append(Finding(
            fid="", type="PERSON", layer="ner", start=start, end=end,
            raw=name, normalized=name, confidence=0.7,
            whitelisted=False, action_hint="MASK",
        ))

    return findings


def _overlaps(start: int, end: int, taken: list[tuple[int, int]]) -> bool:
    return any(start < t_end and t_start < end for t_start, t_end in taken)
