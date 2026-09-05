# -*- coding: utf-8 -*-
"""ดูว่าทำไมหน้านั้นถึงจำแนกไม่ได้ — อ่านไม่ออก หรือไม่มีกฎรองรับ

ใช้ cache เดิม ไม่ OCR ซ้ำ จึงรันเร็ว
ใช้:  python scripts/why_unknown.py docs_in/*.pdf
"""
from __future__ import annotations
import sys, os, glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from customs_checker.doctype import classify, RULES, normalize, despace, _score_one  # noqa: E402
from split_docs import read_pages, load_cache                                        # noqa: E402


def main(paths):
    cache = load_cache()
    n_bad = 0
    for pdf in paths:
        for r in read_pages(pdf, cache, want_color=False):
            c = classify(r["text"], r["title"])
            if c.status == "ยืนยัน":
                continue
            n_bad += 1
            words = len(r["text"].split())
            print("=" * 100)
            print(f"{os.path.basename(pdf)}  หน้า {r['page']}   อ่านด้วย {r['how']}   "
                  f"ได้ {words} คำ   -> {c.status}  ({c.note})")

            pn, pf = normalize(r["text"]), despace(normalize(r["text"]))
            zn, zf = normalize(r["title"]), despace(normalize(r["title"]))
            sc = sorted((_score_one(x, zn, zf, pn, pf) for x in RULES),
                        key=lambda x: x.score, reverse=True)[:3]
            print("  คะแนน 3 อันดับแรก:")
            for s in sc:
                print(f"    {s.name_th:<24}{s.score:>5.0f}   {', '.join(s.evidence[:4]) or '(ไม่พบหลักฐานเลย)'}")

            if words < 25:
                print("  -> สาเหตุ: อ่านข้อความแทบไม่ได้เลย เป็นปัญหาของชั้น OCR ไม่ใช่กฎจำแนก")
            else:
                print("  -> สาเหตุ: อ่านได้แต่ไม่เข้ากฎไหน อาจเป็นเอกสารชนิดที่ยังไม่มีกฎ")
            print("  โซนหัวเรื่องที่อ่านได้:")
            print("    " + " ".join(r["title"].split())[:180] or "    (ว่าง)")
            print("  ข้อความทั้งหน้า 300 ตัวแรก:")
            print("    " + " ".join(r["text"].split())[:300])
    print("=" * 100)
    print(f"รวมหน้าที่ยังจำแนกไม่ได้ {n_bad} หน้า")


if __name__ == "__main__":
    files = [f for a in sys.argv[1:] for f in sorted(glob.glob(a))]
    if not files:
        print("ใช้: python scripts/why_unknown.py docs_in/*.pdf"); sys.exit(1)
    main(files)
