#!/usr/bin/env python3
"""ทดสอบ OCR ทุกหน้าใน docs_out/ แล้ววัดผลเป็นตัวเลข"""
from pathlib import Path
from collections import defaultdict
import pytesseract
from pytesseract import Output
from PIL import Image

OUT_DIR = Path("docs_out")
LANG = "eng+tha"
A4_WIDTH_IN = 8.27

DOC_KEYWORDS = {
    "Invoice":      ["COMMERCIAL INVOICE", "INVOICE NO", "INVOICE"],
    "Packing List": ["PACKING LIST", "PACKING"],
    "B/L":          ["BILL OF LADING", "SHIPPER", "CONSIGNEE", "PORT OF LOADING"],
    "Form CO":      ["CERTIFICATE OF ORIGIN", "ORIGIN CRITERIA", "ISSUED RETROACTIVELY"],
    "Declaration":  ["DECLARATION", "CUSTOMS"],
}


def guess_type(text: str) -> str:
    up = text.upper()
    best, score = "ไม่ทราบ", 0
    for name, keys in DOC_KEYWORDS.items():
        hits = sum(1 for k in keys if k.upper() in up)
        if hits > score:
            best, score = name, hits
    return best if score else "ไม่ทราบ"


def band(dpi: int) -> str:
    if dpi < 200:
        return "ต่ำกว่า 200"
    if dpi < 280:
        return "200-279"
    return "280 ขึ้นไป"


def main() -> None:
    images = sorted(p for p in OUT_DIR.rglob("page_*")
                    if p.suffix.lower() in {".png", ".jpg", ".jpeg"})
    if not images:
        print("ไม่พบภาพใน docs_out/ - รัน pdf_to_images.py ก่อน")
        return

    stats = defaultdict(list)
    types = defaultdict(int)
    print(f"กำลัง OCR {len(images)} หน้า (ใช้เวลาสักครู่)\n")

    for n, img_path in enumerate(images, 1):
        img = Image.open(img_path)
        dpi = round(img.width / A4_WIDTH_IN)

        data = pytesseract.image_to_data(img, lang=LANG, output_type=Output.DICT)
        confs = [int(c) for c in data["conf"] if str(c) != "-1"]
        words = [w for w in data["text"] if w.strip()]
        conf = sum(confs) / len(confs) if confs else 0
        doc_type = guess_type(" ".join(words))

        types[doc_type] += 1
        stats[band(dpi)].append((conf, len(words)))

        print(f"[{n:>3}/{len(images)}] {img_path.parent.name[:22]:<22} {img_path.name}  "
              f"{dpi:>4} DPI  conf {conf:5.1f}  คำ {len(words):>4}  {doc_type}")

    print("\n" + "=" * 62)
    print("ผลตามช่วงความละเอียด")
    print(f"{'ช่วง DPI':<12}{'หน้า':>8}{'ความมั่นใจเฉลี่ย':>20}{'คำเฉลี่ย/หน้า':>18}")
    for key in ["ต่ำกว่า 200", "200-279", "280 ขึ้นไป"]:
        rows = stats.get(key)
        if not rows:
            continue
        c = sum(r[0] for r in rows) / len(rows)
        w = sum(r[1] for r in rows) / len(rows)
        print(f"{key:<12}{len(rows):>8}{c:>20.1f}{w:>18.0f}")

    print("\nประเภทเอกสารที่เดาได้")
    for t, n in sorted(types.items(), key=lambda x: -x[1]):
        print(f"   {t:<14} {n:>3} หน้า")


if __name__ == "__main__":
    main()
