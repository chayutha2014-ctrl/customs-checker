# -*- coding: utf-8 -*-
"""แยกไฟล์ PDF หนึ่งไฟล์ออกเป็น "เอกสาร" หลายฉบับ

ทำ 3 อย่างต่อกัน
  1. อ่านทุกหน้า (text layer ถ้ามี ไม่งั้น OCR)
  2. จำแนกชนิดเอกสารรายหน้า
  3. รวมหน้าที่ต่อเนื่องกันเป็นฉบับ + ประเมินสภาพหน้ากระดาษ

ใช้:  python scripts/split_docs.py docs_in/*.pdf
      python scripts/split_docs.py --no-color docs_in/*.pdf   (ข้ามการวัดสี เร็วขึ้น)
"""
from __future__ import annotations
import subprocess, sys, os, re, glob, json, hashlib, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from customs_checker.doctype import classify                     # noqa: E402
from customs_checker.docgroup import group_pages, page_condition  # noqa: E402

TITLE_ZONE = 0.22
TEXT_LAYER_MIN_WORDS = 20
OCR_DPI = 200
COLOR_DPI = 72          # วัดสีไม่ต้องละเอียด
CACHE = ".page_cache.json"


def _run(cmd): return subprocess.run(cmd, capture_output=True, text=True).stdout
def n_pages(f):
    m = re.search(r"^Pages:\s+(\d+)", _run(["pdfinfo", f]), re.M); return int(m.group(1)) if m else 0
def page_size(f):
    m = re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", _run(["pdfinfo", f]))
    return (float(m.group(1)), float(m.group(2))) if m else (595.0, 842.0)
def text_layer(f, p, crop=None):
    c = ["pdftotext", "-f", str(p), "-l", str(p)]
    if crop:
        x, y, w, h = crop; c += ["-x", str(int(x)), "-y", str(int(y)), "-W", str(int(w)), "-H", str(int(h))]
    return _run(c + [f, "-"])

_THA = None
def _has_tha():
    global _THA
    if _THA is None: _THA = "tha" in _run(["tesseract", "--list-langs"])
    return _THA

def _render(f, p, dpi):
    d = tempfile.mkdtemp(); b = os.path.join(d, "pg")
    subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(p), "-l", str(p), "-png", f, b],
                   capture_output=True)
    g = glob.glob(b + "*.png"); return g[0] if g else None

def _tess(img):
    return _run(["tesseract", img, "stdout", "-l", "tha+eng" if _has_tha() else "eng", "--psm", "3"])


def _orientation(img):
    """ถามเทสเซอแรกต์ว่าหน้านี้หมุนอยู่กี่องศา (0/90/180/270)

    ที่มา: พบหน้าที่สแกนกลับหัว OCR ได้ข้อความอ่านไม่ออก เช่น IWLOL ซึ่งคือ
    TOTAL ที่กลับหัว ถ้าไม่หมุนก่อน ทั้งการจำแนกและการอ่านค่าจะพังทั้งหน้า
    """
    out = _run(["tesseract", img, "stdout", "--psm", "0"])
    m = re.search(r"Rotate:\s*(\d+)", out)
    return int(m.group(1)) if m else 0


def _autorotate(img):
    """หมุนภาพให้ตั้งตรงถ้าจำเป็น คืน path ที่ควรใช้ต่อ"""
    try:
        deg = _orientation(img)
        if deg % 360 == 0:
            return img, 0
        from PIL import Image
        rot = img.replace(".png", f"_r{deg}.png")
        Image.open(img).rotate(-deg, expand=True).save(rot)
        return rot, deg
    except Exception:
        return img, 0

def ocr_page(f, p, rotate=False):
    """OCR หน้าเดียว  rotate=True จะถาม OSD ว่าหน้าหมุนอยู่หรือไม่แล้วหมุนก่อน

    การถาม OSD เพิ่มเวลาเกือบเท่าตัว จึงเรียกเฉพาะตอนที่อ่านครั้งแรกแล้วจำแนกไม่ได้
    """
    src = _render(f, p, OCR_DPI)
    if not src: return "", ""
    if rotate:
        src, deg = _autorotate(src)
        if not deg:
            return "", ""          # ไม่ได้หมุน ไม่ต้องอ่านซ้ำ
        print(f"    (หน้า {p} หมุนอยู่ {deg} องศา อ่านใหม่หลังหมุน)")
    full, title = _tess(src), ""
    try:
        from PIL import Image
        im = Image.open(src); c = src.replace(".png", "_t.png")
        im.crop((0, 0, im.width, int(im.height * TITLE_ZONE))).save(c)
        title = _tess(c)
    except Exception:
        pass
    return full, title

def color_pct(f, p):
    """สัดส่วนพิกเซลที่มีสีชัดเจน (%) — ใช้บอกว่ามีตราประทับ/ลายเซ็นสีทับหรือไม่"""
    try:
        from PIL import Image
    except Exception:
        return None
    src = _render(f, p, COLOR_DPI)
    if not src: return None
    im = Image.open(src).convert("RGB"); px = im.load(); W, H = im.size; n = 0
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            mx, mn = max(r, g, b), min(r, g, b)
            if mx > 60 and mx - mn > 60: n += 1
    return n / (W * H) * 100


def load_cache():
    try: return json.load(open(CACHE, encoding="utf-8"))
    except Exception: return {}

def read_pages(pdf, cache, want_color=True):
    key0 = hashlib.md5((os.path.abspath(pdf) + str(os.path.getmtime(pdf))).encode()).hexdigest()[:12]
    out = []
    for p in range(1, n_pages(pdf) + 1):
        k = f"{key0}:{p}"
        if k in cache and (not want_color or cache[k].get("color") is not None):
            out.append(cache[k]); continue
        full = text_layer(pdf, p)
        if len(full.split()) >= TEXT_LAYER_MIN_WORDS:
            w, h = page_size(pdf)
            title, how = text_layer(pdf, p, (0, 0, w, h * TITLE_ZONE)), "text layer"
            if not classify(full, title).ok:
                f2, t2 = ocr_page(pdf, p)
                if classify(f2 or full, t2).ok:
                    full, title, how = (f2 or full), t2, "text+OCR"
        else:
            full, title = ocr_page(pdf, p); how = "OCR"
        if not classify(full, title).ok:
            # ยังจำแนกไม่ได้ — ลองดูว่าหน้าถูกสแกนกลับหัวหรือตะแคงหรือเปล่า
            f3, t3 = ocr_page(pdf, p, rotate=True)
            if f3 and classify(f3, t3).ok:
                full, title, how = f3, t3, how + "+หมุน"
        rec = {"page": p, "text": full, "title": title, "how": how,
               "color": color_pct(pdf, p) if want_color else None}
        cache[k] = rec; out.append(rec)
    return out


def main(paths, want_color=True):
    cache = load_cache()
    for pdf in paths:
        pages = read_pages(pdf, cache, want_color)
        recs = []
        for r in pages:
            c = classify(r["text"], r["title"])
            recs.append({"page": r["page"], "code": c.code, "name_th": c.name_th,
                         "text": r["text"], "status": c.status, "note": c.note,
                         "how": r["how"], "color": r["color"]})
        docs = group_pages(recs)
        print(f"\n=== {os.path.basename(pdf)}  ({len(pages)} หน้า -> {len(docs)} ฉบับ)")
        print(f"{'ฉบับ':<5}{'ชนิดเอกสาร':<22}{'หน้า':<10}{'เลขเอกสาร':<24}"
              f"{'สภาพหน้า':<22}{'ข้อสังเกต':<12}{'สถานะ':<10} หมายเหตุ")
        for i, d in enumerate(docs, 1):
            txt = "\n".join(r["text"] for r in recs if r["page"] in d.pages)
            cols = [r["color"] for r in recs if r["page"] in d.pages and r["color"] is not None]
            cond = page_condition(txt, max(cols) if cols else None)
            pg = ",".join(map(str, d.pages))
            print(f"{i:<5}{d.name_th:<22}{pg:<10}{(d.ident or '-'):<24}"
                  f"{cond['สภาพหน้า']:<22}{cond['ร่าง/ตัวจริง']:<12}{d.status:<10} "
                  f"{d.note}{(' | ' + cond['หมายเหตุ']) if cond['หมายเหตุ'] else ''}")
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--no-color"]
    files = [f for a in args for f in sorted(glob.glob(a))]
    if not files:
        print("ใช้: python scripts/split_docs.py docs_in/*.pdf"); sys.exit(1)
    main(files, want_color="--no-color" not in sys.argv)
