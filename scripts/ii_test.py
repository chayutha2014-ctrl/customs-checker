#!/usr/bin/env python3
"""ทดสอบตัวอ่านใบแจ้งหนี้เบี้ยประกันภัยกับหน้าจริงใน _box_cache.json"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from customs_checker.tables import to_cells, group_rows                    # noqa: E402
from customs_checker.doctype import classify                               # noqa: E402
from customs_checker.insurance_invoice import analyze_insurance_invoice    # noqa: E402

BOX = ROOT / "docs_out" / "_box_cache.json"
TITLE_ZONE = 0.22


def page_text(rows):
    return "\n".join(r.text() for r in rows)


def title_text(rows):
    if not rows:
        return ""
    ys = [c.y0 for r in rows for c in r.cells] + [c.y1 for r in rows for c in r.cells]
    top, bottom = min(ys), max(ys)
    cut = top + (bottom - top) * TITLE_ZONE
    return "\n".join(r.text() for r in rows if r.cy <= cut)


def money(v):
    return "ไม่พบ" if v is None else format(v, ",.2f")


def main(prefix=""):
    cache = json.loads(BOX.read_text(encoding="utf-8"))
    n = ok = issue = fail = 0
    n_sum = n_pol = 0
    for k in sorted(cache):
        if not k.startswith(prefix):
            continue
        rows = group_rows(to_cells(cache[k]))
        if not rows:
            continue
        if classify(page_text(rows), title_text(rows)).code != "insurance_invoice":
            continue
        n += 1
        r = analyze_insurance_invoice(rows)
        print(f"\n{'=' * 78}\n{k}")
        print(f"  {r.status}")
        print(f"    ทุนประกัน {money(r.sum_insured)} · เลขที่กรมธรรม์ "
              f"{r.policy_no or 'ไม่พบ'} · วันที่ {', '.join(r.dates) or 'ไม่พบ'}")
        if r.wht is not None:
            print(f"    หัก ณ ที่จ่าย {money(r.wht)} เหลือจ่าย {money(r.net_payable)}")
        for x in r.notes:
            print(f"    หมายเหตุ {x}")
        for i in r.issues:
            print(f"    ⚠ {i}")
        n_sum += r.sum_insured is not None
        n_pol += r.policy_no is not None
        if r.total is not None and not r.issues:
            ok += 1
        elif r.issues:
            issue += 1
        else:
            fail += 1
    print(f"\n{'=' * 78}")
    print(f"ใบแจ้งหนี้เบี้ยประกัน {n} ใบ | เลขคณิตลงตัว {ok} "
          f"| พบข้อขัดแย้ง {issue} | อ่านไม่ได้ {fail}")
    print(f"ทุนประกันอ่านได้ {n_sum}/{n} · เลขที่กรมธรรม์ {n_pol}/{n}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "")
