#!/usr/bin/env python3
"""
เทียบ OCR สองเครื่องยนต์เฉพาะ 'ตัวเลข' เพื่อหาจุดที่น่าจะอ่านผิด
ตรงกัน = เชื่อได้ · ต่างกัน = ต้องให้คนดู
"""
from pathlib import Path
from collections import defaultdict
import json
import re
import pytesseract
from pytesseract import Output
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

OUT_DIR = Path("docs_out")
REPORT = Path("docs_out/_compare.json")
A4_W_IN = 8.27
NUM_RE = re.compile(r"\d[\d,.\-/]*")

DOC_KEYWORDS = {
    "Invoice":      ["COMMERCIAL INVOICE", "INVOICE NO", "UNIT PRICE"],
    "Packing List": ["PACKING LIST", "NET WEIGHT", "GROSS WEIGHT"],
    "B/L":          ["BILL OF LADING", "PORT OF LOADING", "PORT OF DISCHARGE"],
    "Form CO":      ["CERTIFICATE OF ORIGIN", "ORIGIN CRITERIA",
                     "ISSUED RETROACTIVELY", "EXPORTER'S BUSINESS NAME"],
    "ใบขนสินค้า":   ["ใบขนสินค้า", "กรมศุลกากร", "พิกัดศุลกากร", "ราคาของ"],
    "ประกันภัย":    ["MARINE CARGO", "POLICY NO", "กรมธรรม์", "INSURANCE"],
    "ค่าระวาง":     ["FREIGHT INVOICE", "OCEAN FREIGHT", "ค่าระวาง", "AIRWAY BILL"],
}


def guess_type(text: str) -> str:
    up = text.upper()
    best, score = "ไม่ทราบ", 0
    for name, keys in DOC_KEYWORDS.items():
        hits = sum(1 for k in keys if k.upper() in up)
        if hits > score:
            best, score = name, hits
    return best if score else "ไม่ทราบ"


def numbers(text: str) -> set:
    """ดึงเฉพาะตัวเลขที่ยาวพอจะมีความหมาย (อย่างน้อย 3 หลัก)"""
    out = set()
    for tok in NUM_RE.findall(text):
        norm = tok.replace(",", "").rstrip(".-/")
        if sum(c.isdigit() for c in norm) >= 3:
            out.add(norm)
    return out


def main() -> None:
    images = sorted(p for p in OUT_DIR.rglob("page_*")
                    if p.suffix.lower() in {".png", ".jpg", ".jpeg"})
    if not images:
        print("ไม่พบภาพใน docs_out/")
        return

    print("กำลังโหลดโมเดล RapidOCR (ครั้งแรกจะดาวน์โหลดราว 15 MB)...")
    rapid = RapidOCR()

    by_type = defaultdict(lambda: {"both": 0, "t_only": 0, "r_only": 0, "pages": 0})
    records = []
    print(f"เทียบ {len(images)} หน้า\n")

    for n, path in enumerate(images, 1):
        img = Image.open(path)
        dpi = round(img.width / A4_W_IN)

        d = pytesseract.image_to_data(img, lang="eng+tha", output_type=Output.DICT)
        t_words = [w for w in d["text"] if w.strip()]
        t_text = " ".join(t_words)
        t_nums = numbers(t_text)

        res, _ = rapid(str(path))
        r_text = " ".join(item[1] for item in (res or []))
        r_nums = numbers(r_text)

        both = t_nums & r_nums
        t_only = t_nums - r_nums
        r_only = r_nums - t_nums
        union = t_nums | r_nums
        agree = len(both) / len(union) * 100 if union else 0

        doc_type = guess_type(t_text)
        s = by_type[doc_type]
        s["both"] += len(both); s["t_only"] += len(t_only)
        s["r_only"] += len(r_only); s["pages"] += 1

        records.append({
            "file": path.parent.name, "page": path.name, "dpi": dpi,
            "type": doc_type, "agree_pct": round(agree, 1),
            "both": sorted(both), "tess_only": sorted(t_only),
            "rapid_only": sorted(r_only),
        })

        flag = "  <-- ตรวจ" if agree < 60 else ""
        print(f"[{n:>3}/{len(images)}] {path.parent.name[:20]:<20} {path.name}  "
              f"{doc_type:<12} ตรงกัน {agree:5.1f}%  "
              f"({len(both)} ตรง / {len(t_only)}+{len(r_only)} ต่าง){flag}")

    REPORT.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n" + "=" * 66)
    print("ความน่าเชื่อถือของตัวเลข แยกตามประเภทเอกสาร")
    print(f"{'ประเภท':<14}{'หน้า':>6}{'ตัวเลขตรงกัน':>14}{'ต่างกัน':>10}{'% ตรงกัน':>12}")
    for t, s in sorted(by_type.items(), key=lambda x: -x[1]["pages"]):
        diff = s["t_only"] + s["r_only"]
        tot = s["both"] + diff
        pct = s["both"] / tot * 100 if tot else 0
        print(f"{t:<14}{s['pages']:>6}{s['both']:>14}{diff:>10}{pct:>11.1f}%")

    worst = sorted(records, key=lambda r: r["agree_pct"])[:5]
    print("\n5 หน้าที่ตัวเลขน่าเชื่อถือน้อยที่สุด")
    for r in worst:
        print(f"   {r['file'][:24]:<24} {r['page']}  {r['type']:<12} {r['agree_pct']:>5.1f}%")
    print(f"\nรายละเอียดเต็มบันทึกไว้ที่ {REPORT}")


if __name__ == "__main__":
    main()
