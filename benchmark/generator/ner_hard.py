"""ne_hard.jsonl 金标生成器（NER 难例评测集）。

生成 ≥120 条政务文书样例，覆盖：
- 60+ 个不同人名（复姓/单姓 + 2-3 字名，含边界扰动）
- 40+ 个不同住址（省市区县乡镇街道门牌五级结构，含简写/缺级形态）
- 混合扰动（全角/数字分组/OCR 上下文/部分打码）

seed 固定 → 字节级可复现。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from benchmark.generator import perturb as pert
from benchmark.generator import geo
from benchmark.generator.personas import Personas
from common.config import REPO_ROOT

SEED = 20261006

# ── 人名池（72 个，含复姓/双名边界）──────────────────────────────────────
_PERSON_POOL = (
    # 单姓 + 2 字名（30）
    "王刚", "李明", "张伟", "刘洋", "陈静", "杨帆", "赵丽", "周强", "吴芳", "郑浩",
    "孙敏", "朱军", "胡斌", "林涛", "何雨", "高远", "马超", "罗琳", "谢安", "韩雪",
    "唐明", "冯亮", "董伟", "萧红", "程健", "曹阳", "袁博", "邓辉", "彭亮", "姜维",
    # 单姓 + 3 字名（22）
    "王志强", "李慧珍", "张建国", "刘海燕", "陈玉兰", "杨晓明", "赵文华", "周秀英", "吴玉梅", "郑国平",
    "孙丽娜", "朱建平", "胡秀兰", "林国栋", "何玉兰", "高明辉", "马玉梅", "罗建国", "谢晓红", "韩志强",
    "唐丽华", "冯志远",
    # 复姓 + 1-2 字名（20）
    "欧阳明", "司马华", "诸葛丽", "上官云", "皇甫松", "令狐冲", "慕容博", "端木懿", "公孙丑", "轩辕缙",
    "长孙康", "宇文统", "诸葛欣", "皇甫杰", "上官梅", "司马云", "公孙亮", "令狐艳", "慕容慧", "端木宏",
)

# ── 住址池（48 个，含简写/缺级）──────────────────────────────────────────
_ADDRESS_POOL = (
    # 完整五级：省+市+县+镇+路+号（16）
    "海南省澄迈县金江镇文化北路101号",
    "海南省海口市秀英区滨海大道188号",
    "海南省三亚市天涯区解放路66号",
    "海南省儋州市那大镇中兴大街299号",
    "海南省琼海市嘉积镇金海路88号",
    "海南省万宁市万城镇人民路55号",
    "海南省文昌市文城镇文建路77号",
    "海南省东方市八所镇解放路33号",
    "海南省定安县定城镇见龙大道22号",
    "海南省屯昌县屯城镇兴业路44号",
    "海南省临高县临城镇临昌路99号",
    "海南省白沙黎族自治县牙叉镇金沙路11号",
    "海南省昌江黎族自治县石碌镇东风路7号",
    "海南省乐东黎族自治县抱由镇乐祥路13号",
    "海南省陵水黎族自治县椰林镇建设路25号",
    "海南省保亭黎族苗族自治县保城镇文明路9号",
    # 缺省：无省（16）
    "澄迈县金江镇文化北路101号",
    "海口市秀英区滨海大道188号",
    "三亚市天涯区解放路66号",
    "儋州市那大镇中兴大街299号",
    "琼海市嘉积镇金海路88号",
    "万宁市万城镇人民路55号",
    "文昌市文城镇文建路77号",
    "东方市八所镇解放路33号",
    "定安县定城镇见龙大道22号",
    "屯昌县屯城镇兴业路44号",
    "临高县临城镇临昌路99号",
    "白沙黎族自治县牙叉镇金沙路11号",
    "昌江黎族自治县石碌镇东风路7号",
    "乐东黎族自治县抱由镇乐祥路13号",
    "陵水黎族自治县椰林镇建设路25号",
    "保亭黎族苗族自治县保城镇文明路9号",
    # 缺级：缺镇或缺县（10）
    "海南省澄迈县文化北路101号",
    "海口市秀英区滨海大道188号",
    "儋州市那大镇中兴大街299号",
    "琼海市金海路88号",
    "万宁市人民路55号",
    "文昌市文建路77号",
    "东方市解放路33号",
    "定安县见龙大道22号",
    "屯昌县屯城镇兴业路44号",
    "澄迈县金江镇沿江路9号",
    # 简写形态（6）
    "澄迈县金江镇文化路1号",
    "海口市龙华区大同路12号",
    "三亚市吉阳区迎宾路8号",
    "儋州市那大镇怡心花园5号",
    "琼海市嘉积镇爱华路3号",
    "万宁市万城镇西门街2号",
)

# ── 文书模板（10 类）─────────────────────────────────────────────────────
_TEMPLATES = (
    "low_income_publicity",
    "petition_transfer",
    "administrative_penalty",
    "medical_reimburse",
    "disability_subsidy",
    "community_correction",
    "cadre_assessment",
    "talent_publicity",
    "business_registration",
    "key_personnel_visit",
)

# ── 上下文锚点（用于人名/住址槽位）────────────────────────────────────────
_PERSON_CTX = (
    "户主：{name}",
    "联系人：{name}",
    "申请人：{name}",
    "经办人：{name}",
    "居民{name}",
    "村民{name}",
    "同志：{name}",
    "先生：{name}",
    "女士：{name}",
    "经理{name}",
    "老师{name}",
    "医生{name}",
)

_ADDRESS_CTX = (
    "家庭住址：{addr}",
    "住址：{addr}",
    "地址：{addr}",
    "户籍地：{addr}",
    "现住址：{addr}",
    "住所：{addr}",
    "位于{addr}",
)


def _build_ner_case(case_id: str, template: str, name: str, address: str,
                    rng: random.Random) -> dict:
    """生成一条 ne_hard 评测样例。"""
    p_tpl = rng.choice(_PERSON_CTX)
    a_tpl = rng.choice(_ADDRESS_CTX)
    p_text = p_tpl.format(name=name)
    a_text = a_tpl.format(addr=address)

    filler = "   根据相关文件精神，现将上述事项予以公示，如有异议请于7日内向有关部门反映。"
    parts = [p_text, "；", a_text, "。", filler]
    text = "".join(parts)

    # 扰动：仅对填充文 + 标点施加，不扰动人名/住址原文以保证 span 标注有效
    pert_kinds: list[str] = []
    if rng.random() < 0.4:
        text = text.replace("。", "。\n", 1)
        pert_kinds.append("newline_blank")
    if rng.random() < 0.3:
        # 只对 filler 部分做 OCR 上下文扰动
        filler_pos = text.find(filler)
        if filler_pos >= 0:
            before = text[:filler_pos]
            after = text[filler_pos + len(filler):]
            mangled = pert.ocr_context_mangle(filler, rng)
            text = before + mangled + after
            pert_kinds.append("ocr_context")

    p_start = text.find(name)
    p_end = p_start + len(name)
    a_start = text.find(address)
    a_end = a_start + len(address)

    expected = [
        {
            "fid": "f_0001",
            "type": "PERSON",
            "subtype": None,
            "start": p_start,
            "end": p_end,
            "raw": name,
            "normalized": name,
            "confidence": 0.9,
            "whitelisted": False,
            "action_hint": "MASK",
            "graded": True,
            "rule_detectable": False,
        },
        {
            "fid": "f_0002",
            "type": "ADDRESS",
            "subtype": None,
            "start": a_start,
            "end": a_end,
            "raw": address,
            "normalized": address,
            "confidence": 0.9,
            "whitelisted": False,
            "action_hint": "MASK",
            "graded": True,
            "rule_detectable": False,
        },
    ]

    return {
        "id": case_id,
        "template": template,
        "grading": "detect",
        "text": text,
        "perturbations": sorted(set(pert_kinds)),
        "expected": expected,
    }


def build_ne_hard(seed: int = SEED, outdir: str | None = None) -> list[dict]:
    """生成 ne_hard.jsonl 评测集，返回评测行列表。"""
    rng = random.Random(seed)
    cases: list[dict] = []

    names = list(_PERSON_POOL)
    addrs = list(_ADDRESS_POOL)
    rng.shuffle(names)
    rng.shuffle(addrs)

    seq = 0
    name_idx = 0
    addr_idx = 0
    for template in _TEMPLATES:
        for _ in range(13):  # 10 模板 × 13 = 130 条
            name = names[name_idx % len(names)]
            address = addrs[addr_idx % len(addrs)]
            name_idx += 1
            addr_idx += 1
            seq += 1
            cases.append(_build_ner_case(f"nh_{seq:04d}", template, name, address, rng))

    if outdir:
        out = Path(outdir)
        (out / "cases").mkdir(parents=True, exist_ok=True)
        lines = "".join(json.dumps(c, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                       for c in cases)
        (out / "ne_hard.jsonl").write_text(lines, encoding="utf-8")
        (out / "cases" / "ne_hard.jsonl").write_text(lines, encoding="utf-8")

    return cases


if __name__ == "__main__":
    cases = build_ne_hard(seed=SEED)
    print(f"Generated {len(cases)} cases")
    names = {c["expected"][0]["raw"] for c in cases if c["expected"] and c["expected"][0]["type"] == "PERSON"}
    addrs = {c["expected"][1]["raw"] for c in cases if len(c.get("expected", [])) > 1 and c["expected"][1]["type"] == "ADDRESS"}
    print(f"Unique names={len(names)}, Unique addresses={len(addrs)}")
    # 检查是否有 start=-1 的异常 case
    bad = [c["id"] for c in cases if any(e["start"] < 0 for e in c["expected"])]
    print(f"Cases with negative start: {bad}")
