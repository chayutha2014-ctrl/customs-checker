#!/usr/bin/env python3
"""ทดสอบตัวระบุสกุลเงินกับผล OCR จริง"""
from pathlib import Path
import csv, json, sys
from customs_checker.currency import resolve_currency

OUT = Path("docs_out")
T = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "_truth_blind.csv"
cache = json.loads((OUT / (T.stem + "_cache.json")).read_text(encoding="utf-8"))

print(f"{'เอกสาร':<10}{'เฉลย':>6}{'ระบบตอบ':>10}{'สถานะ':>18}  หลักฐาน")
ok = 0
buckets = {}
rows = list(csv.DictReader(T.open(encoding="utf-8")))
for r in rows:
    both = cache[f"{r['file']}/{r['page']}"]
    txt = both["rapidocr"] + "\n" + both["tesseract"]
    res = resolve_currency(txt)
    if res.code == r["currency"] and res.status == "ยืนยัน":
        hit, bucket = "✅", "auto"
    elif res.code == r["currency"]:
        hit, bucket = "🔵", "ask"          # ถูก แต่ขอให้คนยืนยัน
    elif res.code is None:
        hit, bucket = "⚠️", "ask"          # ไม่เดา ส่งให้คนดู
    else:
        hit, bucket = "❌", "silent"       # ตอบผิดแบบมั่นใจ — ห้ามเกิด
    buckets[bucket] = buckets.get(bucket, 0) + 1
    if bucket == "auto":
        ok += 1
    ev = ", ".join(sorted({m[0] for m in res.mentions}))[:40] or res.note[:40]
    print(f"{r['file']:<10}{r['currency']:>6}{(res.code or '-'):>10}"
          f"{res.status:>18}  {hit} {ev}")
n = len(rows)
print(f"\n{'ยืนยันอัตโนมัติ':<20}{buckets.get('auto',0)}/{n}")
print(f"{'ส่งให้คนยืนยัน':<20}{buckets.get('ask',0)}/{n}")
print(f"{'ผิดแบบเงียบ':<20}{buckets.get('silent',0)}/{n}   <- ต้องเป็น 0 เสมอ")
