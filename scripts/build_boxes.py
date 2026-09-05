#!/usr/bin/env python3
"""สร้าง docs_out/_box_cache.json — กล่องข้อความพร้อมพิกัด สำหรับทุกหน้าใน docs_in

แทนที่ตัวเดิมที่ฝังอยู่ใน table_test.py ซึ่งวนเฉพาะไฟล์ในชุดเฉลย จึงได้แค่ 6 หน้า
ตัวนี้
  - วนทุกไฟล์ที่สั่ง ไม่ผูกกับไฟล์เฉลย
  - หน้าที่มี text layer ใช้พิกัดจาก pdftotext -bbox-layout ไม่ต้อง OCR (เร็วและตรง)
  - หน้าที่เป็นสแกน หมุนให้ตั้งตรงก่อน แล้วค่อย OCR ด้วย RapidOCR
  - ทำต่อจากของเดิมได้ หน้าที่มีใน cache แล้วจะข้าม

ใช้:  python scripts/build_boxes.py docs_in/*.pdf
      python scripts/build_boxes.py --force docs_in/VORETO.pdf     อ่านใหม่ทับของเดิม
      python scripts/build_boxes.py --ocr-only docs_in/*.pdf       บังคับ OCR ทุกหน้า
"""
from pathlib import Path
import json, re, subprocess, sys, glob, tempfile, os
from statistics import median
from xml.etree import ElementTree as ET

OUT = Path("docs_out")
BOX = OUT / "_box_cache.json"
DPI = 300                    # ความละเอียดที่ใช้เรนเดอร์หน้าสแกน
TEXT_LAYER_MIN_WORDS = 20    # น้อยกว่านี้ถือว่าเป็นสแกน
MERGE_GAP = 1.2              # ช่องว่างระหว่างคำที่ยังถือว่าเป็นเซลล์เดียวกัน (เท่าของความสูง)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def n_pages(pdf):
    m = re.search(r"^Pages:\s+(\d+)", run(["pdfinfo", str(pdf)]), re.M)
    return int(m.group(1)) if m else 0


# ---------------- ทางที่ 1: หน้าที่มี text layer ----------------
def words_from_pdf(pdf, page):
    """ดึงคำพร้อมพิกัดจาก text layer  คืน [(x0,y0,x1,y1,text), ...] หน่วยเป็นพิกเซลที่ DPI"""
    xml = run(["pdftotext", "-f", str(page), "-l", str(page), "-bbox-layout",
               str(pdf), "-"])
    if "<word" not in xml:
        return []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    ns = {"x": "http://www.w3.org/1999/xhtml"}
    s = DPI / 72.0
    out = []
    for line in root.iter():
        if not line.tag.endswith("}line") and line.tag != "line":
            continue
        ws = []
        for w in line:
            t = (w.text or "").strip()
            if not t:
                continue
            ws.append((float(w.get("xMin")) * s, float(w.get("yMin")) * s,
                       float(w.get("xMax")) * s, float(w.get("yMax")) * s, t))
        out.append(ws)
    return out


def merge_words(lines, gap=MERGE_GAP):
    """รวมคำที่อยู่ติดกันบนบรรทัดเดียวกันให้เป็นเซลล์เดียว

    ทำไมต้องรวม: RapidOCR คืนกล่องระดับ "ข้อความหนึ่งช่วง" แต่ pdftotext คืนทีละคำ
    ถ้าไม่รวม ประโยคใต้ตารางจะแตกเป็นคำ ๆ แล้วคำว่า "(8)" จะกลายเป็นเซลล์ตัวเลขลอย
    ที่ถูกจัดเข้าคอลัมน์ผิด — ปัญหาเดียวกับที่เคยทำคอลัมน์พาเลทหายไป
    """
    cells = []
    for ws in lines:
        if not ws:
            continue
        h = median(w[3] - w[1] for w in ws) or 1.0
        cur = list(ws[0])
        for w in ws[1:]:
            if w[0] - cur[2] <= h * gap:
                cur[2] = max(cur[2], w[2])
                cur[1] = min(cur[1], w[1])
                cur[3] = max(cur[3], w[3])
                cur[4] = cur[4] + " " + w[4]
            else:
                cells.append(tuple(cur)); cur = list(w)
        cells.append(tuple(cur))
    return cells


# ---------------- ทางที่ 2: หน้าสแกน ----------------
_RAPID = None
def rapid():
    global _RAPID
    if _RAPID is None:
        from rapidocr_onnxruntime import RapidOCR
        _RAPID = RapidOCR()
    return _RAPID


def render(pdf, page, dpi=DPI):
    d = tempfile.mkdtemp(); b = os.path.join(d, "pg")
    subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(page), "-l", str(page),
                    "-png", str(pdf), b], capture_output=True)
    g = glob.glob(b + "*.png")
    return g[0] if g else None


def autorotate(img):
    """หมุนหน้าให้ตั้งตรงก่อน OCR — หน้าที่สแกนกลับหัวหรือตะแคงอ่านไม่ออกทั้งหน้า"""
    try:
        out = run(["tesseract", img, "stdout", "--psm", "0"])
        m = re.search(r"Rotate:\s*(\d+)", out)
        deg = int(m.group(1)) if m else 0
        if deg % 360 == 0:
            return img, 0
        from PIL import Image
        rot = img.replace(".png", f"_r{deg}.png")
        Image.open(img).rotate(-deg, expand=True).save(rot)
        return rot, deg
    except Exception:
        return img, 0


def ocr_cells(pdf, page):
    src = render(pdf, page)
    if not src:
        return [], 0
    src, deg = autorotate(src)
    res, _ = rapid()(src)
    out = []
    for item in (res or []):
        box, text = item[0], item[1]
        xs = [float(p[0]) for p in box]; ys = [float(p[1]) for p in box]
        if str(text).strip():
            out.append((min(xs), min(ys), max(xs), max(ys), str(text).strip()))
    return out, deg


# ---------------- ตัวหลัก ----------------
def to_cache_format(cells):
    """แปลงเป็นรูปแบบเดียวกับที่ to_cells() ของ tables.py รับ"""
    return [[[[x0, y0], [x1, y0], [x1, y1], [x0, y1]], t]
            for x0, y0, x1, y1, t in cells]


def main(paths, force=False, ocr_only=False):
    OUT.mkdir(exist_ok=True)
    cache = json.loads(BOX.read_text(encoding="utf-8")) if BOX.exists() else {}
    n_text = n_ocr = n_skip = 0
    for pdf in paths:
        stem = Path(pdf).stem
        for p in range(1, n_pages(pdf) + 1):
            key = f"{stem}/page_{p:03d}.png"     # รูปแบบเดิม table_test2.py ยังใช้ได้

            # ลบคีย์เก่าของหน้าเดียวกันที่นามสกุลต่างกัน (เช่น .jpg จากท่อเดิม)
            # ถ้าไม่ลบ table_test2.py ซึ่งรวมทุกคีย์ที่ขึ้นต้นด้วยชื่อไฟล์
            # จะนับตารางซ้ำสองรอบ แล้วยอดรวมกลายเป็นสองเท่า
            for d in [k for k in list(cache)
                      if k.startswith(f"{stem}/page_{p:03d}.") and k != key]:
                del cache[d]
                print(f"  ลบคีย์ซ้ำของหน้าเดียวกัน: {d}")

            if key in cache and not force:
                n_skip += 1
                continue
            cells, how = [], ""
            if not ocr_only:
                lines = words_from_pdf(pdf, p)
                if sum(len(w) for w in lines) >= TEXT_LAYER_MIN_WORDS:
                    cells, how = merge_words(lines), "text layer"
            if not cells:
                cells, deg = ocr_cells(pdf, p)
                how = "OCR" + (f" (หมุน {deg}°)" if deg else "")
            cache[key] = to_cache_format(cells)
            n_text += how.startswith("text")
            n_ocr += how.startswith("OCR")
            print(f"  {key:<42} {how:<16} {len(cells):>4} เซลล์")
    BOX.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"\nเขียน {BOX}  รวม {len(cache)} หน้า")
    print(f"  อ่านจาก text layer {n_text} หน้า · OCR {n_ocr} หน้า · ข้ามของเดิม {n_skip} หน้า")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    files = [f for a in args for f in sorted(glob.glob(a))]
    if not files:
        print("ใช้: python scripts/build_boxes.py docs_in/*.pdf"); sys.exit(1)
    main(files, force="--force" in sys.argv, ocr_only="--ocr-only" in sys.argv)
