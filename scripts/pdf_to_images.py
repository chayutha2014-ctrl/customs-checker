#!/usr/bin/env python3
"""
ดึงภาพจาก PDF ใน docs_in/ ไปเก็บที่ docs_out/
- หน้าที่มีภาพเดียวเต็มหน้า      -> ดึงต้นฉบับตรง (ไม่บีบซ้ำ)
- หน้าที่แยกหลายชั้น (MRC)       -> เรนเดอร์รวมทุกชั้นที่ 300 DPI
- หน้าที่เป็น PDF ข้อความ         -> เรนเดอร์ที่ 300 DPI
"""
from pathlib import Path
import pymupdf as fitz

TARGET_DPI = 300
TEXT_THRESHOLD = 50
IN_DIR = Path("docs_in")
OUT_DIR = Path("docs_out")


def largest_image(doc, page):
    best = None
    for info in page.get_images(full=True):
        try:
            img = doc.extract_image(info[0])
        except Exception:
            continue
        if img["width"] * img["height"] < 100_000:
            continue
        if best is None or img["width"] * img["height"] > best["width"] * best["height"]:
            best = img
    return best


def process(pdf_path: Path) -> list[dict]:
    doc = fitz.open(pdf_path)
    out_sub = OUT_DIR / pdf_path.stem
    out_sub.mkdir(parents=True, exist_ok=True)
    rows = []

    for i, page in enumerate(doc, start=1):
        chars = len(page.get_text().strip())
        has_text = chars >= TEXT_THRESHOLD
        page_w_in = (page.rect.width / 72) or 1
        n_layers = len(page.get_images(full=True))
        big = largest_image(doc, page)
        native = round(big["width"] / page_w_in) if big else 0

        # เรนเดอร์เมื่อ: เป็นหน้าข้อความ / แยกหลายชั้น / หาภาพไม่เจอ
        if has_text or n_layers > 1 or big is None:
            pix = page.get_pixmap(dpi=TARGET_DPI)
            out = out_sub / f"page_{i:03d}.png"
            pix.save(out)
            mode = "ข้อความ " if has_text else ("รวมชั้น " if n_layers > 1 else "เรนเดอร์")
            dpi = TARGET_DPI
        else:
            out = out_sub / f"page_{i:03d}.{big['ext']}"
            out.write_bytes(big["image"])
            mode = "ต้นฉบับ"
            dpi = native

        rows.append({"page": i, "mode": mode, "dpi": dpi, "layers": n_layers,
                     "native": native, "kb": out.stat().st_size // 1024})
    doc.close()
    return rows


def main() -> None:
    pdfs = sorted(IN_DIR.rglob("*.pdf"))
    if not pdfs:
        print(f"ไม่พบไฟล์ PDF ใน {IN_DIR}/")
        return

    counts = {}
    for pdf in pdfs:
        rows = process(pdf)
        print(f"\n{pdf.name}  ({len(rows)} หน้า)")
        for r in rows:
            note = f"  [ต้นฉบับ {r['native']} DPI, {r['layers']} ชั้น]" if r["mode"] == "รวมชั้น " else ""
            print(f"   หน้า {r['page']:>2}  {r['mode']}  {r['dpi']:>4} DPI  {r['kb']:>5} KB{note}")
            counts[r["mode"]] = counts.get(r["mode"], 0) + 1

    total = sum(counts.values())
    print("\n" + "=" * 58)
    print(f"ไฟล์ {len(pdfs)} · หน้า {total}")
    for mode, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"   {mode}  {n:>3} หน้า ({n/total*100:.0f}%)")


if __name__ == "__main__":
    main()
