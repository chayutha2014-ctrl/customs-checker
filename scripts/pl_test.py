#!/usr/bin/env python3
"""ทดสอบตัวอ่าน Packing List กับกล่องข้อความจริงใน _box_cache.json

ใช้ท่อเดิมของ table_test2.py — ต่างกันที่หาเองว่าหน้าไหนเป็น Packing List
แทนที่จะรับรายการจากไฟล์เฉลย

ใช้:  python scripts/pl_test.py                 ทุกหน้าใน box cache
      python scripts/pl_test.py FUJIAN          เฉพาะไฟล์ที่ชื่อขึ้นต้นด้วยคำนี้
      python scripts/pl_test.py --debug         แสดงทุกคอลัมน์และการตรวจผลรวมทีละแถว
      python scripts/pl_test.py --all           ไม่กรองชนิดเอกสาร ลองอ่านทุกหน้า
"""
from pathlib import Path
import json, sys

from customs_checker.tables import to_cells, group_rows
from customs_checker.doctype import classify
from customs_checker.packing_list import (analyze_packing_list, numeric_rows,
                                          find_total_row, TOL)
from customs_checker.tables import numeric_columns, _col_x

OUT = Path("docs_out")
TITLE_ZONE = 0.22


def page_text(rows):
    return "\n".join(r.text() for r in rows)


def title_text(rows):
    """ข้อความในโซนหัวเรื่อง — คิดจากพิกัดจริง ไม่ใช่จำนวนบรรทัด"""
    if not rows:
        return ""
    ys = [c.y0 for r in rows for c in r.cells] + [c.y1 for r in rows for c in r.cells]
    top, bottom = min(ys), max(ys)
    cut = top + (bottom - top) * TITLE_ZONE
    return "\n".join(r.text() for r in rows if r.cy <= cut)


def debug_columns(rows):
    """แสดงทุกคอลัมน์ตัวเลข และผลการถามว่าแถวไหนเท่ากับผลบวกของแถวที่เหลือ"""
    cols = numeric_columns(numeric_rows(rows))
    print(f"    [debug] คอลัมน์ตัวเลขที่พบ {len(cols)}")
    for ci, col in enumerate(cols):
        nums = {ri: c.number() for ri, c in col.items() if c.number() is not None}
        raw = ", ".join(f"r{ri}={c.text}" for ri, c in sorted(col.items()))
        print(f"      คอลัมน์ {ci} x={_col_x(col):>6.0f}  {raw}")
        for ri, total in sorted(nums.items()):
            rest = [v for r, v in nums.items() if r != ri]
            if not rest:
                continue
            diff = sum(rest) - total
            mark = "ลงตัว" if abs(diff) <= max(TOL, abs(total) * 1e-6) else f"ต่าง {diff:,.2f}"
            print(f"        ถ้าแถว {ri} ({total:,g}) เป็นยอดรวม: "
                  f"ผลบวกที่เหลือ {sum(rest):,g} -> {mark}")


def main(prefix="", debug=False, take_all=False):
    f = OUT / "_box_cache.json"
    if not f.exists():
        print(f"ไม่พบ {f} — ต้องสร้าง box cache ก่อน (สคริปต์เดียวกับที่ table_test2.py ใช้)")
        return
    cache = json.loads(f.read_text(encoding="utf-8"))
    keys = sorted(k for k in cache if k.startswith(prefix))
    print(f"หน้าที่มีกล่องข้อความทั้งหมด {len(keys)} หน้า")

    n_pl = n_ok = n_issue = n_fail = n_comb = 0
    for k in keys:
        rows = group_rows(to_cells(cache[k]))
        if not rows:
            continue
        c = classify(page_text(rows), title_text(rows))
        if c.code not in ("packing_list", "invoice_packing_list") and not take_all:
            continue
        n_pl += 1
        if c.code == "invoice_packing_list":
            n_comb += 1
        r = analyze_packing_list(rows, page_text(rows))
        print(f"\n{'=' * 78}\n{k}   ({c.status})")
        print(f"  {r.status}")
        if r.total_row is None:
            n_fail += 1
            if debug:
                debug_columns(rows)
        else:
            for col in r.columns:
                mark = " (บรรทัดเดียว)" if col.trivial else ""
                vals = ", ".join(f"{v:,g}" for v in col.values[:5])
                more = f" ...อีก {len(col.values) - 5}" if len(col.values) > 5 else ""
                print(f"    คอลัมน์ x={col.x:>6.0f}  [{vals}{more}]  "
                      f"รวม {col.computed:,g} = ยอดพิมพ์ {col.printed:,g}{mark}")
            if r.issues:
                n_issue += 1
            else:
                n_ok += 1
        for t in r.texts:
            print(f"    ข้อความ: {t.value:,g} {t.unit:<5} [{t.matched}]  «{t.raw[:60]}»")
        for i in r.issues:
            print(f"    ⚠ {i}")

    print(f"\n{'=' * 78}")
    print(f"Packing List ที่พบ {n_pl} หน้า (เป็นใบรวมกับ Invoice {n_comb} หน้า)  "
          f"| ผลรวมลงตัวและไม่มีข้อขัดแย้ง {n_ok}  "
          f"| พบข้อขัดแย้ง {n_issue}  | อ่านตารางไม่ได้ {n_fail}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "",
         debug="--debug" in sys.argv, take_all="--all" in sys.argv)
