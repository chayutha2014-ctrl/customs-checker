#!/usr/bin/env python3
"""ค้นว่าเลขที่ Invoice แต่ละใบอยู่ในหน้าไหนของ docs_out/"""
from pathlib import Path
import json, re
from rapidocr_onnxruntime import RapidOCR

OUT = Path("docs_out")
CACHE = OUT / "_locate_cache.json"

VALUES = [
    # invoice_no, date, currency, total, qty1, price1
    ("FS60413",               "2026-08-17", "USD", "3393.00",   "300",  "10.75"),
    ("5230000677",            "2026-08-27", "CNY", "431945.00", "300",  "303.00"),
    ("IV010845",              "2026-09-01", "USD", "1760.00",   "2",    "790.00"),
    ("20260822SSI",           "2026-08-24", "CNY", "775091.00", "1000", "35.70"),
    ("20260826SNK",           "2026-08-24", "CNY", "644625.00", "4140", "31.90"),
    ("INV2609134",            "2026-09-02", "CNY", "401937.60", "8000", "35.28"),
    ("LTH26F11",              "2026-09-10", "USD", "2482.50",   "150",  "16.55"),
    ("WLKL-CTSW-2605B&06&7B", "2026-08-03", "-",   "-",         "3000", "-"),
]


def key(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def main() -> None:
    images = sorted(p for p in OUT.rglob("page_*")
                    if p.suffix.lower() in {".png", ".jpg", ".jpeg"})
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    rapid = RapidOCR()

    todo = [p for p in images if f"{p.parent.name}/{p.name}" not in cache]
    if todo:
        print(f"กำลังอ่าน {len(todo)} หน้า (ครั้งเดียว แล้วจะเก็บไว้ใช้ซ้ำ)")
    for n, p in enumerate(todo, 1):
        res, _ = rapid(str(p))
        cache[f"{p.parent.name}/{p.name}"] = " ".join(i[1] for i in (res or []))
        if n % 10 == 0:
            print(f"   {n}/{len(todo)}")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 64)
    rows = []
    for vals in VALUES:
        inv = vals[0]
        hits = [k for k, txt in cache.items() if key(inv) in key(txt)]
        print(f"\n{inv}")
        if not hits:
            print("   ไม่พบในหน้าใดเลย")
        for h in hits:
            print(f"   {h}")
        if len(hits) == 1:
            rows.append((hits[0], vals))

    print("\n" + "=" * 64)
    print("แถวที่เจอหน้าเดียวชัดเจน (คัดลอกไปใส่ _truth.csv ได้เลย)\n")
    for h, v in rows:
        f, pg = h.split("/")
        print(f"{f},{pg}," + ",".join(v))


if __name__ == "__main__":
    main()
