#!/usr/bin/env python3
"""ดูหน้าที่จำแนกได้เป็นชนิดใดชนิดหนึ่ง และดูเซลล์ดิบของหน้านั้น

ใช้ตอนเริ่มออกแบบตัวอ่านเอกสารชนิดใหม่ ต้องเห็นโครงจริงก่อนเขียนกฎ

ใช้:  python scripts/dump_type.py                    นับทุกชนิด
      python scripts/dump_type.py freight_invoice    รายชื่อหน้าของชนิดนั้น
      python scripts/dump_type.py freight_invoice 1  เซลล์ดิบของหน้าที่ 1 ในรายชื่อ
      python scripts/dump_type.py freight_invoice ทุกหน้า   เซลล์ดิบทุกหน้า
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from customs_checker.tables import to_cells, group_rows      # noqa: E402
from customs_checker.doctype import classify                 # noqa: E402

BOX = ROOT / "docs_out" / "_box_cache.json"
TITLE_ZONE = 0.22


def page_text(rows):
    return "\n".join(r.text() for r in rows)


def title_text(rows):
    if not rows:
        return ""
    ys = [c.y0 for r in rows for c in r.cells] + [c.y1 for r in rows for c in r.cells]
    top, bottom = min(ys), max(ys)
    cut = top + (bottom - top) * TITLE_ZONE
    return "\n".join(r.text() for r in rows if r.cy <= cut)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cache = json.loads(BOX.read_text(encoding="utf-8"))

    pages = []
    for k in sorted(cache):
        rows = group_rows(to_cells(cache[k]))
        if not rows:
            continue
        c = classify(page_text(rows), title_text(rows))
        pages.append((k, rows, c))

    if not args:
        n = Counter(c.code for _, _, c in pages)
        print(f"หน้าทั้งหมด {len(pages)} หน้า")
        for code, cnt in n.most_common():
            print(f"  {code or '(ไม่ทราบชนิด)':<24} {cnt:>3} หน้า")
        return

    want = args[0]
    got = [(k, rows, c) for k, rows, c in pages if c.code == want]
    if not got:
        print(f"ไม่พบหน้าชนิด {want}")
        return

    if len(args) == 1:
        print(f"ชนิด {want} มี {len(got)} หน้า")
        for i, (k, rows, c) in enumerate(got, start=1):
            print(f"  {i:>2}. {k:<46} {len(rows):>3} แถว  ({c.status})")
        print("\nดูเซลล์ดิบ: python scripts/dump_type.py "
              f"{want} 1     หรือใส่ ทุกหน้า แทนเลข")
        return

    pick = args[1]
    show = got if pick in ("ทุกหน้า", "all") else [got[int(pick) - 1]]
    for k, rows, c in show:
        print(f"\n{'=' * 78}\n### {k}   ({c.status})")
        for ri, r in enumerate(rows):
            print(f"  r{ri:<3} " + " | ".join(cell.text for cell in r.cells))


if __name__ == "__main__":
    main()
