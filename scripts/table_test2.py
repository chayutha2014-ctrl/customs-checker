#!/usr/bin/env python3
"""วิเคราะห์ตารางด้วยความสัมพันธ์ของตัวเลข ไม่พึ่งหัวตาราง"""
from pathlib import Path
import csv, json, sys
from customs_checker.tables import to_cells, group_rows, analyze_invoice

OUT = Path("docs_out")
cache = json.loads((OUT / "_box_cache.json").read_text(encoding="utf-8"))
T = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "_truth_blind.csv"

for tr in csv.DictReader(T.open(encoding="utf-8")):
    want = float(tr["total_amount"])
    allrows = []
    for key in sorted(k for k in cache if k.startswith(tr["file"] + "/")):
        allrows += group_rows(to_cells(cache[key]))

    r = analyze_invoice(allrows)
    got = r["computed"]
    ok = "✅" if got is not None and abs(got - want) <= 0.02 else "❌"
    print(f"\n{'='*72}\n{tr['file']:<10} เฉลย {want:>13,.2f}   "
          f"คำนวณ {(got or 0):>13,.2f}  {ok}")
    print(f"  คอลัมน์ตัวเลขที่พบ {r['n_numeric_cols']} · "
          f"บรรทัดสินค้า {len(r['lines'])} · {r['status']}")
    if r.get("missing_lines"):
        print(f"  ⚠ บรรทัดที่อ่านปริมาณ/ราคาไม่ครบ: "
              f"{[f'{v:,.2f}' for v in r['missing_lines']]}")
    if r.get("printed"):
        print(f"  ยอดพิมพ์ที่ตรงกัน {r['printed']:,.2f}")
    elif r.get("other_totals"):
        print(f"  ตัวเลขอื่นในคอลัมน์จำนวนเงิน {r['other_totals']}")
    for l in r["lines"][:4]:
        print(f"     {l['qty']:,g} × {l['price']:,g} = {l['amount']:,.2f}")
    if len(r["lines"]) > 4:
        print(f"     ... อีก {len(r['lines'])-4} บรรทัด")
