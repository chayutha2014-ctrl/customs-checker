#!/usr/bin/env python3
"""ทดสอบว่าการรวมคำของ merge_words() ทำให้เลขในตารางเพี้ยนหรือไม่

อ่าน PDF ใหม่ทุกรอบด้วยค่า gap ต่างกัน แล้ววัดผลกับเฉลย
ไม่แตะ _box_cache.json เลย รันกี่ครั้งก็ได้ ไม่ทำลายอะไร

ใช้:  python scripts/gap_sweep.py
      python scripts/gap_sweep.py VORETO SHIJUN
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from customs_checker.tables import to_cells, group_rows, analyze_invoice  # noqa: E402
import build_boxes as bb                                                  # noqa: E402

TRUTH = {
    "FUJIAN": 100420.15,
    "VORETO": 26947.32,
    "HUANYU": 10797.20,
    "ITALISA": 3090.00,
    "SHIJUN": 190028.50,
}

GAPS = [0.0, 0.15, 0.3, 0.5, 0.8, 1.2]


def find_pdf(stem):
    for d in ("docs_in", "docs_out", "."):
        p = ROOT / d / f"{stem}.pdf"
        if p.exists():
            return p
    hits = sorted(ROOT.rglob(f"{stem}.pdf"))
    return hits[0] if hits else None


def cells_for(pdf, gap, ocr=False):
    """คืนเซลล์ของทุกหน้าในไฟล์ ที่ค่า gap ที่กำหนด"""
    allcells = []
    for p in range(1, bb.n_pages(pdf) + 1):
        if ocr:
            c, _ = bb.ocr_cells(pdf, p)
        else:
            lines = bb.words_from_pdf(pdf, p)
            if sum(len(w) for w in lines) < bb.TEXT_LAYER_MIN_WORDS:
                c, _ = bb.ocr_cells(pdf, p)
            else:
                c = bb.merge_words(lines, gap=gap)
        allcells.append(c)
    return allcells


def measure(pages):
    rows = []
    for c in pages:
        rows += group_rows(to_cells(bb.to_cache_format(c)))
    return analyze_invoice(rows)


def show(label, res, truth):
    comp = res.get("computed")
    ok = comp is not None and abs(comp - truth) < 0.02
    print(f"    {label:<16} บรรทัด {len(res.get('lines', [])):3d}  "
          f"คำนวณ {('ไม่พบ' if comp is None else format(comp, ',.2f')):>14}  "
          f"{'✅' if ok else '❌'}")
    return ok


def main():
    want = [a for a in sys.argv[1:] if not a.startswith("--")] or sorted(TRUTH)
    for stem in want:
        truth = TRUTH.get(stem)
        pdf = find_pdf(stem)
        if truth is None or pdf is None:
            print(f"\n=== {stem} === ไม่พบไฟล์หรือเฉลย ข้าม")
            continue
        print(f"\n=== {stem}  เฉลย {truth:,.2f}   {pdf} ===")

        lines0 = bb.words_from_pdf(pdf, 1)
        has_text = sum(len(w) for w in lines0) >= bb.TEXT_LAYER_MIN_WORDS
        print(f"    หน้าแรกมี text layer: {'ใช่' if has_text else 'ไม่ (เป็นสแกน)'}")

        if has_text:
            for g in GAPS:
                try:
                    show(f"gap {g}", measure(cells_for(pdf, g)), truth)
                except Exception as e:                       # noqa: BLE001
                    print(f"    gap {g:<12} ผิดพลาด: {type(e).__name__}: {e}")
        try:
            show("OCR อย่างเดียว", measure(cells_for(pdf, 0.0, ocr=True)), truth)
        except Exception as e:                               # noqa: BLE001
            print(f"    OCR อย่างเดียว   ผิดพลาด: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
