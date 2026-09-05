#!/usr/bin/env python3
"""ทดสอบตัวอ่านใบแจ้งหนี้ค่าระวางกับหน้าจริงใน _box_cache.json

ใช้:  python scripts/fi_test.py            ทุกหน้าที่จำแนกเป็น freight_invoice
      python scripts/fi_test.py XTRIM      เฉพาะไฟล์ที่ชื่อขึ้นต้นด้วยคำนี้
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from customs_checker.tables import to_cells, group_rows            # noqa: E402
from customs_checker.doctype import classify                       # noqa: E402
from customs_checker.freight_invoice import analyze_freight_invoice  # noqa: E402

BOX = ROOT / "docs_out" / "_box_cache.json"
TITLE_ZONE = 0.22
FIELD_ORDER = ("invoice_no", "job_no", "invoice_date", "vessel", "feeder",
               "etd", "eta", "house_bl", "new_bl", "container",
               "packages", "gross_weight", "cbm", "origin", "destination")


def page_text(rows):
    return "\n".join(r.text() for r in rows)


def title_text(rows):
    if not rows:
        return ""
    ys = [c.y0 for r in rows for c in r.cells] + [c.y1 for r in rows for c in r.cells]
    top, bottom = min(ys), max(ys)
    cut = top + (bottom - top) * TITLE_ZONE
    return "\n".join(r.text() for r in rows if r.cy <= cut)


def main(prefix=""):
    cache = json.loads(BOX.read_text(encoding="utf-8"))
    n_doc = n_ok = n_issue = n_fail = 0
    n_field = n_got = 0
    for k in sorted(cache):
        if not k.startswith(prefix):
            continue
        rows = group_rows(to_cells(cache[k]))
        if not rows:
            continue
        if classify(page_text(rows), title_text(rows)).code != "freight_invoice":
            continue
        n_doc += 1
        r = analyze_freight_invoice(rows)
        print(f"\n{'=' * 78}\n{k}")
        print(f"  {r.status}")
        for c in r.charges:
            print(f"    {c.f1:>10,g} x {c.f2:<10,g} = {c.amount:>12,.2f}   "
                  f"ฐาน: {c.basis or 'ไม่ทราบ'}")
        if r.total is not None:
            print(f"    ยอดรวมท้ายใบ {r.total:,.2f}")
        q = " · ".join(f"{a} {b:,g}" for a, b in r.quantities.items())
        print(f"    ปริมาณในใบ: {q or '-'}")
        got = [f for f in FIELD_ORDER if r.fields.get(f)]
        n_field += len(FIELD_ORDER)
        n_got += len(got)
        print(f"    ช่องที่อ่านได้ {len(got)}/{len(FIELD_ORDER)}: "
              + ", ".join(f"{f}={r.fields[f]}" for f in got))
        miss = [f for f in FIELD_ORDER if not r.fields.get(f)]
        if miss:
            print(f"    ช่องที่อ่านไม่ได้: {', '.join(miss)}")
        for n in r.notes:
            print(f"    หมายเหตุ {n}")
        for i in r.issues:
            print(f"    ⚠ {i}")
        if r.charges and r.total is not None and not r.issues:
            n_ok += 1
        elif r.issues:
            n_issue += 1
        else:
            n_fail += 1
    print(f"\n{'=' * 78}")
    print(f"ใบแจ้งหนี้ค่าระวาง {n_doc} ใบ | ผลบวกตรงยอดรวม {n_ok} "
          f"| พบข้อขัดแย้ง {n_issue} | อ่านไม่ครบ {n_fail}")
    print(f"ช่องที่อ่านได้ {n_got}/{n_field}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "")
