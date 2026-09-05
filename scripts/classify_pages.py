# -*- coding: utf-8 -*-
"""อ่านทุกหน้าของ PDF -> ตัดสินว่าใช้ text layer หรือ OCR -> จำแนกชนิดเอกสาร

ใช้:  python scripts/classify_pages.py docs_in/*.pdf
"""
from __future__ import annotations
import subprocess, sys, os, re, glob, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from customs_checker.doctype import classify, MIN_WORDS   # noqa: E402

TITLE_ZONE = 0.22          # สัดส่วนความสูงของโซนหัวเรื่อง
TEXT_LAYER_MIN_WORDS = 20
OCR_DPI = 200              # พอสำหรับ "หน้านี้คือเอกสารอะไร" ไม่ต้องใช้ 300  # หน้าที่มีคำน้อยกว่านี้ถือว่าเป็นสแกน


def _run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def page_size(pdf: str) -> tuple[float, float]:
    m = re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", _run(["pdfinfo", pdf]))
    return (float(m.group(1)), float(m.group(2))) if m else (595.0, 842.0)


def n_pages(pdf: str) -> int:
    m = re.search(r"^Pages:\s+(\d+)", _run(["pdfinfo", pdf]), re.M)
    return int(m.group(1)) if m else 0


def text_layer(pdf: str, p: int, crop: tuple | None = None) -> str:
    cmd = ["pdftotext", "-f", str(p), "-l", str(p)]
    if crop:
        x, y, w, h = crop
        cmd += ["-x", str(int(x)), "-y", str(int(y)), "-W", str(int(w)), "-H", str(int(h))]
    return _run(cmd + [pdf, "-"])


def _render(pdf: str, p: int, dpi: int) -> str | None:
    d = tempfile.mkdtemp()
    base = os.path.join(d, "pg")
    subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(p), "-l", str(p),
                    "-png", pdf, base], capture_output=True)
    img = glob.glob(base + "*.png")
    return img[0] if img else None


def _tess(img: str) -> str:
    langs = "tha+eng" if _has_tha() else "eng"
    return _run(["tesseract", img, "stdout", "-l", langs, "--psm", "3"])


_THA = None
def _has_tha() -> bool:
    global _THA
    if _THA is None:
        _THA = "tha" in _run(["tesseract", "--list-langs"])
    return _THA


def ocr_page(pdf: str, p: int, dpi: int = OCR_DPI) -> tuple[str, str]:
    """เรนเดอร์หน้าครั้งเดียว แล้ว OCR ทั้งหน้า + โซนหัวเรื่อง จากภาพเดียวกัน"""
    src = _render(pdf, p, dpi)
    if not src:
        return "", ""
    full = _tess(src)
    title = ""
    try:
        from PIL import Image
        im = Image.open(src)
        crop = src.replace(".png", "_t.png")
        im.crop((0, 0, im.width, int(im.height * TITLE_ZONE))).save(crop)
        title = _tess(crop)
    except Exception:
        pass
    return full, title


def classify_page(pdf: str, p: int):
    """จำแนกหน้าหนึ่ง — ใช้ text layer ก่อน ถ้าไม่มั่นใจจึงถอยไป OCR

    เหตุผล: PDF ที่สร้างจากโปรแกรมบางไฟล์วางหัวเรื่องเป็น "ภาพ" ไม่ใช่ข้อความ
    (B/L ของชุด 3 และ 5) text layer จึงมีแต่ที่อยู่ ไม่มีคำว่า BILL OF LADING
    """
    full = text_layer(pdf, p)
    if len(full.split()) >= TEXT_LAYER_MIN_WORDS:
        w, h = page_size(pdf)
        r = classify(full, text_layer(pdf, p, (0, 0, w, h * TITLE_ZONE)))
        if r.ok:
            return r, "text layer"
        f2, t2 = ocr_page(pdf, p)
        r2 = classify(f2 or full, t2)
        if r2.ok:
            return r2, "text+OCR"
        return (r if r.score >= r2.score else r2), "text+OCR"
    f, t = ocr_page(pdf, p)
    return classify(f, t), "OCR"


def main(paths: list[str]) -> None:
    print(f"{'ไฟล์':<34}{'หน้า':>4} {'วิธีอ่าน':<10} {'ชนิดเอกสาร':<22}"
          f"{'สถานะ':<16}{'คะแนน':>6}{'ห่าง':>6}  หมายเหตุ")
    print("-" * 130)
    tally = {}
    for pdf in paths:
        name = os.path.basename(pdf)[:33]
        for p in range(1, n_pages(pdf) + 1):
            r, how = classify_page(pdf, p)
            tally[r.status] = tally.get(r.status, 0) + 1
            print(f"{name:<34}{p:>4} {how:<10} {r.name_th:<22}"
                  f"{r.status:<16}{r.score:>6.0f}{r.margin:>6.0f}  {r.note}")
    print("-" * 130)
    tot = sum(tally.values())
    for k, v in sorted(tally.items(), key=lambda x: -x[1]):
        print(f"  {k:<20}{v:>4} หน้า  ({v/tot*100:.0f}%)")


if __name__ == "__main__":
    files = [f for a in sys.argv[1:] for f in sorted(glob.glob(a))]
    if not files:
        print("ใช้: python scripts/classify_pages.py docs_in/*.pdf")
        sys.exit(1)
    main(files)
