#!/usr/bin/env python3
"""ทดสอบการประกอบตารางกับใบ Invoice จริง"""
from pathlib import Path
import csv, json, sys
from rapidocr_onnxruntime import RapidOCR
from customs_checker.tables import (
    to_cells, group_rows, find_header_band, column_spans, read_row)

OUT = Path("docs_out")
BOX = OUT / "_box_cache.json"
T = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "_truth_blind.csv"
rows_truth = list(csv.DictReader(T.open(encoding="utf-8")))

cache = json.loads(BOX.read_text(encoding="utf-8")) if BOX.exists() else {}
rapid = RapidOCR()

for tr in rows_truth:
    folder = OUT / tr["file"]
    pages = sorted(p for p in folder.glob("page_*")
                   if p.suffix.lower() in {".png", ".jpg", ".jpeg"})

    print("\n" + "=" * 78)
    print(f"{tr['file']}   เฉลยยอดรวม {float(tr['total_amount']):,.2f}")

    grand, n_lines, bad = 0.0, 0, 0
    for pg in pages:
        key = f"{tr['file']}/{pg.name}"
        if key not in cache:
            res, _ = rapid(str(pg))
            cache[key] = [[[[float(x) for x in p] for p in i[0]], i[1]]
                          for i in (res or [])]
        cells = to_cells(cache[key])
        rows = group_rows(cells)
        hi, band = find_header_band(rows)
        if hi is None:
            print(f"  {pg.name}: ไม่พบหัวตาราง")
            continue
        cols = column_spans(band)
        print(f"  {pg.name}: หัวตารางจบที่แถว {hi} → {list(cols)}")
        print(f"     หัวตารางที่อ่านได้: {' | '.join(c.text for c in band)[:110]}")
        if not {"qty", "price", "amount"} <= set(cols):
            print("     ขาดคอลัมน์ที่จำเป็น ข้ามการตรวจคณิต")
            continue

        for r in rows[hi + 1:]:
            d = read_row(r, cols)
            q, p_, a = d.get("qty"), d.get("price"), d.get("amount")
            if not all(isinstance(v, float) for v in (q, p_, a)):
                continue
            ok = abs(q * p_ - a) <= max(0.01, a * 1e-6)
            if r.is_total_row():
                print(f"     [แถวรวม] {a:,.2f}")
                continue
            n_lines += 1
            grand += a
            if not ok:
                bad += 1
                print(f"     ✗ {q:,g} × {p_:,g} ≠ {a:,.2f}")

    want = float(tr["total_amount"])
    mark = "✅" if abs(grand - want) <= 0.01 else "❌"
    diff = grand - want
    print(f"  → {n_lines} รายการ, ไม่ลงตัว {bad}, รวม {grand:,.2f}  {mark}"
          + (f"  (ต่าง {diff:+,.2f})" if abs(diff) > 0.005 else ""))

BOX.write_text(json.dumps(cache), encoding="utf-8")
