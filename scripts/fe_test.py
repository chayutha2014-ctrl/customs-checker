#!/usr/bin/env python3
"""ทดสอบตัวอ่าน Form E กับหน้าจริงใน _box_cache.json

อ่านเป็นฉบับ — แผ่นที่ต่อเนื่องกันในไฟล์เดียวกันถือเป็นฉบับเดียว
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from customs_checker.tables import to_cells, group_rows        # noqa: E402
from customs_checker.doctype import classify                   # noqa: E402
from customs_checker.form_e import (_dist, analyze_form_e,  # noqa: E402
                                    combine_sheets, group_sheets)

BOX = ROOT / "docs_out" / "_box_cache.json"
TITLE_ZONE = 0.22
_PAGENO = re.compile(r"page_(\d+)", re.I)


def page_text(rows):
    return "\n".join(r.text() for r in rows)


def title_text(rows):
    if not rows:
        return ""
    ys = [c.y0 for r in rows for c in r.cells] + [c.y1 for r in rows for c in r.cells]
    top, bottom = min(ys), max(ys)
    cut = top + (bottom - top) * TITLE_ZONE
    return "\n".join(r.text() for r in rows if r.cy <= cut)


def main(prefix=""):
    cache = json.loads(BOX.read_text(encoding="utf-8"))
    pages = []
    for k in sorted(cache):
        if not k.startswith(prefix):
            continue
        rows = group_rows(to_cells(cache[k]))
        if not rows:
            continue
        if classify(page_text(rows), title_text(rows)).code != "form_co":
            continue
        pages.append((k, rows))

    # จัดกลุ่มเป็นฉบับ — รวมแผ่นก่อน แล้วค่อยเลือกเลขที่อ้างอิง
    # ถ้าจัดกลุ่มด้วยเลขที่ที่ยังไม่ได้แก้ แผ่นที่ OCR อ่านเพี้ยนจะกลายเป็นคนละฉบับ
    by_file = defaultdict(list)
    for k, rows in pages:
        by_file[k.split("/")[0]].append((k, analyze_form_e(rows)))
    docs = []
    for stem, pairs in sorted(by_file.items()):
        for g in group_sheets(pairs):
            docs.append((stem, g))

    n_doc = n_ok = n_issue = 0
    n_check = n_note = 0
    for stem, group in docs:
        n_doc += 1
        out = combine_sheets([r for _, r in group])
        ref = out["reference_no"] or "ไม่ทราบเลขที่"
        print(f"\n{'=' * 78}\n{stem} · {ref} · {len(group)} แผ่น")
        for c in out["checks"]:
            print(f"  ✓ {c}")
        for i in out["issues"]:
            print(f"  ⚠ {i}")
        for x in out["notes"]:
            print(f"  หมายเหตุ {x}")
        bad = 0
        for k, r in group:
            page = k.split("/")[-1]
            print(f"  -- {page}  {r.status}")
            for c in r.checks:
                n_check += 1
                print(f"       ✓ {c}")
            for i in r.issues:
                # คำเตือนเรื่องเลขที่อ้างอิงของแผ่นเดียว ถ้าระดับฉบับแก้ไปแล้ว
                # ด้วยเสียงข้างมาก ก็ไม่ต้องฟ้องซ้ำ ตัววิเคราะห์รายแผ่นไม่รู้ว่ามีแผ่นอื่น
                if ("เลขที่อ้างอิง" in i and out["reference_no"]
                        and r.reference_no
                        and _dist(r.reference_no, out["reference_no"]) <= 1):
                    continue
                bad += 1
                print(f"       ⚠ {i}")
            for x in r.notes:
                n_note += 1
                print(f"       หมายเหตุ {x}")
        if bad or out["issues"]:
            n_issue += 1
        else:
            n_ok += 1

    print(f"\n{'=' * 78}")
    print(f"Form E {n_doc} ฉบับ | ไม่พบข้อขัดแย้ง {n_ok} | พบข้อขัดแย้ง {n_issue}")
    print(f"ข้อที่ตรวจผ่าน {n_check} · หมายเหตุ {n_note}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "")
