"""M2 NER 难例验收（新增）：词表外人名 + 住址识别精度与误报率。

运行::

    cd REPO_ROOT && PYTHONUTF8=1 /tmp/gov-venv/bin/python -m evals.m2_ner_hard

exit 0 = 通过。金标文件 ``data/cases/ne_hard.jsonl`` 由 benchmark.generator.ner_hard 生成，
seed 固定可复现。

通过线：
1. 人名 F1 ≥ 0.85
2. 住址 F1 ≥ 0.85
3. 误报率（FPR）≤ 0.05（仅统计 NER 层预测，避免规则层既有误报干扰）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from recognizers.pipeline import detect_full  # noqa: E402

CASES_PATH = REPO_ROOT / "data" / "cases" / "ne_hard.jsonl"
RESULTS: list[tuple[bool, str]] = []


def _record(name: str, fn):
    try:
        detail = fn()
        RESULTS.append((True, f"PASS  {name}" + (f" — {detail}" if detail else "")))
    except Exception as exc:
        RESULTS.append((False, f"FAIL  {name} — {type(exc).__name__}: {exc}"))


def _load_cases() -> list[dict]:
    assert CASES_PATH.exists(), f"missing: {CASES_PATH.relative_to(REPO_ROOT)}"
    cases = [json.loads(line) for line in
             CASES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(cases) >= 120, f"cases {len(cases)} < 120"
    return cases


def _span_overlap(p_start: int, p_end: int, e_start: int, e_end: int) -> bool:
    return p_start < e_end and e_start < p_end


def _eval_metrics(cases: list[dict]) -> tuple[float, float, float]:
    """分别计算 PERSON 和 ADDRESS 的 F1，以及全局 FPR（仅 NER 层）。

    返回 (person_f1, address_f1, fpr)。
    """
    tp_p = fp_p = fn_p = 0
    tp_a = fp_a = fn_a = 0
    total_pred = 0
    total_fp = 0

    for case in cases:
        text = case["text"]
        dets = detect_full(text)
        exps = case.get("expected", [])

        exp_by_type: dict[str, list[dict]] = {"PERSON": [], "ADDRESS": []}
        pred_by_type: dict[str, list] = {"PERSON": [], "ADDRESS": []}

        for e in exps:
            if e.get("type") in exp_by_type:
                exp_by_type[e["type"]].append(e)
        for d in dets:
            if d.type.value in pred_by_type:
                pred_by_type[d.type.value].append(d)

        for etype in ("PERSON", "ADDRESS"):
            exp_list = exp_by_type[etype]
            pred_list = pred_by_type[etype]
            matched_exp = [False] * len(exp_list)
            matched_pred = [False] * len(pred_list)

            for pi, pred in enumerate(pred_list):
                best_ei = -1
                best_overlap = 0
                for ei, exp in enumerate(exp_list):
                    if matched_exp[ei]:
                        continue
                    if _span_overlap(pred.start, pred.end, exp["start"], exp["end"]):
                        overlap_len = min(pred.end, exp["end"]) - max(pred.start, exp["start"])
                        if overlap_len > best_overlap:
                            best_overlap = overlap_len
                            best_ei = ei
                if best_ei >= 0:
                    matched_pred[pi] = True
                    matched_exp[best_ei] = True

            tp = sum(matched_pred)
            fp = len(matched_pred) - tp
            fn = len(exp_list) - sum(matched_exp)

            if etype == "PERSON":
                tp_p += tp
                fp_p += fp
                fn_p += fn
            else:
                tp_a += tp
                fp_a += fp
                fn_a += fn

        # FPR 仅统计 NER 层预测，避免规则层既有误报干扰
        for d in dets:
            if d.layer != "ner" or d.type.value not in ("PERSON", "ADDRESS"):
                continue
            total_pred += 1
            hit = any(
                _span_overlap(d.start, d.end, e["start"], e["end"])
                for e in exps if e.get("type") == d.type.value
            )
            if not hit:
                total_fp += 1

    def _f1(tp, fp, fn):
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        return (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

    p_f1 = _f1(tp_p, fp_p, fn_p)
    a_f1 = _f1(tp_a, fp_a, fn_a)
    fpr = total_fp / total_pred if total_pred > 0 else 0.0
    return p_f1, a_f1, fpr


def check_f1() -> str:
    cases = _load_cases()
    p_f1, a_f1, fpr = _eval_metrics(cases)
    assert p_f1 >= 0.85, f"PERSON F1 {p_f1:.4f} < 0.85"
    assert a_f1 >= 0.85, f"ADDRESS F1 {a_f1:.4f} < 0.85"
    return f"PERSON F1={p_f1:.4f}; ADDRESS F1={a_f1:.4f}"


def check_fpr() -> str:
    cases = _load_cases()
    p_f1, a_f1, fpr = _eval_metrics(cases)
    assert fpr <= 0.05, f"FPR {fpr:.4f} > 0.05"
    return f"FPR={fpr:.4f}"


def main() -> int:
    _record("ner_f1(人名/住址 F1≥0.85)", check_f1)
    _record("ner_fpr(误报率≤0.05)", check_fpr)

    for _, line in RESULTS:
        print(line)
    passed = sum(1 for ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"M2 NER HARD: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
