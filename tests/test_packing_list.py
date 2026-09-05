# -*- coding: utf-8 -*-
"""ชุดทดสอบตัวอ่าน Packing List

ทุกกรณีจำลองจากตาราง Packing List จริงในชุดตัวอย่าง 5 ชุด
"""
import sys, os
# ให้ทำงานได้ทั้งเมื่อ package อยู่ข้าง tests/ และเมื่ออยู่ใต้ src/
_here = os.path.dirname(os.path.abspath(__file__))
for _p in ("..", os.path.join("..", "src")):
    sys.path.insert(0, os.path.abspath(os.path.join(_here, _p)))
from customs_checker.tables import Cell, Row
from customs_checker.packing_list import (analyze_packing_list, find_total_row,
                                          text_totals)
from customs_checker.tables import numeric_columns
from customs_checker.packing_list import numeric_rows


def table(spec, h=20, gap=60):
    """สร้างแถวจาก [(ข้อความ, ขอบขวา), ...] ต่อหนึ่งแถว"""
    rows = []
    for i, line in enumerate(spec):
        y = i * gap
        rows.append(Row([Cell(t, x - 70, y, x, y + h) for t, x in line]))
    return rows


# ---------------- ชุดที่ 4 HENGYUAN — เคสที่จับผิดได้จริง ----------------
HENGYUAN = [
    [("ITEM", 250), ("QTY (PCS)", 400), ("CARTONS", 500), ("PALLETS", 590),
     ("Total CBM", 680), ("G.W.(KGS)", 790), ("N.W.(KGS)", 900)],
    [("C91542", 250), ("500", 400), ("125", 500), ("4", 590),
     ("9.19", 680), ("1712.00", 790), ("1500.00", 900)],
    [("C91542", 250), ("500", 400), ("125", 500), ("4", 590),
     ("9.19", 680), ("1712.00", 790), ("1500.00", 900)],
    [("Total:", 250), ("1000", 400), ("250", 500), ("8", 590),
     ("18.38", 680), ("3424.00", 790), ("3000.00", 900)],
]
HENGYUAN_TEXT = """TOTAL PACKED IN EIGHT (8) PLTS ONLY.
TOTAL GROSS WEIGHT: 3424.00KGS
TOTAL NET WEIGHT: 3000.00KGS
TOTAL MEASUREMENT: 9.19CBM"""


def test_หาแถวรวมได้โดยไม่ต้องอ่านคำว่า_total():
    cols = numeric_columns(numeric_rows(table(HENGYUAN)))
    ri, agree = find_total_row(cols)
    assert ri == 3, (ri, agree)
    assert len(agree) >= 5


def test_จับข้อความใต้ตารางที่ขัดกับตารางได้():
    """เคสจริงชุดที่ 4 — ข้อความเขียน 9.19 CBM ซึ่งเป็นค่าบรรทัดเดียว
    ส่วนตารางรวมได้ 18.38 ข้อผิดนี้หลุดถึงเอกสารตัวจริง"""
    r = analyze_packing_list(table(HENGYUAN), HENGYUAN_TEXT)
    assert r.total_row == 3
    assert len(r.issues) == 1, r.issues
    assert "9.19" in r.issues[0] and "18.38" in r.issues[0]
    m = {t.label: t.matched for t in r.texts}
    assert m["GROSS WEIGHT"] == "ตรงกับยอดรวมในตาราง"
    assert m["NET WEIGHT"] == "ตรงกับยอดรวมในตาราง"
    assert m["MEASUREMENT"] == "ตรงกับค่าของบรรทัดเดียว ไม่ใช่ยอดรวม"


def test_ประโยคใต้ตารางต้องไม่ถูกจัดเข้าคอลัมน์ตัวเลข():
    """พบจริงตอนทดสอบกับกล่องข้อความ: บรรทัด
    'TOTAL PACKED IN EIGHT (8) PLTS ONLY.' ถูกอ่านเป็นเลข 8
    แล้วถูกจัดเข้าคอลัมน์พาเลทเพราะขอบขวาบังเอิญตรงกัน
    ทำให้ผลรวมของคอลัมน์นั้นเพี้ยน แล้วคอลัมน์พาเลทหายไปทั้งคอลัมน์"""
    spec = HENGYUAN + [[("TOTAL PACKED IN EIGHT (8) PLTS ONLY.", 600)]]
    cols = numeric_columns(numeric_rows(table(spec)))
    pallet = [c for c in cols if abs(_x(c) - 590) < 5]
    assert pallet, "ไม่พบคอลัมน์พาเลท"
    assert len(pallet[0]) == 3, [v.text for v in pallet[0].values()]

    r = analyze_packing_list(table(spec), HENGYUAN_TEXT)
    xs = sorted(round(c.x) for c in r.columns)
    assert 590 in xs, xs


def _x(col):
    from statistics import median
    return median(c.x1 for c in col.values())


# ---------------- ชุดที่ 2 SOLEX — ต้องไม่เตือนผิด ----------------
SOLEX = [
    [("PO", 250), ("QTY", 400), ("CTNS", 480), ("N.W.", 600), ("G.W.", 700),
     ("CBM", 800)],
    [("4308001590", 250), ("400", 400), ("80", 480), ("960.00", 600),
     ("1120.00", 700), ("7.2", 800)],
    [("4308001598", 250), ("500", 400), ("100", 480), ("1075.00", 600),
     ("1275.00", 700), ("7.1", 800)],
    [("4308001616", 250), ("1700", 400), ("340", 480), ("3655.00", 600),
     ("4335.00", 700), ("24.14", 800)],
    [("Total", 250), ("2600", 400), ("520", 480), ("5690", 600),
     ("6730", 700), ("38.44", 800)],
]

def test_เอกสารที่ถูกต้อง_ต้องไม่มีข้อผิด():
    r = analyze_packing_list(
        table(SOLEX), "SAY TOTAL FIVE HUNDRED AND TWENTY (520) CTNS ONLY.")
    assert r.total_row == 4 and r.issues == [], r.issues
    assert r.texts[0].matched == "ตรงกับยอดรวมในตาราง"
    assert r.ok


# ---------------- ชุดที่ 5 FOSHAN — คอลัมน์รวมเซลล์ ----------------
# คอลัมน์พาเลท/น้ำหนัก พิมพ์ค่าเดียวคร่อมหลายบรรทัด จึงมีแค่ค่าเดียวกับยอดรวม
FOSHAN = [
    [("NO", 200), ("Package", 380), ("Quantity", 480), ("Pallets", 560),
     ("Net weight", 680), ("Gross weight", 800)],
    [("1", 200), ("8", 380), ("8150", 480)],
    [("2", 200), ("8", 380), ("8280", 480), ("2", 560), ("1991.00", 680),
     ("2051.00", 800)],
    [("3", 200), ("4", 380), ("4035", 480)],
    [("TOTAL:", 200), ("20", 380), ("20465", 480), ("2", 560), ("1991.00", 680),
     ("2051.00", 800)],
]

def test_คอลัมน์ที่รวมเซลล์_ยังอ่านได้():
    r = analyze_packing_list(table(FOSHAN), "")
    assert r.total_row == 4, r.status
    solid = [c for c in r.columns if not c.trivial]
    assert len(solid) >= 2, [(c.col, c.values, c.printed) for c in r.columns]


# ---------------- ใบที่มียอดรวมเฉพาะเป็นข้อความ ไม่มีแถวรวมในตาราง ----------------
NO_TOTAL_ROW = [
    [("ITEM", 250), ("PCS", 400), ("CTNS", 500), ("N.W.", 620), ("CBM", 740)],
    [("A", 250), ("60", 400), ("2", 500), ("8.00", 620), ("0.080", 740)],
    [("B", 250), ("90", 400), ("2", 500), ("12.50", 620), ("0.120", 740)],
]
NO_TOTAL_TEXT = """TOTALPCS 150 PCS
TOTALCTNS 4 CTNS
TOTAL N.W. 20.50 KGS
TOTALCBM 0.200 CBM"""


def test_ยอดรวมอยู่ในข้อความอย่างเดียว_ไม่มีแถวรวมในตาราง():
    """พบจริง (Scan2026-09-03_181503 หน้า 4) — ตารางมีแต่บรรทัดสินค้า
    ยอดรวมเขียนเป็นข้อความใต้ตารางล้วน ๆ"""
    r = analyze_packing_list(table(NO_TOTAL_ROW), NO_TOTAL_TEXT)
    assert r.total_row is None
    assert len(r.columns) >= 2, r.status
    assert "ยืนยันด้วยยอดรวมที่เขียนเป็นข้อความ" in r.status
    assert r.issues == [], r.issues


def test_ยอดในข้อความไม่ตรงกับผลบวกเลย_ต้องไม่ยืนยัน():
    r = analyze_packing_list(table(NO_TOTAL_ROW), "TOTAL 999 PCS\nTOTAL 888 CTNS")
    assert r.columns == [] and "ต้องให้คนตรวจ" in r.status


# ---------------- ด่านกันข้อผิดเงียบ ----------------
def test_คอลัมน์เดียวลงตัว_ต้องไม่เชื่อ():
    """คอลัมน์เดียวอาจลงตัวโดยบังเอิญ ต้องมีอย่างน้อย 2 คอลัมน์เห็นตรงกัน"""
    spec = [
        [("A", 300), ("B", 500)],
        [("10", 300), ("7", 500)],
        [("20", 300), ("9", 500)],
        [("30", 300), ("99", 500)],     # คอลัมน์ A ลงตัว คอลัมน์ B ไม่ลงตัว
    ]
    r = analyze_packing_list(table(spec), "")
    assert r.total_row is None and "ต้องให้คนตรวจ" in r.status


def test_ไม่มีตาราง():
    r = analyze_packing_list(table([[("PACKING LIST", 400)]]), "")
    assert r.total_row is None and r.status == "ไม่พบตารางตัวเลข"


# ---------------- ยอดรวมที่เขียนเป็นข้อความ ----------------
def test_ดึงยอดรวมจากข้อความได้ทุกรูปแบบที่พบจริง():
    got = {t.label: (t.value, t.unit) for t in text_totals(
        "TOTAL PACKED IN EIGHT (8) PLTS ONLY.\n"
        "TOTAL GROSS WEIGHT: 3424.00KGS\n"
        "TOTAL MEASUREMENT: 9.19CBM\n"
        "SAY TOTAL FIVE HUNDRED AND TWENTY (520) CTNS ONLY.")}
    assert got["PACKED IN EIGHT"] == (8.0, "PLTS")
    assert got["GROSS WEIGHT"] == (3424.0, "KGS")
    assert got["MEASUREMENT"] == (9.19, "CBM")
    assert got["FIVE HUNDRED AND TWENTY"] == (520.0, "CTNS")


def test_แถวรวมในตารางเอง_ต้องไม่ถูกเทียบเป็นข้อความใต้ตาราง():
    """ชุดที่ 3 เขียนป้ายแถวรวมว่า 'TOTAL PACKED ON ONE (1) PALLET:'
    แล้วตามด้วยตัวเลขยอดรวมบนบรรทัดเดียวกัน ต้องไม่ฟ้องว่า 1 ไม่ตรงกับอะไร"""
    spec = [
        [("PCS", 400), ("CTNS", 500), ("N.W.", 620), ("G.W.", 740)],
        [("36", 400), ("2", 500), ("28.80", 620), ("31.30", 740)],
        [("36", 400), ("2", 500), ("28.80", 620), ("31.30", 740)],
        [("72", 400), ("4", 500), ("57.40", 620), ("62.40", 740)],
        [("144", 400), ("8", 500), ("115.00", 620), ("125.00", 740)],
    ]
    r = analyze_packing_list(
        table(spec), "TOTAL PACKED ON ONE (1) PALLET: 144 8 115.00 125.00")
    assert r.total_row == 4
    assert r.issues == [], r.issues
    assert r.texts[0].matched == "เป็นแถวรวมในตารางเอง ไม่ใช่ข้อความใต้ตาราง"


def test_ข้อความที่ไม่มีคอลัมน์รองรับ_ต้องไม่นับเป็นข้อผิด():
    r = analyze_packing_list(table(SOLEX), "TOTAL PACKED ON ONE (1) PALLET ONLY.")
    assert r.issues == []
    assert "ตรวจไม่ได้" in r.texts[0].matched
