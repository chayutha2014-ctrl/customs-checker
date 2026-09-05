#!/usr/bin/env python3
"""ดูว่า Form CO แต่ละหน้าเป็นแบบไหน โดยพิมพ์บรรทัดที่บอกชนิดออกมาดิบ ๆ

ยังไม่เดา ยังไม่เขียนกฎ — ดูข้อมูลก่อนว่ามีแบบไหนบ้าง
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from customs_checker.tables import to_cells, group_rows      # noqa: E402
from customs_checker.doctype import classify                 # noqa: E402

BOX = ROOT / "docs_out" / "_box_cache.json"
TITLE_ZONE = 0.22

# คำที่น่าจะอยู่ในบรรทัดบอกชนิดฟอร์ม
HINT = re.compile(
    r"FORM\s*[A-Z]{0,4}\b|CERTIFICATE|ORIGIN|AGREEMENT|REFERENCE\s*NO|"
    r"ASEAN|CHINA|KOREA|INDIA|JAPAN|AUSTRALIA|NEW\s*ZEALAND|RCEP|"
    r"ACFTA|ATIGA|AKFTA|AIFTA|AJCEP|AANZFTA|THAILAND-",
    re.I)


def page_text(rows):
    return "\n".join(r.text() for r in rows)


def title_text(rows):
    if not rows:
        return ""
    ys = [c.y0 for r in rows for c in r.cells] + [c.y1 for r in rows for c in r.cells]
    top, bottom = min(ys), max(ys)
    cut = top + (bottom - top) * TITLE_ZONE
    return "\n".join(r.text() for r in rows if r.cy <= cut)


def main(want="form_co", limit=6):
    cache = json.loads(BOX.read_text(encoding="utf-8"))
    for k in sorted(cache):
        rows = group_rows(to_cells(cache[k]))
        if not rows:
            continue
        if classify(page_text(rows), title_text(rows)).code != want:
            continue
        hits = []
        for r in rows:
            t = r.text().strip()
            if len(t) > 110 or not HINT.search(t):
                continue
            if t not in hits:
                hits.append(t)
        print(f"\n### {k}")
        for h in hits[:limit]:
            print(f"    {h[:104]}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "form_co",
         int(args[1]) if len(args) > 1 else 6)
