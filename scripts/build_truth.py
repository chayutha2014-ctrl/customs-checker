#!/usr/bin/env python3
"""เลือกหน้าที่เป็น Commercial Invoice จริง (ดูจากชื่อเอกสาร ไม่ใช่จากค่าที่จะวัด)"""
from pathlib import Path
import json, re

OUT = Path("docs_out")
cache = json.loads((OUT / "_locate_cache.json").read_text(encoding="utf-8"))

VALUES = [
    ("FS60413",               "2026-08-17", "USD", "3393.00",   "300",  "10.75"),
    ("5230000677",            "2026-08-27", "CNY", "431945.00", "300",  "303.00"),
    ("IV010845",              "2026-09-01", "USD", "1760.00",   "2",    "790.00"),
    ("20260822SSI",           "2026-08-24", "CNY", "775091.00", "1000", "35.70"),
    ("20260826SNK",           "2026-08-24", "CNY", "644625.00", "4140", "31.90"),
    ("INV2609134",            "2026-09-02", "CNY", "401937.60", "8000", "35.28"),
    ("LTH26F11",              "2026-09-10", "USD", "2482.50",   "150",  "16.55"),
    ("WLKL-CTSW-2605B&06&7B", "2026-08-03", "CNY", "46830.00",  "30",   "6.45"),
]


def key(s): return re.sub(r"[^A-Z0-9]", "", s.upper())


def title_score(text):
    """ให้คะแนนจากชื่อเอกสารเท่านั้น ไม่แตะค่าที่จะวัด"""
    up = re.sub(r"\s+", " ", text.upper())
    if "PACKING LIST" in up:          return -10
    if "CERTIFICATE OF ORIGIN" in up: return -10
    if "BILL OF LADING" in up:        return -10
    if "POLICY" in up or "INSURANCE" in up: return -5
    s = 0
    if "COMMERCIAL INVOICE" in up: s += 10
    if "UNIT PRICE" in up:         s += 3
    if "INVOICE NO" in up:         s += 1
    return s


rows = []
print(f"{'Invoice No.':<24}{'หน้าที่เลือก':<44}{'คะแนน':>6}")
for vals in VALUES:
    hits = [(k, title_score(t)) for k, t in cache.items() if key(vals[0]) in key(t)]
    hits.sort(key=lambda x: -x[1])
    if not hits or hits[0][1] <= 0:
        print(f"{vals[0]:<24}{'ไม่พบหน้าที่เป็น Commercial Invoice':<44}")
        continue
    page, sc = hits[0]
    others = [f"{h[0].split('/')[1]}({h[1]})" for h in hits[1:4]]
    print(f"{vals[0]:<24}{page:<44}{sc:>6}   รองลงมา: {', '.join(others)}")
    f, pg = page.split("/")
    rows.append(f"{f},{pg}," + ",".join(vals))

out = OUT / "_truth.csv"
out.write_text("file,page,invoice_no,invoice_date,currency,total_amount,"
               "line1_qty,line1_unit_price\n" + "\n".join(rows) + "\n", encoding="utf-8")
print(f"\nเขียน {len(rows)} แถวลง {out}")
