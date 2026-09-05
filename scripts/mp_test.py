#!/usr/bin/env python3
"""ทดสอบตัวอ่านกรมธรรม์ประกันภัยกับหน้าจริงใน _box_cache.json"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from customs_checker.tables import to_cells, group_rows              # noqa: E402
from customs_checker.doctype import classify                         # noqa: E402
from customs_checker.marine_policy import analyze_marine_policy      # noqa: E402

BOX = ROOT / "docs_out" / "_box_cache.json"
TITLE_ZONE = 0.22
FIELDS = ("policy_no", "assured", "vessel", "sailing", "voyage_from",
          "voyage_to", "packages", "gross_weight", "invoice_no")


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
    n = ok = issue = fail = 0
    n_words = n_field = n_got = 0
    for k in sorted(cache):
        if not k.startswith(prefix):
            continue
        rows = group_rows(to_cells(cache[k]))
        if not rows:
            continue
        if classify(page_text(rows), title_text(rows)).code != "marine_policy":
            continue
        n += 1
        r = analyze_marine_policy(rows)
        print(f"\n{'=' * 78}\n{k}\n  {r.status}")
        for c in r.checks:
            print(f"    ✓ {c}")
        for i in r.issues:
            print(f"    ⚠ {i}")
        for x in r.notes:
            print(f"    หมายเหตุ {x}")
        got = [f for f in FIELDS if getattr(r, f) is not None]
        n_field += len(FIELDS)
        n_got += len(got)
        print("    " + " · ".join(f"{f}={getattr(r, f)}" for f in got))
        miss = [f for f in FIELDS if getattr(r, f) is None]
        if miss:
            print(f"    อ่านไม่ได้: {', '.join(miss)}")
        n_words += r.amount_in_words is not None
        if r.amount_insured is None:
            fail += 1
        elif r.issues:
            issue += 1
        else:
            ok += 1
    print(f"\n{'=' * 78}")
    print(f"กรมธรรม์ {n} ใบ | ตรวจผ่านหมด {ok} | พบข้อขัดแย้ง {issue} | อ่านไม่ได้ {fail}")
    print(f"ตัวหนังสือกำกับยืนยันได้ {n_words}/{n} · ช่องที่อ่านได้ {n_got}/{n_field}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "")
