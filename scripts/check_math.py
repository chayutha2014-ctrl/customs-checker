#!/usr/bin/env python3
"""ทดสอบชั้นตรวจคณิตศาสตร์กับผล OCR ที่มีอยู่"""
from pathlib import Path
import csv, json, sys
from customs_checker.invoice_math import (
    extract_numbers, find_line_triples, sum_amounts, verify_total)

OUT = Path("docs_out")
T = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "_truth_blind.csv"
cache = json.loads((OUT / (T.stem + "_cache.json")).read_text(encoding="utf-8"))
rows = list(csv.DictReader(T.open(encoding="utf-8")))

print(f"{'เอกสาร':<12}{'เฉลยยอดรวม':>15}{'คำนวณได้':>15}{'รายการที่พบ':>13}  สถานะ")
for r in rows:
    txt = cache[f"{r['file']}/{r['page']}"]["rapidocr"]
    nums = extract_numbers(txt)
    triples = find_line_triples(nums)
    res = verify_total(triples, nums)
    want = float(r["total_amount"]) if r["total_amount"] not in ("", "-") else None
    got = res["computed"]
    ok = "✅" if (want and got and abs(want - got) <= 0.01) else "❌"
    print(f"{r['file']:<12}{want:>15,.2f}{(got if got else 0):>15,.2f}"
          f"{len(triples):>13}  {ok} {res['status']}")

print("\nรายละเอียดรายการที่พบในแต่ละใบ")
for r in rows:
    txt = cache[f"{r['file']}/{r['page']}"]["rapidocr"]
    triples = find_line_triples(extract_numbers(txt))
    print(f"\n{r['file']} — {len(triples)} รายการ, รวม {sum_amounts(triples):,.2f}")
    for t in triples[:6]:
        print(f"   {t}")
    if len(triples) > 6:
        print(f"   ... อีก {len(triples)-6} รายการ")
