#!/usr/bin/env python3
"""เทียบผลอ่านตารางระหว่างชุดกล่องเก่า (.jpeg) กับชุดใหม่ (.png) ในคีย์เดียวกัน

ใช้ตอบคำถามเดียว: build_boxes.py อ่านหน้าเดียวกันได้แย่กว่าท่อเดิมหรือไม่
ไม่แก้ไขไฟล์ใดๆ อ่าน cache อย่างเดียว
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from customs_checker.tables import to_cells, group_rows, analyze_invoice  # noqa: E402

TRUTH = {
    "FUJIAN": 100420.15,
    "VORETO": 26947.32,
    "HUANYU": 10797.20,
    "ITALISA": 3090.00,
    "SHIJUN": 190028.50,
}


def money(v):
    return "ไม่พบ" if v is None else format(v, ",.2f")


def run(cache, keys):
    rows = []
    for k in sorted(keys):
        rows += group_rows(to_cells(cache[k]))
    return analyze_invoice(rows)


def main():
    cache = json.loads((ROOT / "docs_out" / "_box_cache.json").read_text())

    # จัดกลุ่มคีย์ตาม (ชื่อไฟล์, นามสกุล)
    groups = defaultdict(list)
    for k in cache:
        stem = k.split("/")[0]
        if stem not in TRUTH:
            continue
        groups[(stem, Path(k).suffix.lower())].append(k)

    for stem in sorted(TRUTH):
        sufs = sorted({s for (f, s) in groups if f == stem})
        if not sufs:
            continue
        print(f"\n=== {stem}  เฉลย {TRUTH[stem]:,.2f} ===")
        for suf in sufs:
            keys = groups[(stem, suf)]
            try:
                res = run(cache, keys)
            except Exception as e:                       # noqa: BLE001
                print(f"  {suf:6s} ผิดพลาด: {type(e).__name__}: {e}")
                continue
            comp = res.get("computed")
            printed = res.get("printed")
            n = len(res.get("lines", []))
            mark = "✅" if comp is not None and abs(comp - TRUTH[stem]) < 0.02 else "❌"
            print(f"  {suf:6s} {len(keys)} คีย์  บรรทัด {n:3d}  "
                  f"คำนวณ {money(comp):>14}  ในเอกสาร {money(printed):>14}  {mark}")
            if res.get("guard"):
                print(f"         guard: {res['guard']}")
            if res.get("status"):
                print(f"         {res['status']}")
            un = res.get("unmatched") or res.get("missing_lines")
            if un:
                print(f"         ยอดที่ยังไม่เข้าคู่: {un}")
            if "--lines" in sys.argv:
                for ln in res.get("lines", []):
                    print(f"           {ln.get('qty')} x {ln.get('price')} = {ln.get('amount')}")

        # รวมทุกนามสกุล = สิ่งที่ table_test2.py ทำอยู่ตอนนี้
        if len(sufs) > 1:
            allk = [k for k in cache if k.split("/")[0] == stem]
            res = run(cache, allk)
            comp = res.get("computed")
            print(f"  รวมทุกคีย์ ({len(allk)}) บรรทัด {len(res.get('lines', [])):3d}  "
                  f"คำนวณ {money(comp)}  <- นี่คือสิ่งที่ table_test2.py เห็นตอนนี้")


if __name__ == "__main__":
    main()
