#!/usr/bin/env python3
"""แสดงข้อความเฉพาะโซนหัวกระดาษ (22% บน) ของหน้าที่มีเลข Invoice นั้นๆ"""
from pathlib import Path
import json, re
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

OUT = Path("docs_out")
LOCATE = json.loads((OUT / "_locate_cache.json").read_text(encoding="utf-8"))
TCACHE = OUT / "_title_cache.json"
TOP = 0.22

INVOICES = ["FS60413", "5230000677", "IV010845", "20260822SSI",
            "20260826SNK", "INV2609134", "LTH26F11", "WLKL-CTSW-2605B&06&7B"]


def key(s): return re.sub(r"[^A-Z0-9]", "", s.upper())


def main():
    cache = json.loads(TCACHE.read_text(encoding="utf-8")) if TCACHE.exists() else {}
    rapid = RapidOCR()

    wanted = set()
    for inv in INVOICES:
        wanted |= {k for k, t in LOCATE.items() if key(inv) in key(t)}
    todo = [k for k in sorted(wanted) if k not in cache]

    if todo:
        print(f"อ่านโซนหัวกระดาษ {len(todo)} หน้า")
    for n, k in enumerate(todo, 1):
        p = OUT / k
        h = Image.open(p).height
        res, _ = rapid(str(p))
        top = [i[1] for i in (res or [])
               if sum(pt[1] for pt in i[0]) / 4 < h * TOP]
        cache[k] = " ".join(top)
        if n % 5 == 0:
            print(f"   {n}/{len(todo)}")
    TCACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 100)
    for inv in INVOICES:
        print(f"\n{inv}")
        for k in sorted(k for k, t in LOCATE.items() if key(inv) in key(t)):
            title = re.sub(r"\s+", " ", cache.get(k, ""))[:78]
            print(f"   {k.split('/')[0][:26]:<26} {k.split('/')[1]:<14} | {title}")


if __name__ == "__main__":
    main()
