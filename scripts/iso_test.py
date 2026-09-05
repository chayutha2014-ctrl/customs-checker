#!/usr/bin/env python3
"""แยกตัวแปรทีละตัว เพื่อหาว่าอะไรทำให้ยอดคำนวณของ invoice เปลี่ยนไป

ใช้กล่องชุดเดิมใน _box_cache.json ทั้งหมด ไม่ OCR ใหม่ ไม่เขียนทับอะไร
เปลี่ยนเฉพาะพฤติกรรมของ parse_number ทีละข้อ แล้ววัดผลกับเฉลย

ใช้:  python scripts/iso_test.py
      python scripts/iso_test.py --cells VORETO     พิมพ์เซลล์ดิบของไฟล์นั้นด้วย
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from customs_checker import numbers as N          # noqa: E402
from customs_checker import tables as T           # noqa: E402

TRUTH = {
    "FUJIAN": 100420.15,
    "VORETO": 26947.32,
    "HUANYU": 10797.20,
    "ITALISA": 3090.00,
    "SHIJUN": 190028.50,
}

NEVER = re.compile(r"(?!x)x")        # regex ที่ไม่มีวันตรงกับอะไรเลย


def keys_for(cache, stem):
    """เอาเฉพาะนามสกุลเดียว กันปัญหาคีย์ซ้ำที่ทำให้ตารางถูกนับสองรอบ"""
    ks = [k for k in cache if k.split("/")[0] == stem]
    sufs = sorted({Path(k).suffix.lower() for k in ks})
    pick = ".png" if ".png" in sufs else (sufs[0] if sufs else None)
    return sorted(k for k in ks if Path(k).suffix.lower() == pick), pick


def measure(cache, keys):
    rows = []
    for k in keys:
        rows += T.group_rows(T.to_cells(cache[k]))
    return T.analyze_invoice(rows)


def report(name, cache, order):
    print(f"\n--- {name} ---")
    hit = 0
    for stem in order:
        keys, suf = keys_for(cache, stem)
        if not keys:
            continue
        res = measure(cache, keys)
        comp = res.get("computed")
        ok = comp is not None and abs(comp - TRUTH[stem]) < 0.02
        hit += ok
        print(f"  {stem:<9} {suf:<6} บรรทัด {len(res.get('lines', [])):3d}  "
              f"คำนวณ {('ไม่พบ' if comp is None else format(comp, ',.2f')):>13}  "
              f"เฉลย {TRUTH[stem]:>13,.2f}  {'✅' if ok else '❌'}")
    print(f"  ผ่าน {hit}/{len(order)}")
    return hit


def main():
    cache = json.loads((ROOT / "docs_out" / "_box_cache.json").read_text())
    order = [s for s in sorted(TRUTH) if any(k.split("/")[0] == s for k in cache)]

    if "--cells" in sys.argv:
        i = sys.argv.index("--cells")
        stem = sys.argv[i + 1] if i + 1 < len(sys.argv) else order[0]
        keys, _ = keys_for(cache, stem)
        for k in keys:
            print(f"\n### {k}")
            for row in T.group_rows(T.to_cells(cache[k])):
                cells = getattr(row, "cells", row)
                txt = " | ".join(str(getattr(c, "text", c)) for c in cells)
                print(f"  {txt}")
        return

    report("ปัจจุบัน (มีทั้งการตัดหน่วย และกฎตัวคั่นผสม)", cache, order)

    keep = N._NUM_UNIT
    N._NUM_UNIT = NEVER
    try:
        report("ปิดการตัดหน่วยท้ายตัวเลข (27526PCS จะอ่านไม่ออก)", cache, order)
    finally:
        N._NUM_UNIT = keep

    print("\nอ่านผลอย่างไร")
    print("  ถ้าสองบล็อกเหมือนกันทุกบรรทัด = การแก้ numbers.py ไม่เกี่ยวกับเรื่องนี้เลย")
    print("  ถ้าบล็อกที่สองดีกว่า          = การตัดหน่วยคือต้นเหตุ ต้องจำกัดขอบเขต")


if __name__ == "__main__":
    main()
