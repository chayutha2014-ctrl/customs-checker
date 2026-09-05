#!/usr/bin/env python3
"""เพิ่ม split_glued() เข้า tables.py และเรียกใช้ที่ต้น analyze_invoice

ตรวจสอบตัวเองทุกขั้น สำรองไฟล์เดิมเป็น .bak ก่อนเขียน
ถ้าอะไรไม่ตรงจะหยุดโดยไม่แตะไฟล์
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src" / "customs_checker" / "tables.py"

FUNC = '''

_GLUED = re.compile(r"^(?P<num>\\d[\\d.,]*)\\s+(?P<junk>\\S{1,4})$")


def split_glued(rows, max_junk=4):
    """แยกเซลล์ที่ OCR เชื่อมข้อความคนละช่องมาไว้ด้วยกัน แล้วหั่นกล่องตามสัดส่วน

    ทำไมต้องแยก: numeric_columns() จัดคอลัมน์จากขอบขวาของเซลล์
    เซลล์ "269.00 26" มีขอบขวาอยู่ที่เลขลำดับ ไม่ใช่ที่จำนวนเงิน
    มันจึงถูกจัดเข้าคอลัมน์เลขลำดับ ทำให้คอลัมน์จำนวนเงินถูกฉีกเป็นสองคอลัมน์
    analyze_invoice เลือกคอลัมน์จำนวนเงินได้คอลัมน์เดียว อีกครึ่งจึงหลุดหายเงียบ ๆ
    (HUANYU ขาดบรรทัด 20 x 13.45 = 269.00 พอดี)

    ไม่แยกเมื่อคำท้ายเป็นชื่อหน่วย เพราะ "150.00 MTR" คือตัวเลขเดียวที่มีหน่วยกำกับ
    ไม่ใช่สองช่องที่ติดกัน

    ตำแหน่งที่หั่นประมาณจากจำนวนตัวอักษร ซึ่งเพียงพอเพราะการจัดคอลัมน์
    ใช้ระยะคลาดเคลื่อนราวหนึ่งเท่าของความสูงตัวอักษรอยู่แล้ว
    """
    out = []
    for r in rows:
        cells = []
        for c in r.cells:
            m = _GLUED.match(c.text)
            if (m is None or len(m.group("junk")) > max_junk
                    or is_unit(m.group("junk"))
                    or parse_number(m.group("num")) is None):
                cells.append(c)
                continue
            t = c.text
            cut = m.end("num")
            w = c.x1 - c.x0
            n = len(t)
            xa = c.x0 + w * cut / n
            xb = c.x0 + w * m.start("junk") / n
            cells.append(Cell(m.group("num"), c.x0, c.y0, xa, c.y1))
            cells.append(Cell(m.group("junk"), xb, c.y0, c.x1, c.y1))
        cells.sort(key=lambda c: c.x0)
        out.append(Row(cells))
    return out
'''

CALL_ANCHOR = '''    res = {"lines": [], "computed": None, "printed": None,
           "missing_lines": [], "gap": None, "status": "ไม่พบตาราง",
           "n_numeric_cols": 0}'''

CALL_NEW = '''    rows = split_glued(rows)
''' + CALL_ANCHOR


def main():
    if not TARGET.exists():
        sys.exit(f"ไม่พบไฟล์ {TARGET}")
    src = TARGET.read_text(encoding="utf-8")

    if "def split_glued" in src:
        sys.exit("มี split_glued อยู่แล้ว ไม่ทำอะไร")

    anchor = "def _col_x(col):\n    return median(c.x1 for c in col.values())"
    if anchor not in src:
        sys.exit("ไม่พบ _col_x ตามที่คาด หยุดโดยไม่แตะไฟล์")
    if CALL_ANCHOR not in src:
        sys.exit("ไม่พบต้น analyze_invoice ตามที่คาด หยุดโดยไม่แตะไฟล์")

    new = src.replace(anchor, anchor + FUNC, 1)
    new = new.replace(CALL_ANCHOR, CALL_NEW, 1)

    if "from .numbers import parse_number" in new and "is_unit" not in new.split("\n")[9]:
        new = new.replace("from .numbers import parse_number",
                          "from .numbers import parse_number, is_unit", 1)
    if "is_unit" not in new:
        sys.exit("นำเข้า is_unit ไม่สำเร็จ หยุดโดยไม่แตะไฟล์")

    compile(new, str(TARGET), "exec")

    TARGET.with_suffix(".py.bak").write_text(src, encoding="utf-8")
    TARGET.write_text(new, encoding="utf-8")
    print(f"แก้ {TARGET} แล้ว  สำรองเดิมไว้ที่ {TARGET.with_suffix('.py.bak')}")

    sys.path.insert(0, str(ROOT / "src"))
    from customs_checker.tables import split_glued, Cell, Row  # noqa: E402
    r = Row([Cell("269.00 26", 2114.5, 100.0, 2399.9, 140.0),
             Cell("150.00 MTR", 1437.9, 100.0, 1670.4, 140.0)])
    got = split_glued([r])[0].cells
    assert len(got) == 3, [c.text for c in got]
    assert got[0].text == "150.00 MTR"
    assert [c.text for c in got[1:]] == ["269.00", "26"], [c.text for c in got]
    assert got[1].x1 < 2399.9
    print("ตรวจสอบหลังแก้: ผ่าน")


if __name__ == "__main__":
    main()
