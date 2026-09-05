#!/usr/bin/env python3
"""ทดสอบตัวอ่าน Packing List กับกล่องข้อความจริงใน _box_cache.json

อ่านเป็น "ฉบับ" ไม่ใช่ "หน้า" — หน้าที่ต่อเนื่องกันของไฟล์เดียวกันถูกต่อเข้าด้วยกัน
เพราะแถวรวมอยู่แผ่นสุดท้ายแผ่นเดียว

ใช้:  python scripts/pl_test.py                 ทุกฉบับใน box cache
      python scripts/pl_test.py FUJIAN          เฉพาะไฟล์ที่ชื่อขึ้นต้นด้วยคำนี้
      python scripts/pl_test.py --debug         แสดงทุกคอลัมน์และการตรวจผลรวมทีละแถว
      python scripts/pl_test.py --all           ไม่กรองชนิดเอกสาร ลองอ่านทุกหน้า
      python scripts/pl_test.py --no-join       อ่านทีละหน้าแบบเดิม
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from customs_checker.tables import numeric_columns, _col_x          # noqa: E402
from customs_checker.packing_list import (analyze_packing_list,     # noqa: E402
                                          numeric_rows, TOL)
from pl_pages import pl_documents                                   # noqa: E402

OUT = ROOT / "docs_out"


def debug_columns(rows):
    cols = numeric_columns(numeric_rows(rows))
    print(f"    [debug] คอลัมน์ตัวเลขที่พบ {len(cols)}")
    for ci, col in enumerate(cols):
        nums = {ri: c.number() for ri, c in col.items() if c.number() is not None}
        raw = ", ".join(f"r{ri}={c.text}" for ri, c in sorted(col.items()))
        print(f"      คอลัมน์ {ci} x={_col_x(col):>6.0f}  {raw}")
        for ri, total in sorted(nums.items()):
            above = [v for r, v in nums.items() if r < ri]
            if not above:
                continue
            diff = sum(above) - total
            mark = ("ลงตัว" if abs(diff) <= max(TOL, abs(total) * 1e-6)
                    else f"ต่าง {diff:,.2f}")
            print(f"        ถ้าแถว {ri} ({total:,g}) เป็นยอดรวม: "
                  f"ผลบวกของแถวเหนือมัน {sum(above):,g} -> {mark}")


def main(prefix="", debug=False, take_all=False, join=True):
    f = OUT / "_box_cache.json"
    if not f.exists():
        print(f"ไม่พบ {f} — ต้องสร้าง box cache ก่อนด้วย scripts/build_boxes.py")
        return
    cache = json.loads(f.read_text(encoding="utf-8"))

    docs = pl_documents(cache, prefix, take_all, join)

    n_doc = n_ok = n_issue = n_fail = n_comb = n_multi = 0
    for label, keys, rows, text, c in docs:
        n_doc += 1
        if c.code == "invoice_packing_list":
            n_comb += 1
        if len(keys) > 1:
            n_multi += 1
        r = analyze_packing_list(rows, text)
        print(f"\n{'=' * 78}\n{label}   ({c.status})")
        if len(keys) > 1:
            print(f"  ต่อ {len(keys)} แผ่นเป็นฉบับเดียว: " + ", ".join(
                k.split('/')[-1] for k in keys))
        print(f"  {r.status}")
        if r.total_row is None and "ยืนยันด้วยยอดรวมที่เขียนเป็นข้อความ" not in r.status:
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
    print(f"Packing List ที่พบ {n_doc} ฉบับ (ใบรวมกับ Invoice {n_comb} · "
          f"หลายแผ่น {n_multi})  | ผลรวมลงตัวและไม่มีข้อขัดแย้ง {n_ok}  "
          f"| พบข้อขัดแย้ง {n_issue}  | อ่านตารางไม่ได้ {n_fail}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "",
         debug="--debug" in sys.argv, take_all="--all" in sys.argv,
         join="--no-join" not in sys.argv)
