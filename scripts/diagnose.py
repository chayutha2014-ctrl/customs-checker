#!/usr/bin/env python3
"""ดูว่า OCR เห็นอะไรบ้างในฟิลด์ที่พลาด"""
from pathlib import Path
import csv, json, re

OUT = Path("docs_out")
import sys
T = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "_truth.csv"
cache = json.loads((OUT / (T.stem + "_cache.json")).read_text(encoding="utf-8"))
rows = list(csv.DictReader(T.open(encoding="utf-8")))

DATE_RE = re.compile(
    r"\d{1,4}[\s./-]*(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*[\s./-]*\d{2,4}"
    r"|(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*[\s./-]*\d{1,2}[\s,./-]*\d{2,4}"
    r"|\d{1,4}[/.-]\d{1,2}[/.-]\d{2,4}", re.I)
CUR_RE = re.compile(r"\b(USD|CNY|RMB|EUR|JPY|THB|US\$|HK\$)\b|[¥$€₩]", re.I)

for r in rows:
    key = f"{r['file']}/{r['page']}"
    txt = cache[key]["rapidocr"] + " " + cache[key]["tesseract"]
    flat = re.sub(r"\s+", " ", txt)

    print(f"\n{'='*72}\n{r['invoice_no']}   ({r['file']}/{r['page']})")
    print(f"  เฉลยวันที่ : {r['invoice_date']}")
    dates = sorted(set(m.group(0).strip() for m in DATE_RE.finditer(flat)))[:8]
    print(f"  OCR เห็น   : {dates if dates else 'ไม่พบรูปแบบวันที่เลย'}")

    print(f"  เฉลยสกุล  : {r['currency']}")
    curs = sorted(set(m.group(0).upper() for m in CUR_RE.finditer(flat)))
    print(f"  OCR เห็น   : {curs if curs else 'ไม่พบ'}")

    if r["total_amount"] not in ("", "-"):
        want = float(r["total_amount"])
        nums = sorted({float(t.replace(",", "")) for t in
                       re.findall(r"\d[\d,]*\.\d{2}", flat)}, reverse=True)[:6]
        print(f"  เฉลยยอดรวม: {want:,.2f}")
        print(f"  ตัวเลขใหญ่สุดที่เจอ: {[f'{n:,.2f}' for n in nums]}")
