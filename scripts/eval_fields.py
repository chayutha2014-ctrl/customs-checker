#!/usr/bin/env python3
"""
วัดว่าค่าที่ถูกต้อง (จาก _truth.csv) ปรากฏในผล OCR ของแต่ละเครื่องยนต์หรือไม่
= เพดานสูงสุดที่เป็นไปได้ของแต่ละเครื่องยนต์
"""
from pathlib import Path
import csv, re, json
from datetime import date
from customs_checker.dates import parse_date
import pytesseract
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

OUT = Path("docs_out")
import sys
TRUTH = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "_truth.csv"
CACHE_NAME = TRUTH.stem + "_cache.json"
CACHE = OUT / CACHE_NAME
FIELDS = ["invoice_no", "invoice_date", "currency",
          "total_amount", "line1_qty", "line1_unit_price"]
MONS = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
FULL = ["JANUARY","FEBRUARY","MARCH","APRIL","MAY","JUNE","JULY","AUGUST",
        "SEPTEMBER","OCTOBER","NOVEMBER","DECEMBER"]


def squash(s: str) -> str:
    return re.sub(r"[\s,'’]", "", s.upper())


def date_variants(iso: str) -> set:
    y, m, d = iso.split("-")
    di, mi = str(int(d)), str(int(m))
    mon, full = MONS[int(m) - 1], FULL[int(m) - 1]
    v = set()
    for sep in ["/", "-", ".", ""]:
        for a, b in [(d, m), (m, d), (di, mi), (mi, di)]:
            v.add(f"{a}{sep}{b}{sep}{y}")
        v.add(f"{y}{sep}{m}{sep}{d}")
    for name in (mon, full):
        for dd in (d, di):
            v.update({f"{dd}{name}{y}", f"{name}{dd}{y}", f"{name}{dd},{y}"})
    yy = y[2:]
    for x in list(v):
        v.add(x.replace(y, yy))
    return {squash(x) for x in v}


def numbers_in(text: str) -> set:
    out = set()
    for tok in re.findall(r"\d[\d,]*\.?\d*", text):
        try:
            out.add(round(float(tok.replace(",", "")), 3))
        except ValueError:
            pass
    return out


def found(field: str, truth: str, text: str) -> bool:
    if not truth or truth == "-":
        return True
    flat = squash(text)
    if field == "invoice_date":
        return date_found(truth, text)
    if field in {"total_amount", "line1_qty", "line1_unit_price"}:
        try:
            return round(float(truth), 3) in numbers_in(text)
        except ValueError:
            return squash(truth) in flat
    return squash(truth) in flat



# ตัวจับข้อความที่หน้าตาเหมือนวันที่ แล้วส่งให้ตัวแปลงของระบบตัดสิน
DATE_TOKEN = re.compile(
    r"\d{1,4}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*\d{2,4}"
    r"|\d{1,2}(?:ST|ND|RD|TH)?[\s.,/-]*(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*[\s.,/-]*\d{2,4}"
    r"|(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*[\s.,/-]*\d{1,2}(?:ST|ND|RD|TH)?[\s.,/-]*\d{2,4}"
    r"|\d{1,2}\s*(?:ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.)\s*\d{2,4}",
    re.I)

# วันอ้างอิงคงที่ ไม่ผูกกับเฉลย เพื่อไม่ให้การวัดวนเป็นวงกลม
REF = date(2026, 9, 4)


def date_found(truth: str, text: str) -> bool:
    want = date.fromisoformat(truth)
    for m in DATE_TOKEN.finditer(text):
        got = parse_date(m.group(0), ref=REF)
        if got.value == want:
            return True
        if got.ambiguous and want in (got.alternatives or ()):
            return True
    return False


def main() -> None:
    rows = list(csv.DictReader(TRUTH.open(encoding="utf-8")))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    rapid = RapidOCR()

    score = {e: {f: 0 for f in FIELDS} for e in ("tesseract", "rapidocr", "รวมกัน")}
    details = []

    for r in rows:
        key = f"{r['file']}/{r['page']}"
        if key not in cache:
            if r["page"] == "*":
                pages = sorted(q for q in (OUT / r["file"]).glob("page_*")
                               if q.suffix.lower() in {".png", ".jpg", ".jpeg"})
            else:
                pages = [OUT / r["file"] / r["page"]]
            t_all, r_all = [], []
            for pg in pages:
                t_all.append(pytesseract.image_to_string(Image.open(pg), lang="eng+tha"))
                res, _ = rapid(str(pg))
                r_all.append(" ".join(i[1] for i in (res or [])))
            cache[key] = {"tesseract": "\n".join(t_all), "rapidocr": "\n".join(r_all)}
            print(f"  OCR {key} ({len(pages)} หน้า)")
        texts = cache[key]
        texts["รวมกัน"] = texts["tesseract"] + "\n" + texts["rapidocr"]

        row_detail = {"page": key, "results": {}}
        for f in FIELDS:
            for eng in ("tesseract", "rapidocr", "รวมกัน"):
                ok = found(f, r[f], texts[eng])
                score[eng][f] += ok
                row_detail["results"].setdefault(f, {})[eng] = ok
        details.append(row_detail)

    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    n = len(rows)

    print("\n" + "=" * 70)
    print(f"ค่าที่ถูกต้องปรากฏในผล OCR หรือไม่  ({n} หน้า)\n")
    print(f"{'ฟิลด์':<20}{'Tesseract':>13}{'RapidOCR':>13}{'รวมสองตัว':>14}")
    for f in FIELDS:
        t, rp, c = (score[e][f] for e in ("tesseract", "rapidocr", "รวมกัน"))
        print(f"{f:<20}{t:>6}/{n:<6}{rp:>6}/{n:<6}{c:>7}/{n:<6}")
    tot = {e: sum(score[e].values()) for e in score}
    all_n = n * len(FIELDS)
    print("-" * 70)
    print(f"{'รวมทุกฟิลด์':<20}"
          f"{tot['tesseract']:>4}/{all_n} ({tot['tesseract']/all_n*100:.0f}%)"
          f"{tot['rapidocr']:>6}/{all_n} ({tot['rapidocr']/all_n*100:.0f}%)"
          f"{tot['รวมกัน']:>6}/{all_n} ({tot['รวมกัน']/all_n*100:.0f}%)")

    print("\nหน้าที่พลาด (รวมสองเครื่องยนต์แล้วยังหาไม่เจอ)")
    miss = 0
    for d in details:
        bad = [f for f, v in d["results"].items() if not v["รวมกัน"]]
        if bad:
            miss += 1
            print(f"   {d['page']:<44} {', '.join(bad)}")
    if not miss:
        print("   ไม่มี — เจอครบทุกฟิลด์")


if __name__ == "__main__":
    main()
